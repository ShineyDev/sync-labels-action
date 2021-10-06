import argparse
import asyncio
import collections
import sys
import textwrap
import traceback

import aiohttp
import graphql
import yaml

try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader


_VersionInfo = collections.namedtuple("_VersionInfo", "major minor micro release serial")

version = "0.0.0a"
version_info = _VersionInfo(0, 0, 0, "alpha", 0)


_printers = list()


def _create_printer(*, level=None, prefix=None, suffix=None, stream=None):
    def printer(*args, **kwargs):
        if not printer.is_active:
            return

        args = list(args)

        e = None
        if args and isinstance(args[-1], BaseException):
            *args, e = args
            args.append("See the error output below.")

        file = kwargs.pop("file", stream) or sys.stdout

        if prefix:
            if args:
                args[0] = prefix + (args[0] if isinstance(args[0], str) else repr(args[0]))
            else:
                args = [prefix]

        if suffix:
            if args:
                args[-1] = (args[-1] if isinstance(args[-1], str) else repr(args[-1])) + suffix
            else:
                args = [suffix]

        if e is not None:
            args.append("\n\n" + textwrap.indent("".join(traceback.format_exception(type(e), e, e.__traceback__)), "    "))

        print(*args, file=file, **kwargs)

    printer.is_active = True
    if level is not None:
        printer.level = level
        printer.is_active = False

        _printers.append(printer)

    return printer


print_debug = _create_printer(level=4, prefix="  \x1B[32m[DEBUG]\x1B[39m ", suffix="")
print_info = _create_printer(level=3, prefix="   \x1B[34m[INFO]\x1B[39m ", suffix="")
print_warning = _create_printer(level=2, prefix="\x1B[33m[WARNING]\x1B[39m ", suffix="")
print_error = _create_printer(level=1, prefix="  \x1B[31m[ERROR] ", stream=sys.stderr, suffix="\x1B[39m")


# fmt: off
_MUTATE_LABEL_CREATE = "mutation($input:CreateLabelInput!){createLabel(input:$input){__typename}}"
_MUTATE_LABEL_DELETE = "mutation($input:DeleteLabelInput!){deleteLabel(input:$input){__typename}}"
_MUTATE_LABEL_UPDATE = "mutation($input:UpdateLabelInput!){updateLabel(input:$input){__typename}}"
_QUERY_REPOSITORY_ID = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id}}"
_QUERY_REPOSITORY_LABELS_PAGE = "query($cursor:String,$repository_id:ID!){node(id:$repository_id){...on Repository{labels(after:$cursor,first:10){pageInfo{endCursor,hasNextPage}nodes{color,description,id,name}}}}}"
# fmt: on


