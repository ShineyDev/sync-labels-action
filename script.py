import argparse
import asyncio
import pathlib

import aiohttp
import graphql
import yaml
import yarl


_QUERY_REPOSITORY_ID = "query($owner: String!, $name: String!){ repository (owner: $owner, name: $name) { id } }"


async def main(*, path, repository, token):
    headers = {
        "Accept": "application/vnd.github.bane-preview+json",
        "Authorization": f"bearer {token}",
        "User-Agent": f"ShineyDev/sync-labels-action @ {repository}",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        client = graphql.client.Client(session=session, url="https://api.github.com/graphql")

        owner, name = repository.split("/")

        data = await client.request(_GQL_REPOSITORY_ID, owner=owner, name=name)
        repository_id = data["repository"]["id"]

        print(repository_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", required=True)
    kwargs = vars(parser.parse_args())

    asyncio.run(main(**kwargs))
