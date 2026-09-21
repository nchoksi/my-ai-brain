from pathlib import Path

from mcp.server.fastmcp import FastMCP


# Create the MCP server for My AI Brain.
mcp = FastMCP("my-ai-brain")


# Resolve the project data directory relative to this file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@mcp.tool()
def read_project_notes(project: str) -> str:
    """
    Read the notes for a project.

    Args:
        project: Name of the project to retrieve, for example "atlas".
    """
    project_name = project.strip().lower()
    project_file = DATA_DIR / f"project_{project_name}.txt"

    if not project_file.exists():
        return f"No notes found for project '{project}'."

    return project_file.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run()