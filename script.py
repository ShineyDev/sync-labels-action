import argparse
import asyncio
import sys

import aiohttp
import graphql
import yaml


print(sys.version_info)


_GQL_REPOSITORY_ID = "query($owner: String!, $name: String!){ repository (owner: $owner, name: $name) { id } }"


async def main(*, repository, token):
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
    parser.add_argument("--repository", required=True, help="A GitHub repository name and owner.")
    parser.add_argument("--token", required=True, help="A GitHub PAT with the 'public_repo' scope.")
    kwargs = parser.parse_args()

    asyncio.run(main(**vars(kwargs)))
