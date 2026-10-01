import asyncio
import sys
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    # Tell the MCP client how to start our MCP server.
    server_params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "src.mcp_server"],
    env=os.environ.copy(),
    )

    # Start the server and establish stdio communication.
    async with stdio_client(server_params) as (read, write):

        # Create an MCP session over that connection.
        async with ClientSession(read, write) as session:

            # MCP handshake.
            await session.initialize()

            # Ask the server which tools it exposes.
            tools = await session.list_tools()

            print("Available tools:")

            for tool in tools.tools:
                print(f"\nName: {tool.name}")
                print(f"Description: {tool.description}")
                print(f"Input schema: {tool.inputSchema}")

            # Invoke our first MCP tool.
            # Index the GitHub source file into semantic memory.
            index_result = await session.call_tool(
                "index_github_file",
                arguments={
                    "repository": "nchoksi/jokesAPI",
                    "path": "demo/src/main/java/com/example/jokes/RandomJokes.java",
                    "project": "jokesAPI",
                },
            )

            print("\nIndex result:")
            for content in index_result.content:
                if hasattr(content, "text"):
                    print(content.text)


            # Search the shared semantic memory.
            search_result = await session.call_tool(
                "search_memory",
                arguments={
                    "query": "How does the application fetch and parse jokes?",
                    "top_k": 3,
                    "project": "jokesAPI",
                },
            )

            print("\nMemory search result:")
            for content in search_result.content:
                if hasattr(content, "text"):
                    print(content.text)


if __name__ == "__main__":
    asyncio.run(main())