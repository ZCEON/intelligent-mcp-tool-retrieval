import json
import re
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


PROJECT_ROOT = Path(__file__).parent.parent.parent
TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"

# A lightweight, widely used model for semantic similarity.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_tools():
    """Load MCP tools from the JSON dataset."""
    with open(TOOLS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def get_tool_text(tool):
    """Combine searchable tool information into one text string."""
    return (
        f"Tool name: {tool['name']}. "
        f"Description: {tool['description']}. "
        f"Category: {tool['category']}."
    )


class SemanticRetriever:
    """Retrieve tools by comparing semantic embeddings."""

    def __init__(self, tools, model_name=MODEL_NAME):
        self.tools = tools
        self.model = SentenceTransformer(model_name)

        # Create each tool embedding once.
        tool_texts = [get_tool_text(tool) for tool in self.tools]

        self.tool_embeddings = self.model.encode(
            tool_texts,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

    def retrieve(self, query, top_k=5):
        """Return the top-K tools ranked by cosine similarity."""

        if not query.strip():
            return []

        query_embedding = self.model.encode(
            query,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

        similarities = cos_sim(
            query_embedding,
            self.tool_embeddings,
        )[0]

        k = min(top_k, len(self.tools))

        scores, indices = similarities.topk(k=k)

        results = []

        for score, index in zip(scores, indices):
            tool_index = index.item()

            results.append({
                "tool": self.tools[tool_index],
                "score": float(score.item()),
            })

        return results


if __name__ == "__main__":
    tools = load_tools()

    print(f"Loaded tools: {len(tools)}")
    print(f"Loading model: {MODEL_NAME}")

    retriever = SemanticRetriever(tools)

    query = "I want to refund order 12345"
    results = retriever.retrieve(query, top_k=5)

    print("\nSemantic Retrieval")
    print("==================")
    print(f"Query: {query}")
    print("\nTop 5 tools:")

    for rank, result in enumerate(results, start=1):
        tool = result["tool"]
        score = result["score"]

        print(f"{rank}. {tool['name']} (similarity={score:.4f})")
