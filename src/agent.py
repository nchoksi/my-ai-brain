import asyncio
import json
import logging
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.llm import LocalLLM


logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)


def load_agent_harness() -> str:
    """
    Load the Agent Harness instructions from AGENTS.md.
    """
    harness_path = Path(__file__).resolve().parent.parent / "AGENTS.md"

    if not harness_path.exists():
        raise FileNotFoundError(
            f"Agent harness not found: {harness_path}"
        )

    return harness_path.read_text(encoding="utf-8")


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

    if tool_name and arguments is None:
        arguments = {}

    return tool_name, arguments


def extract_text_from_tool_result(result) -> str:
    """
    Extract text returned by an MCP tool.
    """
    return "\n".join(
        content.text
        for content in result.content
        if hasattr(content, "text")
    )


async def index_google_search_results(
    session: ClientSession,
    search_observation: str,
    project: str = "",
) -> str:
    """
    Automatically index documents returned by search_google_docs.

    If the Google search represents a known project, the project
    name can be stored as metadata. Otherwise the document is still
    indexed and remains available to semantic retrieval.
    """
    try:
        documents = json.loads(search_observation)
    except json.JSONDecodeError:
        return search_observation

    if not isinstance(documents, list) or not documents:
        return search_observation

    indexing_results = []

    for document in documents:
        document_id = document.get("id")

        if not document_id:
            continue

        document_name = document.get("name", "")
        modified_time = document.get("modifiedTime", "")

        print(f"[Controller] indexing Google Doc: {document_name}")

        try:
            result = await session.call_tool(
                "index_google_doc",
                arguments={
                    "document_id": document_id,
                    "project": project,
                    "document_name": document_name,
                    "modified_time": modified_time,
                },
            )

            indexing_observation = extract_text_from_tool_result(result)

            indexing_results.append(
                {
                    "document": document_name,
                    "project": project or None,
                    "result": indexing_observation,
                }
            )

        except Exception as exc:
            indexing_results.append(
                {
                    "document": document_name,
                    "project": project or None,
                    "result": f"Indexing failed: {exc}",
                }
            )

    return (
        f"Google Docs search results:\n"
        f"{search_observation}\n\n"
        f"The controller automatically indexed the discovered "
        f"documents into semantic memory:\n"
        f"{json.dumps(indexing_results, indent=2)}"
    )


async def build_system_prompt(session: ClientSession) -> str:
    """
    Discover MCP tools dynamically and build the system prompt.

    AGENTS.md defines the Module 4 Agent Harness and is loaded
    at runtime. MCP tools are discovered dynamically.
    """
    agent_harness = load_agent_harness()

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

Follow the Agent Harness below.

--- AGENT HARNESS ---

{agent_harness}

--- END AGENT HARNESS ---

You have access to tools through MCP.

AVAILABLE TOOLS:

{tools_text}

TOOL CALLING FORMAT:

When you need information from a tool, respond using exactly:

TOOL: <tool name>
ARGS: <valid JSON object>

For a tool that takes no arguments, use:

TOOL: <tool name>
ARGS: {{}}

You may call multiple tools sequentially when necessary.

SEMANTIC MEMORY WORKFLOW:

For questions about stored work information:

1. Search semantic memory first using search_memory.

2. Use semantic retrieval to find relevant information rather than
   assuming that a person, keyword, or topic is a project.

3. Use the project argument only when the user is clearly asking
   about a project and the project identity is known.

4. If the required information is not available in semantic memory,
   use an appropriate connected source such as Google Docs to
   discover the information.

5. search_google_docs searches document titles. Use a concise
   identifying keyword likely to appear in the document title.

6. Documents returned by search_google_docs are automatically
   indexed into semantic memory by the controller.

7. After new information is indexed, search semantic memory again
   before answering.

8. Answer using the retrieved evidence.

Use read_google_doc only when you specifically need the complete
contents of a document.

Use read_project_notes when the user's question is specifically
about local project notes.

Do not invent document IDs, project information, source metadata,
tool results, or facts that should come from a tool.

Do not treat a person's name as a project merely because the name
appears in the user's question.

If retrieved evidence is insufficient, say that you do not have
enough information.

When you have enough evidence, answer the original user question
normally.

