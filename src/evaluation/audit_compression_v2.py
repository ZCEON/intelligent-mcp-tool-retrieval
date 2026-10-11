import json
import sys
from pathlib import Path

import tiktoken


# Make the project root importable when this script is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.compression.schema_compressor_v2 import compress_schema_v2


TOOLS_PATH = PROJECT_ROOT / "data" / "tools" / "tools.json"
OUTPUT_PATH = (
    PROJECT_ROOT / "experiments" / "compression_v2_audit.json"
)

ENCODING = tiktoken.get_encoding("cl100k_base")


def load_tools():
    """Load the original tools without modifying the dataset."""
    with TOOLS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def count_tokens(text):
    """Count tokens in a text string using the project's tokenizer."""
    if not isinstance(text, str):
        return 0

    return len(ENCODING.encode(text))


def audit_compression(original_tools):
    """
    Compare original tools with their V2-compressed versions.

    Record every property description that changed.
    The original dataset is never modified.
    """
    audit_records = []

    for original_tool in original_tools:
        compressed_tool = compress_schema_v2(original_tool)

        tool_name = original_tool.get("name", "unknown_tool")

        original_schema = original_tool.get("inputSchema", {})
        compressed_schema = compressed_tool.get("inputSchema", {})

        original_properties = original_schema.get("properties", {})
        compressed_properties = compressed_schema.get("properties", {})

        required_fields = set(original_schema.get("required", []))

        for property_name, original_property in original_properties.items():
            compressed_property = compressed_properties.get(property_name)

            if not isinstance(compressed_property, dict):
                continue

            original_description = original_property.get("description")
            compressed_description = compressed_property.get("description")

            # Only record descriptions that actually changed.
            if original_description == compressed_description:
                continue

            original_tokens = count_tokens(original_description)
            compressed_tokens = count_tokens(compressed_description)

            audit_records.append(
                {
                    "tool_name": tool_name,
                    "property_name": property_name,
                    "is_required": property_name in required_fields,
                    "change_type": (
                        "description_removed"
                        if compressed_description is None
                        else "description_shortened_or_changed"
                    ),
                    "original_description": original_description,
                    "compressed_description": compressed_description,
                    "original_description_tokens": original_tokens,
                    "compressed_description_tokens": compressed_tokens,
                    "description_tokens_saved": (
                        original_tokens - compressed_tokens
                    ),
                }
            )

    return audit_records


def main():
    original_tools = load_tools()
    audit_records = audit_compression(original_tools)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(audit_records, file, indent=2, ensure_ascii=False)

    total_changes = len(audit_records)
    removed = sum(
        record["change_type"] == "description_removed"
        for record in audit_records
    )
    shortened = sum(
        record["change_type"] == "description_shortened_or_changed"
        for record in audit_records
    )

    total_description_tokens_saved = sum(
        record["description_tokens_saved"]
        for record in audit_records
    )

    print("\nSchema Compression V2 Audit")
    print("=" * 45)
    print(f"Original tools examined: {len(original_tools)}")
    print(f"Description changes found: {total_changes}")
    print(f"Descriptions removed: {removed}")
    print(f"Descriptions shortened or changed: {shortened}")
    print(
        "Net description-string tokens saved: "
        f"{total_description_tokens_saved}"
    )
    print(f"\nAudit report saved to:\n{OUTPUT_PATH}")

    print("\nFirst 10 changes")
    print("-" * 45)

    for record in audit_records[:10]:
        print(f"\nTool: {record['tool_name']}")
        print(f"Property: {record['property_name']}")
        print(f"Required: {record['is_required']}")
        print(f"Original: {record['original_description']}")
        print(f"Compressed: {record['compressed_description']}")
        print(
            "Description tokens saved: "
            f"{record['description_tokens_saved']}"
        )


if __name__ == "__main__":
    main()
