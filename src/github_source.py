import base64
import os

import requests


GITHUB_API_URL = "https://api.github.com"


def read_github_file(repository: str, path: str) -> dict:
    """Read a text file from a GitHub repository."""

    token = os.getenv("GITHUB_TOKEN")

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{GITHUB_API_URL}/repos/{repository}/contents/{path}"

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("type") != "file":
        raise ValueError(f"GitHub path is not a file: {path}")

    if data.get("encoding") != "base64":
        raise ValueError(
            f"Unsupported GitHub content encoding: {data.get('encoding')}"
        )

    content = base64.b64decode(data["content"]).decode("utf-8")

    return {
        "repository": repository,
        "path": data["path"],
        "sha": data["sha"],
        "url": data["html_url"],
        "content": content,
    }

def list_github_files(repository: str) -> list[dict]:
    """List files in a GitHub repository recursively."""

    token = os.getenv("GITHUB_TOKEN")

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Get repository metadata so we don't assume the default branch.
    repo_response = requests.get(
        f"{GITHUB_API_URL}/repos/{repository}",
        headers=headers,
        timeout=15,
    )
    repo_response.raise_for_status()

    default_branch = repo_response.json()["default_branch"]

    # Retrieve the repository tree recursively.
    tree_response = requests.get(
        f"{GITHUB_API_URL}/repos/{repository}/git/trees/{default_branch}",
        headers=headers,
        params={"recursive": "1"},
        timeout=15,
    )
    tree_response.raise_for_status()

    tree = tree_response.json().get("tree", [])

    return [
        {
            "path": item["path"],
            "sha": item["sha"],
        }
        for item in tree
        if item.get("type") == "blob"
    ]

def search_github_files(repository: str, query: str) -> list[dict]:
    """
    Find repository files whose paths contain the query.
    """

    files = list_github_files(repository)

    query_lower = query.lower()

    return [
        file
        for file in files
        if query_lower in file["path"].lower()
        and "/target/" not in file["path"]
    ]