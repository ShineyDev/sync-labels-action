import argparse
import asyncio
import collections
import pathlib
import sys
import textwrap
import traceback

import aiohttp
import graphql


_VersionInfo = collections.namedtuple("_VersionInfo", "major minor micro release serial")

version = "0.0.0a"
version_info = _VersionInfo(0, 0, 0, "alpha", 0)


_printers = list()


def _create_printer(level, prefix, suffix, *, retval=None, stream=None):
    def printer(*args, **kwargs):
        if not printer.is_active:
            return retval

        if args and isinstance(args[-1], BaseException):
            *args, e = args
            args += ("See the error output below.",)
        else:
            e = None

        file = kwargs.pop("file", stream) or sys.stdout
        sep = kwargs.pop("sep", " ")

        s = prefix + sep.join(o if isinstance(o, str) else repr(o) for o in args) + suffix

        if e is not None:
            s += "\n\n" + textwrap.indent("".join(traceback.format_exception(type(e), e, e.__traceback__)), "    ")

        print(s, file=file, **kwargs)

        return retval

    printer.level = level
    printer.is_active = False

    _printers.append(printer)

    return printer


print_debug = _create_printer(4, "  \x1B[32m[DEBUG]\x1B[39m ", "", retval=0)
print_info = _create_printer(3, "   \x1B[34m[INFO]\x1B[39m ", "", retval=0)
print_warning = _create_printer(2, "\x1B[33m[WARNING]\x1B[39m ", "", retval=0)
print_error = _create_printer(1, "  \x1B[31m[ERROR] ", "\x1B[39m", retval=1, stream=sys.stderr)


# fmt: off
_QUERY_REPOSITORY_ID = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id}}"
_QUERY_REPOSITORY_LABELS_PAGE = "query($cursor:String,$repository_id:ID!){node(id:$repository_id){...on Repository{labels(after:$cursor,first:10){pageInfo{endCursor,hasNextPage}nodes{color,description,id,name}}}}}"
# fmt: on


async def main(*, repository, source, token):
    print_info(f"running ShineyDev/sync-labels-action v{version}")

    requested_labels = dict()  # TODO

    headers = {
        "Accept": "application/vnd.github.bane-preview+json",
        "Authorization": f"bearer {token}",
        "User-Agent": f"ShineyDev/sync-labels-action @ {repository}",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        client = graphql.client.Client(session=session, url="https://api.github.com/graphql")

        owner, name = repository.split("/")

        print_debug(f"REPOSITORY: '{owner}/{name}'")

        try:
            data = await client.request(_QUERY_REPOSITORY_ID, owner=owner, name=name)
        except graphql.client.ClientResponseError as e:
            return print_error("The request to fetch your repository's ID failed.", e)

        try:
            repository_id = data["repository"]["id"]
        except KeyError as e:
            return print_error("The repository you provided does not exist or the token you provided cannot see it.", e)

        print_debug(f"REPOSITORY ID: '{repository_id}'")

        existing_labels = dict()

        cursor = None
        has_next_page = True

        while has_next_page:
            try:
                data = await client.request(_QUERY_REPOSITORY_LABELS_PAGE, cursor=cursor, repository_id=repository_id)
            except graphql.client.ClientResponseError as e:
                return print_error("A request to fetch your repository's labels failed.", e)

            for label in data["node"]["labels"]["nodes"]:
                name = label.pop("name")
                existing_labels[name] = label

            cursor = data["node"]["labels"]["pageInfo"]["endCursor"]
            has_next_page = data["node"]["labels"]["pageInfo"]["hasNextPage"]

        print_debug(f"REPOSITORY LABELS: {existing_labels.keys()}")

        ...  # TODO: update labels

    return 0


async def main_catchall(*args, **kwargs):
    try:
        code = await main(*args, **kwargs)
    except BaseException as e:
        code = print_error(e)
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

    a = parser.add_argument("--repository", metavar="OWNER/NAME", required=True)
    a.help = "A GitHub repository. (example: 'ShineyDev/sync-labels-action')"

    a = parser.add_argument("--source", metavar="PATH", required=True, type=pathlib.Path)
    a.help = "A path to the source file. (example: './.github/data/labels.yml')"

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
