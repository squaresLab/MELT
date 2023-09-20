import os.path
import sys
import requests
import pandas as pd
from requests.structures import CaseInsensitiveDict
import csv
import argparse

GITHUB_ACCESS_TOKEN = "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"


def find_deprecation_prs(repository_owner, repository_name, access_token, out_dir):
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = f"Bearer {access_token}"

    query_template = """
    {{
        search(query: "repo:{owner}/{name} is:pr DEP: in:title", type: ISSUE, first: 100, after: {after_cursor}) {{
            pageInfo {{
                endCursor
                hasNextPage
            }}
            nodes {{
                ... on PullRequest {{
                    number
                    title
                    url
                    bodyText
                }}
            }}
        }}
    }}
    """

    deprecation_prs = []
    has_next_page = True
    after_cursor = "null"

    while has_next_page:
        query = query_template.format(owner=repository_owner, name=repository_name, after_cursor=after_cursor)
        response = requests.post("https://api.github.com/graphql", headers=headers, json={"query": query})

        if response.status_code != 200:
            raise ValueError(f"Request failed with status code {response.status_code}")

        json_response = response.json()
        print(json_response)
        search_data = json_response["data"]["search"]

        for pr in search_data["nodes"]:
            if pr["title"].startswith("DEP"):
                deprecation_prs.append(pr)
                print(f"Found deprecation PR: {pr['title']} ({pr['url']})")

        has_next_page = search_data["pageInfo"]["hasNextPage"]
        after_cursor = f'"{search_data["pageInfo"]["endCursor"]}"' if has_next_page else "null"

    # Save the list of pull requests corresponding to deprecations to a CSV file using pandas
    pr_data = {
        "Title": [pr["title"] for pr in deprecation_prs],
        "URL": [pr["url"] for pr in deprecation_prs],
        "Number": [pr["number"] for pr in deprecation_prs],
    }

    df = pd.DataFrame(pr_data)
    df.to_csv(
        os.path.join(args.out_dir, f"deprecations_{repository_name}.csv"), index=False, quoting=csv.QUOTE_NONNUMERIC
    )
    print(f"Saved {len(deprecation_prs)} deprecation pull requests to prs.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=str, required=True)
    parser.add_argument("--out-dir", type=str, required=True)
    args = parser.parse_args()
    repo = args.repo
    repo_owner, repo_name = repo.split("/")

    find_deprecation_prs(repo_owner, repo_name, GITHUB_ACCESS_TOKEN, args.out_dir)
