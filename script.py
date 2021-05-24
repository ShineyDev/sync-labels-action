import argparse
import asyncio

import aiohttp
import graphql
import yaml


_GQL_REPOSITORY_ID_FMT = "query{{repository(owner:\"{0}\",name:\"{1}\"){{id}}}}"


async def main(*, repository, token):
    headers = {
        "Accept": "application/vnd.github.bane-preview+json",
        "Authorization": f"bearer {token}",
        "User-Agent": "ShineyDev/sync-labels-action",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        client = graphql.client.Client(session=session, url="https://api.github.com/graphql")

        owner, name = repository.split("/")

        repository_id = await client.request(_GQL_REPOSITORY_ID_FMT.format(owner, name))

        print(repository_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, help="A GitHub repository name and owner.")
    parser.add_argument("--token", required=True, help="A GitHub PAT with the 'public_repo' scope.")
    kwargs = parser.parse_args()

    asyncio.run(main(**vars(kwargs)))
