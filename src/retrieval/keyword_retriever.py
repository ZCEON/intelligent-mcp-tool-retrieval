import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent
TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"


def load_tools():
    with open(TOOLS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def tokenize(text):
    text = text.lower()
    words = re.findall(r"\b[a-z0-9_]+\b", text)
    return set(words)


def get_tool_text(tool):
    return " ".join([
        tool["name"],
        tool["description"],
        tool["category"]
    ])


def calculate_score(query, tool):
    query_words = tokenize(query)
    tool_words = tokenize(get_tool_text(tool))

    if not query_words:
        return 0.0

    matching_words = query_words.intersection(tool_words)

    score = len(matching_words) / len(query_words)

    return score


def retrieve_tools(query, tools, top_k=5):

    scored_tools = []

    for tool in tools:
        score = calculate_score(query, tool)

        scored_tools.append({
            "tool": tool,
            "score": score
        })

    scored_tools.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return scored_tools[:top_k]


if __name__ == "__main__":

    tools = load_tools()

    query = "I want to refund order 12345"

    results = retrieve_tools(
        query,
        tools,
        top_k=5
    )

    print("\nQuery:")
    print(query)

    print("\nTop 5 tools:")

    for rank, result in enumerate(results, start=1):

        tool = result["tool"]

        print(
            f"{rank}. {tool['name']} "
            f"(score={result['score']:.3f})"
        )
