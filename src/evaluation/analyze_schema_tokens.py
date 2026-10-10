import json
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.keyword_retriever import load_tools


PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"

ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(value):
    """Count tokens in a compact JSON representation."""
    text = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(ENCODING.encode(text))


def analyze_tools(tools):
    """Measure token usage for different schema components."""

    totals = {
        "tool_name": 0,
        "tool_description": 0,
        "category": 0,
        "property_names": 0,
        "property_descriptions": 0,
        "types_and_constraints": 0,
        "required_lists": 0,
        "other_schema_content": 0,
    }

    per_tool_results = []

    for tool in tools:
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        property_names = list(properties.keys())

        property_descriptions = [
            prop["description"]
            for prop in properties.values()
            if "description" in prop
        ]

        types_and_constraints = {}
        for name, prop in properties.items():
            constraints = {
                key: value
                for key, value in prop.items()
                if key not in ("description",)
            }
            types_and_constraints[name] = constraints

        # Remove measured components to estimate remaining schema content.
        other_schema_content = {
            key: value
            for key, value in schema.items()
            if key not in ("properties", "required")
        }

        component_counts = {
            "tool_name": count_tokens(tool.get("name", "")),
            "tool_description": count_tokens(tool.get("description", "")),
            "category": count_tokens(tool.get("category", "")),
            "property_names": count_tokens(property_names),
            "property_descriptions": count_tokens(property_descriptions),
            "types_and_constraints": count_tokens(types_and_constraints),
            "required_lists": count_tokens(required),
            "other_schema_content": count_tokens(other_schema_content),
        }

        for component, count in component_counts.items():
            totals[component] += count

        per_tool_results.append({
            "tool_name": tool.get("name", "unknown"),
            "component_tokens": component_counts,
            "full_tool_tokens": count_tokens(tool),
        })

    return totals, per_tool_results


def main():
    tools = load_tools()

    print(f"Loaded tools: {len(tools)}")

    totals, per_tool_results = analyze_tools(tools)

    print("\nSchema Component Token Analysis")
    print("===============================")

    for component, token_count in sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"{component}: {token_count} tokens")

    output = {
        "total_tools": len(tools),
        "tokenizer": "cl100k_base",
        "component_token_totals": totals,
        "per_tool_results": per_tool_results,
    }

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    output_file = EXPERIMENTS_DIR / "schema_token_analysis.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    print(f"\nSaved: {output_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