Do not include TOOL or ARGS in the final answer.
""".strip()


async def run_agent(
    session: ClientSession,
    llm: LocalLLM,
    user_question: str,
    conversation_history: list,
) -> str:
    """
    Run one user turn through a bounded reasoning/tool loop.
    """
    system_prompt = await build_system_prompt(session)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Short-term conversational memory.
    messages.extend(conversation_history[-6:])

    messages.append(
        {
            "role": "user",
            "content": user_question,
        }
    )

    # Bounded loop prevents unlimited tool execution.
    for _ in range(6):
        response = llm.generate_messages(messages)

        tool_name, arguments = parse_tool_request(response)

        if tool_name:
            arguments = arguments or {}

            print(f"[Tool] {tool_name}")

            try:
                result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
                )

                observation = extract_text_from_tool_result(result)

            except Exception as exc:
                observation = f"Tool execution failed: {exc}"

            # --------------------------------------------------
            # Controller-managed source discovery
            # --------------------------------------------------

            if (
                tool_name == "search_memory"
                and (
                    observation.startswith("Semantic memory is empty")
                    or observation.startswith("No relevant information")
                    or observation.startswith("No information for project")
                )
            ):
                project = arguments.get("project", "")

                # ----------------------------------------------
                # Known project miss
                # ----------------------------------------------
                #
                # If the model explicitly supplied a project,
                # preserve that project through source discovery
                # and indexing.

                if project:
                    print(
                        f"[Controller] no memory for project '{project}', "
                        f"searching Google Docs"
                    )

                    try:
                        google_result = await session.call_tool(
                            "search_google_docs",
                            arguments={
                                "query": project,
                            },
                        )

                        google_observation = (
                            extract_text_from_tool_result(
                                google_result
                            )
                        )

                        google_observation = (
                            await index_google_search_results(
                                session=session,
                                search_observation=google_observation,
                                project=project,
                            )
                        )

                        observation = (
                            f"{observation}\n\n"
                            f"{google_observation}\n\n"
                            f"If documents were discovered, search "
                            f"semantic memory again before answering."
                        )

                    except Exception as exc:
                        observation = (
                            f"{observation}\n\n"
                            f"Automatic Google Docs discovery failed: "
                            f"{exc}"
                        )

                # ----------------------------------------------
                # Generic semantic-memory miss
                # ----------------------------------------------
                #
                # Do not guess that a person/topic is a project.
                # Give control back to the LLM so it can choose
                # an appropriate connected source and search term.

                else:
                    print(
                        "[Controller] semantic memory miss; "
                        "source discovery required"
                    )

                    messages.append(
                        {
                            "role": "assistant",
                            "content": response,
                        }
                    )

                    messages.append(
                        {
                            "role": "user",
                            "content": f"""
TOOL OBSERVATION:

{observation}

Semantic memory does not currently contain the information needed
for this question:

{user_question}

Use the connected source tools to discover the missing information.

For Google Docs, search_google_docs searches document titles, so
choose a concise identifying keyword from the user's question that
is likely to occur in the document title.

Do not treat a person's name as a project.

After finding a document, it will be indexed automatically.

Then search semantic memory again before answering the original
question.

Do not answer from assumptions or previous unrelated context.
""".strip(),
                        }
                    )

                    continue

            # --------------------------------------------------
            # Generic Google Docs discovery
            # --------------------------------------------------
            #
            # The LLM may search Google Docs for a person, topic,
            # document name, or another identifier.
            #
            # These documents are indexed without pretending that
            # the search keyword represents a project.

            elif (
                tool_name == "search_google_docs"
                and not observation.startswith(
                    "Tool execution failed:"
                )
            ):
                observation = await index_google_search_results(
                    session=session,
                    search_observation=observation,
                    project="",
                )

            # --------------------------------------------------
            # Feed completed tool observation back to the LLM
            # --------------------------------------------------

            messages.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": f"""
TOOL OBSERVATION:

{observation}

Original question:

{user_question}

Continue working on the original question.

Use retrieved evidence rather than assumptions.

If documents were just indexed into semantic memory, search
semantic memory again before answering.

If more information is required, call another appropriate tool.

If you have sufficient retrieved evidence, provide the final
answer normally.

Do not output TOOL or ARGS unless you actually want another
tool call.
""".strip(),
                }
            )

            continue

        if response.startswith("FINAL:"):
            return response.removeprefix("FINAL:").strip()

        return response.strip()

    return (
        "I could not complete the request within the allowed "
        "number of tool steps."
    )


async def main():
    # Fail early if the Module 4 Agent Harness is unavailable.
    load_agent_harness()

    print("[Harness] AGENTS.md loaded")

    llm = LocalLLM()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
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

                # Keep approximately the last three exchanges.
                conversation_history = conversation_history[-6:]


if __name__ == "__main__":
    asyncio.run(main())