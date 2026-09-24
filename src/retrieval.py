from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


class Retriever:
    def __init__(self):

        self.model = SentenceTransformer(EMBEDDING_MODEL)

        # In-memory vector database for our initial RAG implementation.
        #
        # Each item looks like:
        # {
        #     "text": "...",
        #     "metadata": {...},
        #     "embedding": tensor(...)
        # }
        self.vector_db = []

    def add_chunk(self, text: str, metadata: dict | None = None):
        """
        Convert a text chunk into an embedding and store it
        together with its metadata.
        """

        embedding = self.model.encode(
            text,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

        self.vector_db.append(
            {
                "text": text,
                "metadata": metadata or {},
                "embedding": embedding,
            }
        )

    def retrieve(self, query: str, top_k: int = 3):
        """
        Retrieve the chunks most semantically similar to the query.
        """

        query_embedding = self.model.encode(
            query,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

        results = []

        for item in self.vector_db:
            # Because both embeddings are normalized,
            # dot product is equivalent to cosine similarity.
            similarity = torch.dot(
                query_embedding,
                item["embedding"],
            ).item()

            results.append(
                {
                    "text": item["text"],
                    "metadata": item["metadata"],
                    "score": similarity,
                }
            )

        # Highest similarity first.
        results.sort(
            key=lambda result: result["score"],
            reverse=True,
        )

        return results[:top_k]

    def chunk_text(self, text: str, max_chars: int = 250):
        """
        Split text into reasonably sized semantic chunks.

        Short paragraphs are grouped together until the chunk
        approaches max_chars. Document title metadata is excluded.
        """

        paragraphs = [
            paragraph.strip()
            for paragraph in text.split("\n\n")
            if paragraph.strip()
        ]

        # Remove document metadata/title lines from searchable content.
        paragraphs = [
            paragraph
            for paragraph in paragraphs
            if not paragraph.lower().startswith("document:")
        ]

        chunks = []
        current_chunk = []

        for paragraph in paragraphs:
            candidate = "\n\n".join(current_chunk + [paragraph])

            if current_chunk and len(candidate) > max_chars:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [paragraph]
            else:
                current_chunk.append(paragraph)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def index_text(
        self,
        text: str,
        metadata: dict | None = None,
    ):
        """
        Chunk and index text from any source.

        The source could be a local file, Google Doc,
        Slack message, or another external system.
        """

        chunks = self.chunk_text(text)

        for chunk in chunks:
            self.add_chunk(
                text=chunk,
                metadata=metadata,
            )

        return len(chunks)

    def index_file(self, file_path: str):
        """
        Read a local project notes file and index it.
        """

        path = Path(file_path)
        text = path.read_text(encoding="utf-8")

        sections = self.chunk_text(text)

        project = None

        if sections and sections[0].lower().startswith("project:"):
            project = sections[0].split(":", 1)[1].strip()

            # Remove the project header from the knowledge
            # that will actually be embedded.
            text = "\n\n".join(sections[1:])

        metadata = {
            "project": project,
            "source": path.name,
            "source_type": "local_file",
        }

        return self.index_text(
            text=text,
            metadata=metadata,
        )