import argparse
import asyncio
import collections
import colorsys
import re
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

version = "1.1.0"
version_info = _VersionInfo(1, 1, 0, "final", 0)


_printers = list()
_last_id = None
_last_suffix = None


def _create_printer(*, id=None, level=None, prefix=None, suffix=None, stream=None):
    def printer(*args, **kwargs):
        prefix_ = prefix
        suffix_ = suffix

        if not printer.is_active:
            return

        args = list(args)

        e = None
        if args and isinstance(args[-1], BaseException):
            *args, e = args
            args.append("See the error output below.")

        file = kwargs.pop("file", stream) or sys.stdout

        global _last_id
        global _last_suffix

        if id and _last_id == id:
            prefix_ = None
        elif _last_id:
            prefix_ = _last_suffix + ("\n" + prefix_ if prefix_ is not None else "\n")

        _last_id = None

        end = kwargs.pop("end", "\n")
        if not end.endswith("\n"):
            _last_id = id
            _last_suffix = suffix_
            suffix_ = None

        if prefix_:
            prefix_ = prefix_.format(id=id)

            if args:
                args[0] = prefix_ + (args[0] if isinstance(args[0], str) else repr(args[0]))
            else:
                args = [prefix_]

        if suffix_:
            suffix_ = suffix_.format(id=id)

            if args:
                args[-1] = (args[-1] if isinstance(args[-1], str) else repr(args[-1])) + suffix_
            else:
                args = [suffix_]

        if e is not None:
            args.append("\n\n" + textwrap.indent("".join(traceback.format_exception(type(e), e, e.__traceback__)), "    "))

        print(*args, end=end, file=file, **kwargs)

    printer.is_active = True
    if level is not None:
        printer.level = level
        printer.is_active = False

        _printers.append(printer)

    return printer


print_debug = _create_printer(id="DEBUG", level=4, prefix="  \x1B[32m[{id}]\x1B[39m ", suffix="")
print_info = _create_printer(id="INFO", level=3, prefix="   \x1B[34m[{id}]\x1B[39m ", suffix="")
print_warning = _create_printer(id="WARNING", level=2, prefix="\x1B[33m[{id}]\x1B[39m ", suffix="")
print_error = _create_printer(id="ERROR", level=1, prefix="  \x1B[31m[{id}] ", stream=sys.stderr, suffix="\x1B[39m")


