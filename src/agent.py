import asyncio
import json
import sys
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from llm import LocalLLM

logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

def parse_tool_request(response: str):
    """
    Parse a tool request from the LLM.

    Expected format:

    TOOL: <tool name>
    ARGS: <valid JSON object>
    """
    tool_name = None
    arguments = None

    for line in response.splitlines():
        line = line.strip()

        if line.startswith("TOOL:"):
            tool_name = line[len("TOOL:"):].strip()

        elif line.startswith("ARGS:"):
            args_text = line[len("ARGS:"):].strip()

            try:
                arguments = json.loads(args_text)
            except json.JSONDecodeError:
                return None, None

    return tool_name, arguments


async def build_system_prompt(session: ClientSession) -> str:
    """
    Discover the tools exposed by the MCP server and build
    a system prompt describing them to the model.
    """
    tools_result = await session.list_tools()

    tool_descriptions = []

    for tool in tools_result.tools:
        tool_descriptions.append(
            f"""
Tool name: {tool.name}
Description: {tool.description}
Input schema: {json.dumps(tool.inputSchema)}
""".strip()
        )

    tools_text = "\n\n".join(tool_descriptions)

    return f"""
You are My AI Brain, a work assistant that helps users retrieve
and reason over their work information.

You have access to tools through MCP.

AVAILABLE TOOLS:

{tools_text}

When you need information from a tool, respond using exactly:

TOOL: <tool name>
ARGS: <valid JSON object>

Use the tool descriptions and input schemas above to determine
the correct arguments.

You may call multiple tools when needed.

For example, if the user asks about information in Google Docs
but does not provide a document ID:

1. Search for the relevant Google Doc.
2. Read the relevant document using the document ID returned
   by the search.
3. Answer using the retrieved document contents.

Do not invent tool results, document IDs, project information,
or other facts that should come from a tool.

When you have enough information to answer the user's question,
respond normally with the answer.

Do not include TOOL or ARGS unless you actually want to call a tool.
""".strip()


async def run_agent(
    session: ClientSession,
    llm: LocalLLM,
    user_question: str,
    conversation_history: list,
) -> str:
    """
    Run one user turn.

    The model can either:
      1. request an MCP tool, or
      2. return a normal answer.

    Tool observations are fed back to the model so it can
    continue reasoning and optionally call another tool.
    """
    system_prompt = await build_system_prompt(session)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Short-term memory:
    # include only the most recent conversation messages.
    messages.extend(conversation_history[-6:])

    messages.append(
        {
            "role": "user",
            "content": user_question,
        }
    )

    # Keep the loop bounded so the agent cannot call tools forever.
    for _ in range(5):
        response = llm.generate_messages(messages)

        tool_name, arguments = parse_tool_request(response)

        # If the model requested a tool, execute it through MCP.
        if tool_name and arguments is not None:
            print(f"[Tool] {tool_name}")

            result = await session.call_tool(
                tool_name,
                arguments=arguments,
            )

            observation = "\n".join(
                content.text
                for content in result.content
                if hasattr(content, "text")
            )

            # Preserve the model's tool request in the working context.
            messages.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            # Feed the tool result back to the model.
            messages.append(
                {
                    "role": "user",
                    "content": f"""
TOOL OBSERVATION:
{observation}

Continue answering the original user question.
Use another tool if necessary.
Otherwise, provide the final answer.
""".strip(),
                }
            )

            continue

        # No valid tool request means the model is done.
        # Support FINAL: if the model happens to use it,
        # but do not require it.
        if response.startswith("FINAL:"):
            return response.removeprefix("FINAL:").strip()

        return response.strip()

    return "I could not complete the request within the allowed tool steps."


async def main():
    llm = LocalLLM()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/mcp_server.py"],
    )

    conversation_history = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("My AI Brain is ready.")
            print("Type 'exit' or 'quit' to stop.\n")

            while True:
                user_question = input("You: ").strip()

                if user_question.lower() in {"exit", "quit"}:
                    break

                if not user_question:
                    continue

                answer = await run_agent(
                    session=session,
                    llm=llm,
                    user_question=user_question,
                    conversation_history=conversation_history,
                )

                print(f"\nMy AI Brain: {answer}\n")

                # Store this interaction in short-term memory.
                conversation_history.append(
                    {
                        "role": "user",
                        "content": user_question,
                    }
                )

                conversation_history.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

                # Keep short-term memory bounded.
                conversation_history = conversation_history[-6:]


if __name__ == "__main__":
    asyncio.run(main())