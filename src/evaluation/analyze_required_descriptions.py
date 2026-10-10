import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.keyword_retriever import load_tools


PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"


def main():
    tools = load_tools()

    descriptions = []

    for tool in tools:
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))

        for property_name, property_schema in properties.items():
            if property_name not in required_fields:
                continue

            description = property_schema.get("description")

            if not description:
                continue

            descriptions.append({
                "tool_name": tool.get("name", "unknown"),
                "property_name": property_name,
                "description": description,
                "type": property_schema.get("type"),
                "enum": property_schema.get("enum"),
            })

    # Keep the output deterministic for repeatable experiments.
    descriptions.sort(
        key=lambda item: (
            item["property_name"],
            item["tool_name"],
        )
    )

    print(f"Tools inspected: {len(tools)}")
    print(f"Required-property descriptions: {len(descriptions)}")

    print("\nREQUIRED-PROPERTY DESCRIPTIONS")
    print("=" * 60)

    for index, item in enumerate(descriptions, start=1):
        print(
            f"\n{index}. Tool: {item['tool_name']}"
            f"\n   Property: {item['property_name']}"
            f"\n   Type: {item['type']}"
            f"\n   Description: {item['description']}"
        )

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    output_file = EXPERIMENTS_DIR / "required_property_descriptions.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(descriptions, file, indent=2, ensure_ascii=False)

    print(
        "\nSaved report: "
        f"{output_file.relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
