import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from llm import LocalLLM


SYSTEM_PROMPT = """
You are My AI Brain.

You have access to the tools listed below:

{tools}

If the user asks for information that requires one of these tools,
you MUST use the appropriate tool before answering.

To use a tool, output:

TOOL: <tool name>
PROJECT: <project name>

After receiving a TOOL OBSERVATION, answer using ONLY the retrieved evidence.

Then output:

FINAL: <answer>

Do not invent information.
""".strip()

def parse_tool_request(response: str):
    """
    Parse a tool request produced by the LLM.

    Expected format:
        TOOL: read_project_notes
        PROJECT: Atlas
    """
    tool_name = None
    project = None

    for line in response.splitlines():
        line = line.strip()

        if line.startswith("TOOL:"):
            tool_name = line.split(":", 1)[1].strip()

        elif line.startswith("PROJECT:"):
            project = line.split(":", 1)[1].strip()

    if tool_name and project:
        return tool_name, project

    return None

async def build_system_prompt(session: ClientSession) -> str:
    tools_result = await session.list_tools()

    tool_descriptions = []

    for tool in tools_result.tools:
        tool_descriptions.append(
            f"""
Tool: {tool.name}
Description: {tool.description}
Input schema: {tool.inputSchema}
""".strip()
        )

    tools_text = "\n\n".join(tool_descriptions)

    return SYSTEM_PROMPT.format(tools=tools_text)

async def run_agent(
    llm: LocalLLM,
    session: ClientSession,
    question: str,
    conversation_history: list[dict],
):
    system_prompt = await build_system_prompt(session)

    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history,
        {"role": "user", "content": question},
    ]

    # Keep the loop bounded so the agent cannot call tools forever.
    for _ in range(3):
        response = llm.generate_messages(messages)
        print(f"\n[DEBUG] LLM response:\n{response}\n")
        tool_request = parse_tool_request(response)

        if tool_request:
            tool_name, project = tool_request

            print(f"[Agent] Calling tool: {tool_name}({project})")

            result = await session.call_tool(
                tool_name,
                arguments={"project": project},
            )

            observation = "\n".join(
                content.text
                for content in result.content
                if hasattr(content, "text")
            )

            messages.append(
                {"role": "assistant", "content": response}
            )

            messages.append(
                {
                    "role": "user",
                    "content": f"""
TOOL OBSERVATION:
{observation}

Now answer the original user question using this evidence.
""".strip(),
                }
            )

            continue

        if response.startswith("FINAL:"):
            return response.removeprefix("FINAL:").strip()

        # The model did not follow the TOOL / FINAL protocol.
        # Ask it to retry instead of accepting the malformed response.
        messages.append(
            {"role": "assistant", "content": response}
        )

        messages.append(
            {
                "role": "user",
                "content": """
        Your previous response did not follow the required protocol.

        For project-specific questions, you MUST request the project tool.

        Respond only with one of these formats:

        TOOL: read_project_notes
        PROJECT: <project name>

        or

        FINAL: <answer>
        """.strip(),
            }
        )

        continue

    return "I culd not complete the request within the allowed tool steps."


async def main():
    llm = LocalLLM()
    conversation_history = []

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("\nMy AI Brain - Module 2")
            print("Type 'exit' to quit.\n")

            while True:
                question = input("You: ").strip()

                if not question:
                    continue

                if question.lower() == "exit":
                    break

                answer = await run_agent(
                    llm=llm,
                    session=session,
                    question=question,
                    conversation_history=conversation_history,
                )

                conversation_history.append(
                    {"role": "user", "content": question}
                )

                conversation_history.append(
                    {"role": "assistant", "content": answer}
                )
                conversation_history = conversation_history[-6:]

    print(f"\nMy AI Brain: {answer}\n")


if __name__ == "__main__":
    asyncio.run(main())