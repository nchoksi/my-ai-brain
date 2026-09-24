import asyncio
import json
import logging
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.llm import LocalLLM


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

    # Some models may omit ARGS for tools with no arguments.
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

    The search keyword is also stored as project metadata so that
    future retrieval can filter by project before semantic ranking.
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
                    "project": project,
                    "result": indexing_observation,
                }
            )

        except Exception as exc:
            indexing_results.append(
                {
                    "document": document_name,
                    "project": project,
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

TOOL CALLING FORMAT:

When you need information from a tool, respond using exactly:

TOOL: <tool name>
ARGS: <valid JSON object>

For a tool that takes no arguments, use:

TOOL: <tool name>
ARGS: {{}}

You may call multiple tools sequentially when necessary.

SEMANTIC MEMORY WORKFLOW:

For questions about work information:

1. Identify whether the user explicitly mentions a project, person,
   or other clear identifying topic.

2. Search semantic memory first using search_memory.

   If the user explicitly names a project, pass that project name
   using the project argument.

   Example:

   User: "What should I discuss with the architect about Atlas?"

   TOOL: search_memory
   ARGS: {{"query": "what should I discuss with the architect?", "project": "Atlas", "top_k": 3}}

3. If search_memory reports that no information exists for that
   project, the application controller may automatically search
   Google Docs and index matching documents.

4. search_google_docs searches DOCUMENT TITLES, not document
   contents. Use a short identifying keyword likely to appear
   in the document title.

   Examples:

   User: "What items are pending for Neil?"
   Google Docs search query: "Neil"

   User: "What architecture decisions were made for Atlas?"
   Google Docs search query: "Atlas"

   Do not send the entire user question to search_google_docs.

5. Documents returned by search_google_docs are automatically
   indexed into semantic memory by the application controller.

6. After a document is indexed, call search_memory again.

   If the document was discovered using a project identifier,
   use that same identifier as the project filter.

7. Answer using the evidence returned from semantic memory.

Use read_google_doc only when you specifically need the complete
contents of a document.

Use read_project_notes when the user's question is specifically
about the local project notes.

Do not invent document IDs, project information, source metadata,
tool results, or facts that should come from a tool.

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
            print(f"[Tool] {tool_name}")

            try:
                result = await session.call_tool(
                    tool_name,
                    arguments=arguments or {},
                )

                observation = extract_text_from_tool_result(result)

            except Exception as exc:
                observation = f"Tool execution failed: {exc}"

            # --------------------------------------------------
            # Controller-managed source discovery and ingestion
            # --------------------------------------------------

            # If semantic memory has no information for a named
            # project, automatically discover the corresponding
            # Google Doc and index it.
            if (
                tool_name == "search_memory"
                and (arguments or {}).get("project")
                and (
                    observation.startswith("Semantic memory is empty")
                    or observation.startswith("No information for project")
                )
            ):
                project = (arguments or {}).get("project")

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

                    google_observation = extract_text_from_tool_result(
                        google_result
                    )

                    google_observation = await index_google_search_results(
                        session=session,
                        search_observation=google_observation,
                        project=project,
                    )

                    observation = (
                        f"{observation}\n\n"
                        f"The controller searched Google Docs for project "
                        f"'{project}'.\n\n"
                        f"{google_observation}\n\n"
                        f"The discovered project documents are now indexed. "
                        f"Search semantic memory again using "
                        f"project='{project}'."
                    )

                except Exception as exc:
                    observation = (
                        f"{observation}\n\n"
                        f"Automatic Google Docs discovery failed: {exc}"
                    )

            # If the LLM explicitly searches Google Docs,
            # automatically index the discovered documents.
            elif (
                tool_name == "search_google_docs"
                and not observation.startswith("Tool execution failed:")
            ):
                observation = await index_google_search_results(
                    session=session,
                    search_observation=observation,
                    project=(arguments or {}).get("query", ""),
                )

            # --------------------------------------------------
            # Feed the completed tool/controller observation
            # back to the LLM.
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

If documents were just indexed into semantic memory, use
search_memory again before answering.

If the original question names a project, preserve that project
filter when searching semantic memory again.

If more information is required, call another appropriate tool.

If you have sufficient retrieved evidence, provide the final
answer normally.

Do not output TOOL or ARGS unless you actually want another
tool call.
""".strip(),
                }
            )

            continue

        # No tool request means the model considers the task complete.
        if response.startswith("FINAL:"):
            return response.removeprefix("FINAL:").strip()

        return response.strip()

    return (
        "I could not complete the request within the allowed "
        "number of tool steps."
    )


async def main():
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

                # Store interaction in short-term memory.
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