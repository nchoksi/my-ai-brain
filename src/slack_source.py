import os

import requests


SLACK_API_BASE_URL = "https://slack.com/api"


def _get_headers() -> dict:
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN is not set. Export the Slack bot token before starting My AI Brain."
        )
    return {"Authorization": f"Bearer {token}"}


def _call_slack_api(method: str, params: dict | None = None) -> dict:
    response = requests.get(
        f"{SLACK_API_BASE_URL}/{method}",
        headers=_get_headers(),
        params=params or {},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")
    return data


def list_slack_channels() -> list[dict]:
    data = _call_slack_api(
        "conversations.list",
        {"types": "public_channel", "limit": 200},
    )
    return [
        {"id": channel["id"], "name": channel["name"]}
        for channel in data.get("channels", [])
    ]


def search_slack_channels(query: str) -> list[dict]:
    query_lower = query.lower()
    return [
        channel for channel in list_slack_channels()
        if query_lower in channel["name"].lower()
    ]


def read_slack_channel(channel_id: str, limit: int = 100) -> dict:
    data = _call_slack_api(
        "conversations.history",
        {"channel": channel_id, "limit": limit},
    )
    messages = []
    for message in reversed(data.get("messages", [])):
        text = message.get("text", "").strip()
        if not text or message.get("subtype"):
            continue
        messages.append({
            "timestamp": message.get("ts"),
            "user": message.get("user"),
            "text": text,
        })
    return {"channel_id": channel_id, "messages": messages}