# fmt: off
MUTATE_LABEL_CREATE = "mutation($input:CreateLabelInput!){createLabel(input:$input){__typename}}"
MUTATE_LABEL_DELETE = "mutation($input:DeleteLabelInput!){deleteLabel(input:$input){__typename}}"
MUTATE_LABEL_UPDATE = "mutation($input:UpdateLabelInput!){updateLabel(input:$input){__typename}}"
QUERY_REPOSITORY_ID = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id}}"
QUERY_REPOSITORY_LABELS_PAGE = "query($cursor:String,$repository_id:ID!){node(id:$repository_id){...on Repository{labels(after:$cursor,first:30){pageInfo{endCursor,hasNextPage}nodes{color,description,id,name}}}}}"
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

    print_info("Reading sources.")
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
                    group_name = group_data.get("name", None)
                    group_color = group_data.get("color", None)
                    group_description = group_data.get("description", None)
                    group_labels = group_data.get("labels", list())
                    if isinstance(group_labels, dict):
                        group_labels = [{"name": n, **d} for (n, d) in group_labels.items()]

                    existing_group = None
                    if group_name:
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
                                data = {
                                    "name": label_name,
                                    "color": label_color,
                                    "description": label_description,
                                }

                                existing_group["labels"].append(data)
                    else:
                        for label_data in group_labels:
                            label_data.setdefault("color", None)
                            label_data.setdefault("description", None)

                        data = {
                            "name": group_name,
                            "color": group_color,
                            "description": group_description,
                            "labels": group_labels,
                        }

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
                        data = {
                            "name": label_name,
                            "color": label_color,
                            "description": label_description,
                        }

                        labels.append(data)
    except (OSError, aiohttp.ClientResponseError, yaml.YAMLError) as e:
        print_error("The source you provided is not valid.", e)
        return 1

    def hsv_to_rgb(h, s, v):
        h /= 360
        s /= 100
        v /= 100

        r, g, b = colorsys.hsv_to_rgb(h, s, v)

        r = int(round(r * 255, 0))
        g = int(round(g * 255, 0))
        b = int(round(b * 255, 0))

        return (r, g, b)

    def rgb_to_hsv(r, g, b):
        r /= 255
        g /= 255
        b /= 255

        h, s, v = colorsys.rgb_to_hsv(r, g, b)

        h = int(h * 360)
        s = int(s * 100)
        v = int(v * 100)

        return (h, s, v)

    def get_color(color, palette):
        if isinstance(color, int):
            return color

        match = re.fullmatch("([a-z]+)((?:[+-][rgbhsv][0-9]+)*)", color, re.IGNORECASE)
        if not match:
            raise ValueError(f"The color value '{color}' is not valid.")

        base_string = match.group(1)
        offset_string = match.group(2)

        base_color = min(max(palette[base_string], 0), 0xFFFFFF)

        if not offset_string:
            return base_color

        offsets = re.findall("([+-])([rgbhsv])([0-9]+)", offset_string, re.IGNORECASE)
        for (operator, component, value) in offsets:
            if operator == "+":
                operator = int.__add__
            else:
                operator = int.__sub__

            component = component.lower()

            if component == "h":
                value_max = 359
            elif component in ("s", "v"):
                value_max = 100
            else:
                value_max = 255

            clamp = lambda v: min(max(v, 0), value_max)

            value = int(value)

            components = {
                "r": base_color >> 16 & 0xFF,
                "g": base_color >> 8 & 0xFF,
                "b": base_color & 0xFF,
            }

            if component in ("h", "s", "v"):
                h, s, v = rgb_to_hsv(components["r"], components["g"], components["b"])
                components.update({"h": h, "s": s, "v": v})

            components[component] = clamp(operator(components[component], value))

            if component in ("h", "s", "v"):
                r, g, b = hsv_to_rgb(components["h"], components["s"], components["v"])
                components.update({"r": r, "g": g, "b": b})

            base_color = components["r"] << 16 | components["g"] << 8 | components["b"]

        return base_color

    print_info("Populating colors.")

    while True:
        fails = 0
        passes = 0

        for (key, value) in colors.items():
            if isinstance(value, int):
                continue

            try:
                value = get_color(value, colors)
            except TypeError as e:
                fails += 1
            else:
                passes += 1
                colors[key] = value

        if not passes and fails:
            keys = [key for (key, value) in colors.items() if not isinstance(value, int)]
            print_error(f"The color keys {keys} are recursive.")
            return 1
        elif not fails:
            break

    default_color = defaults.get("color", None)
    if default_color:
        try:
            default_color = get_color(default_color, colors)
        except BaseException as e:
            print_error(f"The default color requests color '{default_color}' which is not valid", e)
            return 1

    default_description = defaults.get("description", None)

    print_info("Populating requested labels.")

    requested_labels = dict()

    for label_data in labels:
        label_name = label_data["name"]

        label_color = label_data["color"] or default_color

        if partial:
            pass
        elif label_color is None:
            print_error(f"The label '{label_name}' does not have a color and no default was provided.")
            return 1
        else:
            if isinstance(label_color, str):
                try:
                    label_color = get_color(label_color, colors)
                except BaseException as e:
                    print_error(f"The label '{label_name}' requests color '{label_color}' which is not valid.", e)
                    return 1

        label_description = label_data["description"] or default_description

        requested_labels[label_name] = {
            "color": f"{label_color:>06X}" if label_color else None,
            "description": label_description,
        }

    for group_data in groups:
        group_name = group_data["name"]
        group_color = group_data["color"]
        group_description = group_data["description"]
        group_labels = group_data["labels"]

        if group_name:
            group_prefix_length = 1
            group_prefix = group_name[:group_prefix_length]
            while any(g["name"].startswith(group_prefix) for g in groups if g["name"] and g["name"] != group_name and g["labels"]):
                group_prefix_length += 1
                group_prefix = group_name[:group_prefix_length]

                if group_prefix == group_name:
                    break
        else:
            group_prefix = None

        for label_data in group_labels:
            label_name = label_data["name"]

            label_color = label_data["color"] or group_color or default_color

            if partial:
                pass
            elif label_color is None:
                print_error(f"The label '{label_name}' in group '{group_name}' does not have a color and no default was provided.")
                return 1
            else:
                if isinstance(label_color, str):
                    try:
                        label_color = get_color(label_color, colors)
                    except BaseException as e:
                        print_error(f"The label '{label_name}' in group '{group_name}' requests color '{label_color}' which is not valid.", e)
                        return 1

            label_description = label_data["description"] or group_description or default_description

            if group_prefix:
                label_name = f"{group_prefix}:{label_name}"

            if label_name in requested_labels.keys():
                print_error(f"The group '{group_name}' defines label '{label_name}' which already exists.")
                return 1

            requested_labels[label_name] = {
                "color": f"{label_color:>06X}" if label_color else None,
                "description": label_description,
            }

    print_info("Authenticating to GitHub.")

    headers = {
        "Accept": "application/vnd.github.bane-preview+json",
        "Authorization": f"bearer {token}",
        "User-Agent": f"ShineyDev/sync-labels-action @ {repository}",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        client = graphql.client.Client(session=session, url="https://api.github.com/graphql")

        owner, name = repository.split("/")

        try:
            data = await client.request(QUERY_REPOSITORY_ID, owner=owner, name=name)
        except graphql.client.ClientResponseError as e:
            print_error("The request to fetch your repository identifier failed.", e)
            return 1

        try:
            repository_id = data["repository"]["id"]
        except KeyError as e:
            print_error("The repository you provided does not exist or the token you provided cannot see it.", e)
            return 1

        print_info("Populating existing labels.")

        existing_labels = dict()

        cursor = None
        has_next_page = True

        while has_next_page:
            try:
                data = await client.request(QUERY_REPOSITORY_LABELS_PAGE, cursor=cursor, repository_id=repository_id)
            except graphql.client.ClientResponseError as e:
                print_error("The request to fetch your repository labels failed.", e)
                return 1

            for label in data["node"]["labels"]["nodes"]:
                existing_labels[label.pop("name")] = label

            cursor = data["node"]["labels"]["pageInfo"]["endCursor"]
            has_next_page = data["node"]["labels"]["pageInfo"]["hasNextPage"]

        print_info("Updating labels.")

        if partial:
            print_info("Skipped delete flow.")
        else:
            delete_n = 0
            for name in existing_labels.keys() - requested_labels.keys():
                data = {"id": existing_labels[name]["id"]}

                try:
                    await client.request(MUTATE_LABEL_DELETE, input=data)
                except graphql.client.ClientResponseError as e:
                    print_error(f"The request to delete label '{name}' failed.", e)
                    return 1

                delete_n += 1
                print_debug(f"Deleted '{name}'.")

            print_info(f"Deleted {delete_n} labels.")

        update_n = 0
        skip_n = 0
        for name in existing_labels.keys() & requested_labels.keys():
            existing_data = existing_labels[name]
            requested_data = requested_labels[name]

            data = dict()

            for (key, value) in requested_data.items():
                if partial and value is None:
                    pass
                elif value != existing_data[key]:
                    data[key] = value

            if data:
                data["id"] = existing_data["id"]

                try:
                    await client.request(MUTATE_LABEL_UPDATE, input=data)
                except graphql.client.ClientResponseError as e:
                    print_error(f"The request to update label '{name}' failed.", e)
                    return 1

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
                await client.request(MUTATE_LABEL_CREATE, input=data)
            except graphql.client.ClientResponseError as e:
                print_error(f"The request to create label '{name}' failed.", e)
                return 1

            create_n += 1
            print_debug(f"Created '{name}'.")

        print_info(f"Created {create_n} labels.")

        if skip_n:
            print_info(f"Skipped {skip_n} labels.")

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
        description="A Python script for synchronizing your GitHub repository labels with a " "labels.yml file.",
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
    a.help = "Marks the source as partial."

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
