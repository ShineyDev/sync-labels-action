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


def _create_printer(level, prefix, suffix, *, stream=None):
    def printer(*args, **kwargs):
        if not printer.is_active:
            return

        if args and isinstance(args[-1], BaseException):
            *args, e = args
            args += ("See the error output below.",)
        else:
            e = None

        file = kwargs.pop("file", stream) or sys.stdout
        sep = kwargs.pop("sep", " ")

        s = prefix + sep.join(o if isinstance(o, str) else repr(o) for o in args) + suffix

        if e is not None:
            s += "\n\n" + textwrap.indent(
                "".join(traceback.format_exception(type(e), e, e.__traceback__)),
                "    ",
            )

        print(s, file=file, **kwargs)

    printer.level = level
    printer.is_active = False

    _printers.append(printer)

    return printer


print_debug = _create_printer(4, "  \x1B[32m[DEBUG]\x1B[39m ", "")
print_info = _create_printer(3, "   \x1B[34m[INFO]\x1B[39m ", "")
print_warning = _create_printer(2, "\x1B[33m[WARNING]\x1B[39m ", "")
print_error = _create_printer(1, "  \x1B[31m[ERROR] ", "\x1B[39m", stream=sys.stderr)


# fmt: off
_QUERY_REPOSITORY_ID = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id}}"
_QUERY_REPOSITORY_LABELS_PAGE = "query($cursor:String,$repository_id:ID!){node(id:$repository_id){...on Repository{labels(after:$cursor,first:10){pageInfo{endCursor,hasNextPage}nodes{color,description,id,name}}}}}"
# fmt: on


async def main(*, repository, source, token):
    print_info(f"running ShineyDev/sync-labels-action v{version}")

    ...  # TODO: generate a labels array

    headers = {
        "Accept": "application/vnd.github.bane-preview+json",
        "Authorization": f"bearer {token}",
        "User-Agent": f"ShineyDev/sync-labels-action @ {repository}",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        client = graphql.client.Client(session=session, url="https://api.github.com/graphql")

        try:
            owner, name = repository.split("/")
        except ValueError as e:
            print_error(
                f"That doesn't look like a GitHub repository! It should look similar to "
                f"'ShineyDev/sync-labels-action', not '{repository}'.",
                e,
            )

            return 1

        print_debug(f"REPOSITORY:        '{owner}/{name}'")

        try:
            data = await client.request(_QUERY_REPOSITORY_ID, owner=owner, name=name)
        except graphql.client.ClientResponseError as e:
            print_error("The request to fetch your repository's ID failed.", e)

            return 1

        try:
            repository_id = data["repository"]["id"]
        except KeyError as e:
            print_error(
                "The repository you provided does not exist or the token you provided cannot see "
                "it.",
                e,
            )

            return 1

        print_debug(f"REPOSITORY ID:     '{repository_id}'")

        existing_labels = list()

        cursor = None
        has_next_page = True

        while has_next_page:
            try:
                data = await client.request(
                    _QUERY_REPOSITORY_LABELS_PAGE,
                    cursor=cursor,
                    repository_id=repository_id,
                )
            except graphql.client.ClientResponseError as e:
                print_error("A request to fetch your repository's labels failed.", e)

                return 1

            existing_labels.extend(data["node"]["labels"]["nodes"])

            cursor = data["node"]["labels"]["pageInfo"]["endCursor"]
            has_next_page = data["node"]["labels"]["pageInfo"]["hasNextPage"]

        print_debug(f"REPOSITORY LABELS: {[l['name'] for l in existing_labels]}")

        ...  # TODO: update labels

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", metavar="OWNER/NAME", required=True)
    parser.add_argument("--source", metavar="PATH", required=True, type=pathlib.Path)
    parser.add_argument("--token", required=True)
    parser.add_argument("--verbosity", metavar="0-4", required=True, type=int)
    kwargs = vars(parser.parse_args())

    verbosity = kwargs.pop("verbosity")
    for printer in _printers:
        if verbosity >= printer.level:
            printer.is_active = True

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    exit(asyncio.run(main_catchall(**kwargs)))
