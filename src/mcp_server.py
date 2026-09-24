import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.google_docs import (
    read_google_doc as google_read_document,
    search_google_docs as google_search_documents,
)
from src.retrieval import Retriever


mcp = FastMCP("my-ai-brain")

# -------------------------------------------------------------------
# Semantic memory
# -------------------------------------------------------------------

retriever = Retriever()
indexed_google_docs = set()


def format_search_results(results):
    """
    Convert semantic retrieval results into a clean structure
    that can be returned through MCP.
    """

    formatted_results = []

    for result in results:
        formatted_results.append(
            {
                "text": result["text"],
                "score": round(result["score"], 4),
                "metadata": result["metadata"],
            }
        )

    return formatted_results


# -------------------------------------------------------------------
# Existing Module 2 tools
# -------------------------------------------------------------------

@mcp.tool()
def read_project_notes() -> str:
    """
    Read the local Project Atlas notes.
    """

    path = Path("data/project_atlas.txt")

    if not path.exists():
        return "Project notes were not found."

    return path.read_text(encoding="utf-8")


@mcp.tool()
def search_google_docs(query: str) -> str:
    """
    Search Google Drive for Google Docs whose names match the query.
    """

    documents = google_search_documents(query)

    if not documents:
        return "No matching Google Docs found."

    return json.dumps(
        documents,
        indent=2,
    )


@mcp.tool()
def read_google_doc(document_id: str) -> str:
    """
    Read the text content of a Google Doc.
    """

    return google_read_document(document_id)


# -------------------------------------------------------------------
# Module 3 tools
# -------------------------------------------------------------------

@mcp.tool()
def index_google_doc(
    document_id: str,
    project: str = "",
    document_name: str = "",
    modified_time: str = "",
) -> str:
    """
    Add a Google Doc to semantic memory.

    The document is chunked, embedded, and stored in the
    in-memory vector store.
    """

    if document_id in indexed_google_docs:
        return "Document is already indexed in semantic memory."

    text = google_read_document(document_id)

    metadata = {
        "project": project or None,
        "source": document_name or document_id,
        "document_id": document_id,
        "source_type": "google_doc",
        "modified_time": modified_time or None,
    }

    count = retriever.index_text(
        text=text,
        metadata=metadata,
    )

    indexed_google_docs.add(document_id)

    return (
        f"Indexed {count} chunks from "
        f"{document_name or document_id} into semantic memory."
    )


@mcp.tool()
def search_memory(
    query: str,
    top_k: int = 3,
    project: str = "",
) -> str:
    """
    Search semantic memory for relevant chunks.

    Optionally filter retrieval to a specific project before
    semantic similarity ranking.
    """

    if not retriever.vector_db:
        return "Semantic memory is empty. Index a document first."

    results = retriever.retrieve(
        query=query,
        top_k=top_k,
        project=project or None,
    )

    if not results:
        if project:
            return (
                f"No information for project '{project}' "
                f"was found in semantic memory."
            )

        return "No relevant information was found in semantic memory."

    return json.dumps(
        format_search_results(results),
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")