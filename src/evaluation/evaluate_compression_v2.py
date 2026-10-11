import copy
import json
import sys
from pathlib import Path

import tiktoken

# Allow imports from the project's src directory.

PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retrieval.keyword_retriever import load_tools
from compression.schema_compressor import compress_schema
from compression.schema_compressor_v2 import (
    compress_schema_v2,
    PRESERVED_OPTIONAL_DESCRIPTIONS,
)

ENCODING = tiktoken.get_encoding("cl100k_base")
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"


def count_tokens(value):
    """Count tokens in compact JSON using the same tokenizer as V1."""
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(ENCODING.encode(serialized))


def validate_compression(original, compressed, version):
    """
    Check structural preservation.

    V1 and V2 may remove descriptions from optional properties.
    V2 may also apply approved identifier-description changes
    to required properties.
    """
    errors = []

    # Tool-level information must remain unchanged.
    for key in ("name", "description", "category"):
        if original.get(key) != compressed.get(key):
            errors.append(f"{key} changed")

    original_schema = original.get("inputSchema", {})
    compressed_schema = compressed.get("inputSchema", {})

    # All schema-level fields other than properties must remain
    # unchanged, including required lists and other constraints.
    original_schema_without_properties = {
        key: value
        for key, value in original_schema.items()
        if key != "properties"
    }
    compressed_schema_without_properties = {
        key: value
        for key, value in compressed_schema.items()
        if key != "properties"
    }

    if original_schema_without_properties != compressed_schema_without_properties:
        errors.append("Schema-level information changed")

    original_properties = original_schema.get("properties", {})
    compressed_properties = compressed_schema.get("properties", {})
    required_fields = set(original_schema.get("required", []))

    # No properties may be added or removed.
    if set(original_properties) != set(compressed_properties):
        errors.append("Property names changed")
        return errors

    for property_name, original_property in original_properties.items():
        compressed_property = compressed_properties[property_name]

        # Property types, enums, and all other constraints must
        # remain unchanged. Only descriptions may be modified.
        original_non_description = {
            key: value
            for key, value in original_property.items()
            if key != "description"
        }
        compressed_non_description = {
            key: value
            for key, value in compressed_property.items()
            if key != "description"
        }

        if original_non_description != compressed_non_description:
            errors.append(
                f"{property_name}: type or other constraints changed"
            )

        original_description = original_property.get("description")
        compressed_description = compressed_property.get("description")

        if property_name not in required_fields:
            # Both versions inherit V1's optional-description removal,
            # except for explicitly preserved tool/property pairs.
            preserved_exception = (
                original.get("name"),
                property_name,
            ) in PRESERVED_OPTIONAL_DESCRIPTIONS
            if "description" in compressed_property and not preserved_exception:
                errors.append(
                    f"{property_name}: optional description was not removed"
                )
        elif version == "V1":
            # V1 must retain required-property descriptions.
            if original_description != compressed_description:
                errors.append(
                    f"{property_name}: required description changed in V1"
                )
        else:
            # V2 may preserve or shorten a required description,
            # but may not remove it when the original had one.
            if original_description and not compressed_description:
                errors.append(
                    f"{property_name}: required description was removed"
                )

    return errors


