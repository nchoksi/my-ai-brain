from src.google_docs import read_google_doc
from src.llm import LocalLLM
from src.retrieval import Retriever


class RAG:
    def __init__(self):
        self.retriever = Retriever()
        self.llm = LocalLLM()

    def index_file(self, file_path: str):
        return self.retriever.index_file(file_path)

    def index_google_doc(
        self,
        document_id: str,
        project: str | None = None,
        document_name: str | None = None,
        modified_time: str | None = None,
    ):
        text = read_google_doc(document_id)

        metadata = {
            "project": project,
            "source": document_name or document_id,
            "document_id": document_id,
            "source_type": "google_doc",
            "modified_time": modified_time,
        }

        return self.retriever.index_text(
            text=text,
            metadata=metadata,
        )

    def answer(self, question: str, top_k: int = 3):
        results = self.retriever.retrieve(
            question,
            top_k=top_k,
        )

        if not results:
            return "I don't have enough information to answer that question."

        context_parts = []

        for result in results:
            metadata = result["metadata"]

            context_parts.append(
                f"""
Source: {metadata.get("source", "unknown")}
Project: {metadata.get("project", "unknown")}
Modified: {metadata.get("modified_time", "unknown")}

{result["text"]}
""".strip()
            )

        context = "\n\n---\n\n".join(context_parts)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are My AI Brain, a work assistant. "
                    "Answer the user's question using only the retrieved "
                    "project context provided to you. "
                    "Do not invent project facts. "
                    "If the retrieved context does not contain enough "
                    "information, say that you do not have enough information."
                ),
            },
            {
                "role": "user",
                "content": f"""
Retrieved project context:

{context}

Question:
{question}
""".strip(),
            },
        ]

        return self.llm.generate_messages(messages)