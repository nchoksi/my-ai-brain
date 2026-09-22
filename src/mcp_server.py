from pathlib import Path

from mcp.server.fastmcp import FastMCP
from google_docs import (
    read_google_doc as fetch_google_doc,
    search_google_docs as search_docs,
)
import logging

logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("mcp.server").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
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

@mcp.tool()
def read_google_doc(document_id: str) -> str:
    """
    Read the contents of a Google Doc.

    Args:
        document_id: The Google Docs document ID.
    """
    return fetch_google_doc(document_id)
    
@mcp.tool()
def search_google_docs(query: str) -> str:
    """
    Search Google Drive for Google Docs by document name.

    Args:
        query: Text to search for in Google Doc names,
            for example "Atlas".
    """
    return search_docs(query)

if __name__ == "__main__":
    mcp.run()