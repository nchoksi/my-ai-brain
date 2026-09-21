import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    # Tell the MCP client how to start our MCP server.
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/mcp_server.py"],
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
            result = await session.call_tool(
                "read_project_notes",
                arguments={"project": "atlas"},
            )

            print("\nTool result:")
            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text)


if __name__ == "__main__":
    asyncio.run(main())