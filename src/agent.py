import asyncio
import json
import logging
import os
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
        f"{json.dumps(indexing_results, indent=2)}\n\n"
        f"Search semantic memory again before answering."
    )


async def index_github_search_results(
    session: ClientSession,
    search_observation: str,
    repository: str,
    project: str = "",
) -> str:
    """
    Automatically index files returned by search_github_files.

    GitHub search discovers candidate source files. The controller
    indexes those files into semantic memory so the agent can
    retrieve their contents semantically on the next step.
    """

    try:
        files = json.loads(search_observation)
    except json.JSONDecodeError:
        return search_observation

    if not isinstance(files, list) or not files:
        return search_observation

    indexing_results = []

    for file in files:
        path = file.get("path")

        if not path:
            continue

        print(f"[Controller] indexing GitHub file: {path}")

        try:
            result = await session.call_tool(
                "index_github_file",
                arguments={
                    "repository": repository,
                    "path": path,
                    "project": project,
                },
            )

            indexing_observation = extract_text_from_tool_result(result)

            indexing_results.append(
                {
                    "repository": repository,
                    "path": path,
                    "project": project or None,
                    "result": indexing_observation,
                }
            )

        except Exception as exc:
            indexing_results.append(
                {
                    "repository": repository,
                    "path": path,
                    "project": project or None,
                    "result": f"Indexing failed: {exc}",
                }
            )

    return (
        f"GitHub search results:\n"
        f"{search_observation}\n\n"
        f"The controller automatically indexed the discovered "
        f"GitHub files into semantic memory:\n"
        f"{json.dumps(indexing_results, indent=2)}\n\n"
        f"Search semantic memory again before answering."
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
   choose the appropriate connected source based on the information
   needed.

5. Use Google Docs for project notes, meeting notes, architecture
   documents, decisions, and other written documentation.

6. Use GitHub for source code, implementation details, classes,
   methods, tests, repository structure, and questions about how
   software behaves.

7. Google Docs discovery searches document titles. Use a concise
   identifying keyword likely to occur in the title.

   Documents returned by search_google_docs are automatically
   indexed into semantic memory by the controller.

8. GitHub discovery searches file paths and file names, not the
   contents of source-code files.

   When calling search_github_files, use a concise file, class, or
   topic identifier likely to occur in a path.

   For example, for a question about how jokes are fetched, search
   for "Joke" or "RandomJokes" rather than phrases such as
   "fetch parse".

   Use the repository mapping in the Agent Harness. Do not invent
   repository names or file paths.

   Files returned by search_github_files are automatically indexed
   into semantic memory by the controller.

9. After new information from any source is indexed, search semantic
   memory again before answering.

10. Answer using the retrieved evidence.

Use read_google_doc only when you specifically need the complete
contents of a document.

Use read_github_file only when you specifically need the complete
contents of a source file.

Use read_project_notes when the user's question is specifically
about local project notes.

Do not invent document IDs, repository paths, project information,
source metadata, tool results, or facts that should come from a tool.

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
            # Semantic-memory miss
            # --------------------------------------------------
            #
            # A memory miss does not determine which external
            # source contains the answer. Give control back to
            # the LLM so it can select Google Docs, GitHub, or
            # another connected source based on the question.

            if (
                tool_name == "search_memory"
                and (
                    observation.startswith("Semantic memory is empty")
                    or observation.startswith("No relevant information")
                    or observation.startswith("No information for project")
                )
            ):
                project = arguments.get("project", "")

                if project:
                    print(
                        f"[Controller] no memory for project '{project}'; "
                        "source discovery required"
                    )
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

Choose the source based on the information needed:

- Use Google Docs for project notes, meeting notes, architecture
  documents, decisions, and other written documentation.

- Use GitHub for source code, implementation details, classes,
  methods, tests, repository structure, and questions about how
  software behaves.

For Google Docs, search_google_docs searches document titles.
Use a concise identifying keyword likely to occur in the title.

For GitHub, search_github_files searches file paths and file names,
not source-code contents.

Use a concise file, class, or topic identifier likely to occur in a
file path. For example, use "Joke" or "RandomJokes" rather than
"fetch parse" when searching the jokesAPI repository.

Use the repository mapping from the Agent Harness. Do not invent
repository names or file paths.

Search results from Google Docs and GitHub will be automatically
indexed into semantic memory by the controller.

After relevant information is indexed, search semantic memory again
before answering.

Do not answer from assumptions or unrelated conversational context.
""".strip(),
                    }
                )

                continue

            # --------------------------------------------------
            # Google Docs discovery
            # --------------------------------------------------
            #
            # Google search results are automatically indexed so
            # the LLM does not need to orchestrate the mechanical
            # indexing step.

            elif (
                tool_name == "search_google_docs"
                and not observation.startswith(
                    "Tool execution failed:"
                )
            ):
                project = arguments.get("project", "")

                observation = await index_google_search_results(
                    session=session,
                    search_observation=observation,
                    project=project,
                )

            # --------------------------------------------------
            # GitHub discovery
            # --------------------------------------------------
            #
            # GitHub path-search results are automatically indexed
            # into the same semantic memory used by other sources.

            elif (
                tool_name == "search_github_files"
                and not observation.startswith(
                    "Tool execution failed:"
                )
            ):
                repository = arguments.get("repository", "")

                if repository:
                    project = repository.split("/")[-1]

                    observation = await index_github_search_results(
                        session=session,
                        search_observation=observation,
                        repository=repository,
                        project=project,
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

If information was just indexed into semantic memory, search
semantic memory again before answering.

If more information is required, call another appropriate tool.

If you have sufficient retrieved evidence, provide the final
answer normally.

Do not merely describe a tool call you intend to make. If another
tool is required, actually issue the TOOL and ARGS request.

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
        env=os.environ.copy(),
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