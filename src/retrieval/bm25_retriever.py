import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi


PROJECT_ROOT = Path(__file__).parent.parent.parent
TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"


def load_tools():
    """Load the MCP-style tools dataset."""

    with open(TOOLS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def tokenize(text):
    """Convert text into lowercase tokens."""

    return re.findall(r"\b[a-z0-9_]+\b", text.lower())


def get_tool_text(tool):
    """Build the searchable text for a tool."""

    return " ".join([
        tool["name"],
        tool["description"],
        tool["category"]
    ])


class BM25Retriever:
    """Retrieve relevant tools using BM25 ranking."""

    def __init__(self, tools):
        self.tools = tools

        # Convert every tool into a list of searchable tokens.
        tokenized_corpus = [
            tokenize(get_tool_text(tool))
            for tool in self.tools
        ]

        # Build the BM25 ranking model.
        self.bm25 = BM25Okapi(tokenized_corpus)

    def retrieve(self, query, top_k=5):
        """Return the top-k tools ranked by BM25."""

        query_tokens = tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Rank tool indices from highest to lowest BM25 score.
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True
        )[:top_k]

        results = []

        for index in ranked_indices:
            results.append({
                "tool": self.tools[index],
                "score": float(scores[index])
            })

        return results


if __name__ == "__main__":

    tools = load_tools()

    retriever = BM25Retriever(tools)

    query = "I want to refund order 12345"

    results = retriever.retrieve(
        query,
        top_k=5
    )

    print("\nBM25 Retrieval")
    print("==============")

    print(f"\nQuery: {query}")
    print(f"Total available tools: {len(tools)}")

    print("\nTop 5 tools:")

    for rank, result in enumerate(results, start=1):

        tool = result["tool"]
        score = result["score"]

        print(
            f"{rank}. {tool['name']} "
            f"(score={score:.4f})"
        )