def main():
    tools = load_tools()

    original_total = 0
    v1_total = 0
    v2_total = 0

    v1_errors = []
    v2_errors = []

    v1_reduced_tools = 0
    v2_reduced_tools = 0
    v2_description_transformations = 0

    per_tool_results = []

    for tool in tools:
        original_tokens = count_tokens(tool)

        v1_tool = compress_schema(copy.deepcopy(tool))
        v2_tool = compress_schema_v2(copy.deepcopy(tool))

        v1_tokens = count_tokens(v1_tool)
        v2_tokens = count_tokens(v2_tool)

        original_total += original_tokens
        v1_total += v1_tokens
        v2_total += v2_tokens

        if v1_tokens < original_tokens:
            v1_reduced_tools += 1

        if v2_tokens < original_tokens:
            v2_reduced_tools += 1

        v1_errors.extend(
            f"{tool.get('name', 'unknown')}: {error}"
            for error in validate_compression(tool, v1_tool, "V1")
        )

        v2_errors.extend(
            f"{tool.get('name', 'unknown')}: {error}"
            for error in validate_compression(tool, v2_tool, "V2")
        )

        original_properties = tool.get("inputSchema", {}).get(
            "properties", {}
        )
        v2_properties = v2_tool.get("inputSchema", {}).get(
            "properties", {}
        )
        required_fields = set(
            tool.get("inputSchema", {}).get("required", [])
        )

        for property_name, original_property in original_properties.items():
            if property_name not in required_fields:
                continue

            original_description = original_property.get("description")
            compressed_description = v2_properties.get(
                property_name, {}
            ).get("description")

            if (
                original_description
                and compressed_description
                and original_description != compressed_description
            ):
                v2_description_transformations += 1

        per_tool_results.append({
            "tool_name": tool.get("name", "unknown"),
            "original_tokens": original_tokens,
            "v1_tokens": v1_tokens,
            "v2_tokens": v2_tokens,
            "v1_tokens_saved": original_tokens - v1_tokens,
            "v2_tokens_saved": original_tokens - v2_tokens,
        })

    def reduction_percentage(before, after):
        if before == 0:
            return 0.0
        return round((before - after) / before * 100, 2)

    print(f"Loaded tools: {len(tools)}")

    print("\nSchema Compression V1 vs V2")
    print("=" * 42)

    print(f"Original tokens: {original_total}")
    print(f"V1 compressed tokens: {v1_total}")
    print(f"V2 compressed tokens: {v2_total}")

    print("\nToken Savings")
    print("-" * 42)

    print(f"V1 tokens saved: {original_total - v1_total}")
    print(
        "V1 reduction: "
        f"{reduction_percentage(original_total, v1_total):.2f}%"
    )

    print(f"V2 tokens saved: {original_total - v2_total}")
    print(
        "V2 reduction: "
        f"{reduction_percentage(original_total, v2_total):.2f}%"
    )

    print(
        "Additional tokens saved by V2 vs V1: "
        f"{v1_total - v2_total}"
    )

    print(
        "Additional reduction vs V1: "
        f"{reduction_percentage(v1_total, v2_total):.2f}%"
    )

    print("\nTransformation Summary")
    print("-" * 42)
    print(f"Tools reduced by V1: {v1_reduced_tools}")
    print(f"Tools reduced by V2: {v2_reduced_tools}")
    print(
        "Required descriptions shortened by V2: "
        f"{v2_description_transformations}"
    )

    print("\nStructural Preservation")
    print("-" * 42)

    print(
        "V1 preservation checks: "
        f"{'PASSED' if not v1_errors else 'FAILED'}"
    )
    print(
        "V2 preservation checks: "
        f"{'PASSED' if not v2_errors else 'FAILED'}"
    )

    if v1_errors:
        print("\nV1 errors:")
        for error in v1_errors[:20]:
            print(f"- {error}")

    if v2_errors:
        print("\nV2 errors:")
        for error in v2_errors[:20]:
            print(f"- {error}")

    results = {
        "total_tools": len(tools),
        "tokenizer": "cl100k_base",
        "original_tokens": original_total,
        "v1": {
            "compressed_tokens": v1_total,
            "tokens_saved": original_total - v1_total,
            "reduction_percent": reduction_percentage(
                original_total, v1_total
            ),
            "tools_reduced": v1_reduced_tools,
            "preservation_passed": not v1_errors,
            "errors": v1_errors,
        },
        "v2": {
            "compressed_tokens": v2_total,
            "tokens_saved": original_total - v2_total,
            "reduction_percent": reduction_percentage(
                original_total, v2_total
            ),
            "tools_reduced": v2_reduced_tools,
            "required_descriptions_shortened": (
                v2_description_transformations
            ),
            "preservation_passed": not v2_errors,
            "errors": v2_errors,
        },
        "additional_tokens_saved_by_v2_vs_v1": v1_total - v2_total,
        "additional_reduction_percent_vs_v1": reduction_percentage(
            v1_total, v2_total
        ),
        "per_tool_results": per_tool_results,
    }

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    output_file = EXPERIMENTS_DIR / "compression_v2_results.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    print(f"\nSaved: {output_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
