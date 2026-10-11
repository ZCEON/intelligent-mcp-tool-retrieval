import copy
import json
from pathlib import Path

import tiktoken

from src.compression.schema_compressor_v2 import compress_schema_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]

TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"

OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v3_results.json"
)

ENCODING_NAME = "cl100k_base"


def load_tools():
    with TOOLS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("tools")

    if not isinstance(data, list):
        raise ValueError(
            "Expected tools.json to contain a list of tools."
        )

    return data


def count_tokens(value, encoding):
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(encoding.encode(serialized))


def strip_descriptions(value):
    if isinstance(value, dict):
        return {
            key: strip_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }

    if isinstance(value, list):
        return [strip_descriptions(item) for item in value]

    return value


def collect_description_changes(original, compressed):
    changes = []

    original_properties = (
        original.get("inputSchema", {}).get("properties", {})
    )
    compressed_properties = (
        compressed.get("inputSchema", {}).get("properties", {})
    )

    for property_name, original_schema in original_properties.items():
        compressed_schema = compressed_properties[property_name]

        original_description = original_schema.get("description")
        compressed_description = compressed_schema.get("description")

        if original_description == compressed_description:
            continue

        if compressed_description is None:
            transformation = "removed"
        else:
            transformation = "shortened_or_changed"

        changes.append(
            {
                "tool_name": original.get("name"),
                "property_name": property_name,
                "transformation": transformation,
                "original_description": original_description,
                "compressed_description": compressed_description,
                "required": property_name
                in original.get("inputSchema", {}).get("required", []),
            }
        )

    return changes


def main():
    tools = load_tools()
    encoding = tiktoken.get_encoding(ENCODING_NAME)

    original_token_total = 0
    compressed_token_total = 0

    structural_checks_passed = 0
    structural_checks_failed = []

    all_changes = []
    compressed_tools = []

    for tool in tools:
        compressed = compress_schema_v2(tool)

        original_token_total += count_tokens(tool, encoding)
        compressed_token_total += count_tokens(compressed, encoding)

        if strip_descriptions(tool) == strip_descriptions(compressed):
            structural_checks_passed += 1
        else:
            structural_checks_failed.append(tool.get("name"))

        all_changes.extend(
            collect_description_changes(tool, compressed)
        )
        compressed_tools.append(compressed)

    tokens_saved = original_token_total - compressed_token_total

    reduction_percentage = (
        tokens_saved / original_token_total * 100
        if original_token_total
        else 0.0
    )

    transformation_counts = {
        "removed": sum(
            change["transformation"] == "removed"
            for change in all_changes
        ),
        "shortened_or_changed": sum(
            change["transformation"] == "shortened_or_changed"
            for change in all_changes
        ),
    }

    report = {
        "experiment": "revised_schema_compression_v3",
        "dataset": "data/tools/tools.json",
        "tool_count": len(tools),
        "encoding": ENCODING_NAME,
        "serialization": "compact JSON; ensure_ascii=False",
        "original_tokens": original_token_total,
        "compressed_tokens": compressed_token_total,
        "tokens_saved": tokens_saved,
        "reduction_percentage": round(reduction_percentage, 4),
        "transformation_counts": transformation_counts,
        "total_description_changes": len(all_changes),
        "structural_checks_passed": structural_checks_passed,
        "structural_checks_failed": structural_checks_failed,
        "all_structural_checks_passed": (
            len(structural_checks_failed) == 0
            and structural_checks_passed == len(tools)
        ),
        "changes": all_changes,
        "limitations": [
            (
                "Token savings depend on the selected tokenizer and "
                "JSON serialization."
            ),
            (
                "Structural equality after ignoring descriptions does "
                "not prove semantic equivalence."
            ),
            (
                "This evaluation measures schema token savings, not "
                "successful tool execution."
            ),
        ],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("Revised Schema Compression Evaluation")
    print("=" * 43)
    print(f"Tools evaluated: {len(tools)}")
    print(f"Original tokens: {original_token_total}")
    print(f"Compressed tokens: {compressed_token_total}")
    print(f"Tokens saved: {tokens_saved}")
    print(f"Reduction: {reduction_percentage:.2f}%")
    print(f"Description changes: {len(all_changes)}")
    print(f"Transformation counts: {transformation_counts}")
    print(
        f"Structural checks passed: "
        f"{structural_checks_passed}/{len(tools)}"
    )
    print(
        f"Structural checks failed: "
        f"{len(structural_checks_failed)}"
    )
    print()
    print(f"Report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
