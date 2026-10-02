"""Slack conversational interface for My AI Brain.

Runs the existing My AI Brain multi-agent workflow behind a Slack bot
using Slack Socket Mode.

Slack is only the conversational interface here. The existing MCP,
retrieval, verifier, guardrails, and connected-source architecture
remain unchanged.
"""

import asyncio
import os
import re
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from src.agent import load_agent_harness
from src.llm import LocalLLM
from src.multi_agent import run_multi_agent


SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN:
    raise RuntimeError(
        "SLACK_BOT_TOKEN is not set. "
        "Export the bot token before starting the Slack bot."
    )

if not SLACK_APP_TOKEN:
    raise RuntimeError(
        "SLACK_APP_TOKEN is not set. "
        "Export the Socket Mode app token before starting the Slack bot."
    )


app = AsyncApp(token=SLACK_BOT_TOKEN)

# Keep short-term conversational memory per Slack thread.
#
# Key:
#   (channel_id, thread_timestamp)
#
# Value:
#   My AI Brain conversation_history
conversation_histories: dict[tuple[str, str], list[dict]] = {}

# These are initialized once when the process starts.
llm: LocalLLM | None = None
mcp_session: ClientSession | None = None


def clean_mention(text: str) -> str:
    """Remove Slack user/bot mention markup from a message."""

    text = re.sub(r"<@[A-Z0-9]+>", "", text)
    return text.strip()


def conversation_key(event: dict) -> tuple[str, str]:
    """Return a stable key for one Slack conversation/thread."""

    channel = event["channel"]

    # Replies remain associated with the original thread.
    thread_ts = event.get("thread_ts") or event["ts"]

    return channel, thread_ts


@app.event("app_mention")
async def handle_app_mention(event, say):
    """Send a Slack mention through the existing My AI Brain workflow."""

    global mcp_session
    global llm

    # Ignore bot-generated events if Slack includes them.
    if event.get("bot_id"):
        return

    question = clean_mention(event.get("text", ""))

    if not question:
        await say(
            text="Ask me a work question after mentioning me.",
            thread_ts=event["ts"],
        )
        return

    if mcp_session is None or llm is None:
        await say(
            text="My AI Brain is still starting up. Please try again shortly.",
            thread_ts=event["ts"],
        )
        return

    key = conversation_key(event)
    history = conversation_histories.get(key, [])

    print(
        f"[Slack] question from channel={event['channel']}: "
        f"{question}"
    )

    try:
        answer = await run_multi_agent(
            session=mcp_session,
            llm=llm,
            user_question=question,
            conversation_history=history,
        )

    except Exception as exc:
        print(f"[Slack] workflow failed: {exc}")

        await say(
            text=(
                "I couldn't complete that request because the agent "
                "workflow encountered an error."
            ),
            thread_ts=event.get("thread_ts") or event["ts"],
        )
        return

    history.append(
        {
            "role": "user",
            "content": question,
        }
    )

    history.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )

    # Match the terminal interface: approximately three exchanges.
    conversation_histories[key] = history[-6:]

    await say(
        text=answer,
        thread_ts=event.get("thread_ts") or event["ts"],
    )

    print("[Slack] response sent")


async def main():
    """Start MCP, the local LLM, and the Slack Socket Mode listener."""

    global mcp_session
    global llm

    # Same Module 4 harness validation used by the terminal interface.
    load_agent_harness()
    print("[Harness] AGENTS.md loaded")

    # Load the model once and reuse it across Slack requests.
    print("[Slack] loading My AI Brain...")
    llm = LocalLLM()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_session = session

            print("[MCP] connected")
            print("[Slack] My AI Brain is ready.")
            print("[Slack] Listening for @mentions...\n")

            handler = AsyncSocketModeHandler(
                app,
                SLACK_APP_TOKEN,
            )

            await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())