import copy
import json
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.keyword_retriever import load_tools
from compression.schema_compressor import compress_schema


PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"

# Consistent tokenizer for comparing original and compressed schemas.
ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(data):
    """Count tokens in a JSON representation of a tool."""
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(ENCODING.encode(serialized))


def check_schema_preservation(original, compressed):
    """Check that required schema information is preserved."""

    original_schema = original.get("inputSchema", {})
    compressed_schema = compressed.get("inputSchema", {})

    original_properties = original_schema.get("properties", {})
    compressed_properties = compressed_schema.get("properties", {})

    original_required = original_schema.get("required", [])
    compressed_required = compressed_schema.get("required", [])

    checks = {
        "tool_name_preserved": (
            original.get("name") == compressed.get("name")
        ),
        "tool_description_preserved": (
            original.get("description") == compressed.get("description")
        ),
        "category_preserved": (
            original.get("category") == compressed.get("category")
        ),
        "schema_type_preserved": (
            original_schema.get("type") == compressed_schema.get("type")
        ),
        "required_list_preserved": (
            original_required == compressed_required
        ),
        "property_names_preserved": (
            set(original_properties) == set(compressed_properties)
        ),
        "required_properties_preserved": all(
            field in compressed_properties
            for field in original_required
        ),
        "property_types_preserved": all(
            original_properties[name].get("type")
            == compressed_properties[name].get("type")
            for name in original_properties
            if name in compressed_properties
        ),
        "enum_values_preserved": all(
            original_properties[name].get("enum")
            == compressed_properties[name].get("enum")
            for name in original_properties
            if name in compressed_properties
        ),
    }

    # Required-property descriptions must remain unchanged.
    required_descriptions_preserved = all(
        original_properties.get(field, {}).get("description")
        == compressed_properties.get(field, {}).get("description")
        for field in original_required
    )

    checks["required_descriptions_preserved"] = (
        required_descriptions_preserved
    )

    return checks


def evaluate_compression(tools):
    """Evaluate compression across the complete tool dataset."""

    results = []

    total_original_tokens = 0
    total_compressed_tokens = 0
    tools_with_reduction = 0

    all_checks_passed = True

    for tool in tools:
        original = copy.deepcopy(tool)
        compressed = compress_schema(tool)

        original_tokens = count_tokens(original)
        compressed_tokens = count_tokens(compressed)

        token_savings = original_tokens - compressed_tokens

        if original_tokens > 0:
            reduction_percentage = (
                token_savings / original_tokens
            ) * 100
        else:
            reduction_percentage = 0.0

        checks = check_schema_preservation(original, compressed)
        checks_passed = all(checks.values())

        if token_savings > 0:
            tools_with_reduction += 1

        if not checks_passed:
            all_checks_passed = False

        total_original_tokens += original_tokens
        total_compressed_tokens += compressed_tokens

        results.append({
            "tool_name": tool["name"],
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": token_savings,
            "reduction_percentage": round(reduction_percentage, 2),
            "preservation_checks": checks,
            "all_preservation_checks_passed": checks_passed,
        })

    total_tokens_saved = (
        total_original_tokens - total_compressed_tokens
    )

    if total_original_tokens > 0:
        overall_reduction = (
            total_tokens_saved / total_original_tokens
        ) * 100
    else:
        overall_reduction = 0.0

    return {
        "total_tools": len(tools),
        "total_original_tokens": total_original_tokens,
        "total_compressed_tokens": total_compressed_tokens,
        "total_tokens_saved": total_tokens_saved,
        "overall_reduction_percentage": round(overall_reduction, 2),
        "tools_with_token_reduction": tools_with_reduction,
        "all_preservation_checks_passed": all_checks_passed,
        "tool_results": results,
    }


def main():
    tools = load_tools()

    print(f"Loaded tools: {len(tools)}")

    metrics = evaluate_compression(tools)

    print("\nSchema Compression Evaluation")
    print("=============================")
    print(f"Total tools: {metrics['total_tools']}")
    print(f"Original tokens: {metrics['total_original_tokens']}")
    print(f"Compressed tokens: {metrics['total_compressed_tokens']}")
    print(f"Tokens saved: {metrics['total_tokens_saved']}")
    print(
        "Overall token reduction: "
        f"{metrics['overall_reduction_percentage']:.2f}%"
    )
    print(
        "Tools with token reduction: "
        f"{metrics['tools_with_token_reduction']}"
    )
    print(
        "All preservation checks passed: "
        f"{metrics['all_preservation_checks_passed']}"
    )

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    output_file = EXPERIMENTS_DIR / "compression_results.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    print(f"\nSaved: {output_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