async def main(*, partial, repository, source, token):
    print_info(f"Running ShineyDev/sync-labels-action v{version}.")

    async def follow_sources(content, session):
        source = yaml.load(content, Loader)

        inherit = source.pop("inherit", list())
        if isinstance(inherit, str):
            inherit = [inherit]

        for source_ in inherit:
            print_info(f"Reading {'partial ' if partial else ''}source '{source_}'.")

            async with session.request("GET", source_, raise_for_status=True) as response:
                content = await response.read()

            async for source_ in follow_sources(content, session):
                yield source_

        yield source

    print_info(f"Reading {'partial ' if partial else ''}source '{source}'.")

    colors = dict()
    defaults = dict()
    groups = list()
    labels = list()

    try:
        async with aiohttp.ClientSession() as session:
            if source.startswith("http://") or source.startswith("https://"):
                async with session.request("GET", source, raise_for_status=True) as response:
                    content = await response.read()
            else:
                with open(source, "r") as stream:
                    content = stream.read()

            async for source in follow_sources(content, session):
                source_colors = source.get("colors", dict())
                if isinstance(source_colors, list):
                    source_colors = {c["name"]: c["value"] for c in source_colors}

                colors.update(source_colors)

                source_defaults = source.get("defaults", dict())
                if isinstance(source_defaults, list):
                    source_defaults = {d["name"]: d["value"] for d in source_defaults}

                defaults.update(source_defaults)

                source_groups = source.get("groups", list())
                if isinstance(source_groups, dict):
                    source_groups = [{"name": n, **d} for (n, d) in source_groups.items()]

                for group_data in source_groups:
                    group_name = group_data["name"]
                    group_color = group_data.get("color", None)
                    group_description = group_data.get("description", None)
                    group_labels = group_data.get("labels", list())
                    if isinstance(group_labels, dict):
                        group_labels = [{"name": n, **d} for (n, d) in group_labels.items()]

                    existing_group = None
                    for group in groups:
                        if group["name"] == group_name:
                            existing_group = group
                            break

                    if existing_group:
                        if group_color is not None:
                            existing_group["color"] = group_color

                        if group_description is not None:
                            existing_group["description"] = group_description

                        if group_labels and "labels" not in existing_group.keys():
                            existing_group["labels"] = list()

                        for label_data in group_labels:
                            label_name = label_data["name"]
                            label_color = label_data.get("color", None)
                            label_description = label_data.get("description", None)

                            existing_label = None
                            for label in existing_group["labels"]:
                                if label["name"] == label_name:
                                    existing_label = label
                                    break

                            if existing_label:
                                if label_color is not None:
                                    existing_label["color"] = label_color

                                if label_description is not None:
                                    existing_label["description"] = label_description
                            else:
                                data = dict()

                                if label_color is not None:
                                    data["color"] = label_color

                                if label_description is not None:
                                    data["description"] = label_description

                                data["name"] = label_name

                                existing_group["labels"].append(data)
                    else:
                        data = dict()

                        if group_color is not None:
                            data["color"] = group_color

                        if group_description is not None:
                            data["description"] = group_description

                        if group_labels:
                            data["labels"] = group_labels

                        data["name"] = group_name

                        groups.append(data)

                source_labels = source.get("labels", list())
                if isinstance(source_labels, dict):
                    source_labels = [{"name": n, **d} for (n, d) in source_labels.items()]

                for label_data in source_labels:
                    label_name = label_data["name"]
                    label_color = label_data.get("color", None)
                    label_description = label_data.get("description", None)

                    existing_label = None
                    for label in labels:
                        if label["name"] == label_name:
                            existing_label = label
                            break

                    if existing_label:
                        if label_color is not None:
                            existing_label["color"] = label_color

                        if label_description is not None:
                            existing_label["description"] = label_description
                    else:
                        data = dict()

                        if label_color is not None:
                            data["color"] = label_color

                        if label_description is not None:
                            data["description"] = label_description

                        data["name"] = label_name

                        labels.append(data)
    except (OSError, aiohttp.ClientResponseError, yaml.YAMLError) as e:
        print_error("The source you provided is not valid.", e)
        return 1

    default_color = defaults.get("color", None)
    default_description = defaults.get("description", None)

    requested_labels = dict()

    for label_data in labels:
        label_name = label_data["name"]

        label_color = label_data.get("color", None) or default_color
        if label_color is None:
            print_error(f"The label '{label_name}' does not have a color and no default was provided.")
            return 1

        if isinstance(label_color, str):
            # TODO: handle offsets

            try:
                label_color = colors[label_color]
            except KeyError as e:
                print_error(f"The label '{label_name}' requests color '{label_color}' which does not exist.", e)
                return 1

        label_description = label_data.get("description", None) or default_description

        requested_labels[label_name] = {
            "color": label_color,
            "description": label_description,
        }

    for group_data in groups:
        group_name = group_data["name"]
        group_color = group_data.get("color", None)
        group_description = group_data.get("description", None)
        group_labels = group_data.get("labels", None)

        group_prefix_length = 1
        group_prefix = group_name[:group_prefix_length]
        while any(g["name"].startswith(group_prefix) for g in groups if g["name"] != group_name):
            group_prefix_length += 1
            group_prefix = group_name[:group_prefix_length]

            if group_prefix == group_name:
                break

        for label_data in group_labels:
            label_name = label_data["name"]

            label_color = label_data.get("color", None) or group_color or default_color
            if label_color is None:
                print_error(f"The label '{label_name}' in group '{group_name}' does not have a color and no default was provided.")
                return 1

            if isinstance(label_color, str):
                # TODO: handle offsets

                try:
                    label_color = colors[label_color]
                except KeyError as e:
                    print_error(f"The label '{label_name}' in group '{group_name}' requests color '{label_color}' which does not exist.", e)
                    return 1

            label_description = label_data.get("description", None) or group_description or default_description

            label_name = f"{group_prefix}:{label_name}"
            if label_name in requested_labels.keys():
                print_error(f"The group '{group_name}' defines label '{label_name}' which already exists.")
                return 1

            requested_labels[label_name] = {
                "color": label_color,
                "description": label_description,
            }

    headers = {
        "Accept": "application/vnd.github.bane-preview+json",
        "Authorization": f"bearer {token}",
        "User-Agent": f"ShineyDev/sync-labels-action @ {repository}",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        client = graphql.client.Client(session=session, url="https://api.github.com/graphql")

        owner, name = repository.split("/")

        try:
            data = await client.request(_QUERY_REPOSITORY_ID, owner=owner, name=name)
        except graphql.client.ClientResponseError as e:
            print_error("The request to fetch your repository identifier failed.", e)
            return 1

        try:
            repository_id = data["repository"]["id"]
        except KeyError as e:
            print_error("The repository you provided does not exist or the token you provided cannot see it.", e)
            return 1

        existing_labels = dict()

        cursor = None
        has_next_page = True

        while has_next_page:
            try:
                data = await client.request(_QUERY_REPOSITORY_LABELS_PAGE, cursor=cursor, repository_id=repository_id)
            except graphql.client.ClientResponseError as e:
                print_error("The request to fetch your repository labels failed.", e)
                return 1

            for label in data["node"]["labels"]["nodes"]:
                existing_labels[label.pop("name")] = label

            cursor = data["node"]["labels"]["pageInfo"]["endCursor"]
            has_next_page = data["node"]["labels"]["pageInfo"]["hasNextPage"]

        error_n = 0

        if not partial:
            delete_n = 0
            for name in existing_labels.keys() - requested_labels.keys():
                data = {"id": existing_labels[name]["id"]}

                try:
                    await client.request(_MUTATE_LABEL_DELETE, input=data)
                except graphql.client.ClientResponseError as e:
                    print_error(f"The request to delete label '{name}' failed.", e)
                    error_n += 1

                    if error_n == 10:
                        print_error("Reached error limit. Exiting early.")
                        return 1
                else:
                    delete_n += 1
                    print_debug(f"Deleted '{name}'.")

            print_info(f"Deleted {delete_n} labels.")
        else:
            print_info("Skipped delete flow.")

        update_n = 0
        skip_n = 0
        for name in existing_labels.keys() & requested_labels.keys():
            existing_data = existing_labels[name]
            requested_data = requested_labels[name]

            data = dict()

            for (key, value) in requested_data.items():
                if value != existing_data[key]:
                    data[key] = value

            if data:
                data["id"] = existing_data["id"]

                try:
                    await client.request(_MUTATE_LABEL_UPDATE, input=data)
                except graphql.client.ClientResponseError as e:
                    print_error(f"The request to update label '{name}' failed.", e)
                    error_n += 1

                    if error_n == 10:
                        print_error("Reached error limit. Exiting early.")
                        return 1
                else:
                    update_n += 1
                    print_debug(f"Updated '{name}'.")
            else:
                skip_n += 1

        print_info(f"Updated {update_n} labels.")

        create_n = 0
        for name in requested_labels.keys() - existing_labels.keys():
            data = requested_labels[name]
            data["name"] = name
            data["repositoryId"] = repository_id

            try:
                await client.request(_MUTATE_LABEL_CREATE, input=data)
            except graphql.client.ClientResponseError as e:
                print_error(f"The request to create label '{name}' failed.", e)
                error_n += 1

                if error_n == 10:
                    print_error("Reached error limit. Exiting early.")
                    return 1
            else:
                create_n += 1
                print_debug(f"Created '{name}'.")

        print_info(f"Created {create_n} labels.")

        if error_n:
            print_error(f"There were {error_n} errors during the update flow.")
            return 1

    return 0


async def main_catchall(*args, **kwargs):
    try:
        code = await main(*args, **kwargs)
    except BaseException as e:
        print_error(e)
        code = 1
    finally:
        return code


if __name__ == "__main__":
    class HelpFormatter(argparse.HelpFormatter):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("max_help_position", 100)
            super().__init__(*args, **kwargs)

    parser = argparse.ArgumentParser(
        add_help=False,
        description="A Python script for synchronizing your GitHub repository labels with a labels.yml file.",
        epilog="See the documentation at <https://docs.shiney.dev/sync-labels-action>.",
        formatter_class=HelpFormatter,
    )

    class UsageAction(argparse._HelpAction):
        def __call__(self, parser, namespace, values, option_string=None):
            formatter = parser._get_formatter()
            usage = formatter._format_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups, prefix="")
            parser._print_message(usage, sys.stdout)
            parser.exit()

    parser.register("action", "usage", UsageAction)

    parser.add_argument("--help", action="help", help=argparse.SUPPRESS)
    parser.add_argument("--usage", action="usage", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", help=argparse.SUPPRESS, version=version)

    a = parser.add_argument("--partial", action="store_true")
    a.help = "Marks the source as partial, skipping the delete flow."

    a = parser.add_argument("--repository", metavar="OWNER/NAME", required=True)
    a.help = "A GitHub repository. (example: 'ShineyDev/sync-labels-action')"

    a = parser.add_argument("--source", metavar="PATH", required=True)
    a.help = "A path or a URL to the source file. (example: './.github/data/labels.yml')"

    a = parser.add_argument("--token", required=True)
    a.help = "A GitHub personal access token with the 'public_repo' scope."

    a = parser.add_argument("--verbosity", choices=range(0, 4 + 1), required=True, type=int)
    a.help = "A level of verbosity for output. 0 for none, error, warning, info, and 4 for debug."

    kwargs = vars(parser.parse_args())

    verbosity = kwargs.pop("verbosity")
    for printer in _printers:
        if verbosity >= printer.level:
            printer.is_active = True

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    exit(asyncio.run(main_catchall(**kwargs)))
