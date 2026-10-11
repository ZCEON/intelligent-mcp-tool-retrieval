import copy
import json
import sys
from pathlib import Path

import tiktoken


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.compression.schema_compressor_v2 import compress_schema_v2


RESULTS_PATH = (
    PROJECT_ROOT / "experiments" / "retrieval_compression_v3_results.json"
)
TOOLS_PATH = PROJECT_ROOT / "data" / "tools" / "tools.json"

EXPECTED_QUERY_COUNT = 30
EXPECTED_TOP_K = 5
EXPECTED_COMPRESSION_METHOD = "revised_schema_compressor_v2"

ENCODING = tiktoken.get_encoding("cl100k_base")


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def count_tokens(data):
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(ENCODING.encode(serialized))


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


def validate_structure_and_recompute(tool, recorded):
    """
    Independently verify one selected tool.

    Re-runs the compressor, checks structural equivalence
    (descriptions ignored), and recomputes token counts.
    """
    errors = []

    compressed = compress_schema_v2(copy.deepcopy(tool))

    if strip_descriptions(tool) != strip_descriptions(compressed):
        errors.append(
            f"{tool.get('name')}: structural difference after "
            "compression (descriptions ignored)."
        )

    original_tokens = count_tokens(tool)
    compressed_tokens = count_tokens(compressed)

    if original_tokens != recorded.get("original_tokens"):
        errors.append(
            f"{tool.get('name')}: recorded original token count "
            f"({recorded.get('original_tokens')}) does not match "
            f"recomputation ({original_tokens})."
        )

    if compressed_tokens != recorded.get("compressed_tokens"):
        errors.append(
            f"{tool.get('name')}: recorded compressed token count "
            f"({recorded.get('compressed_tokens')}) does not match "
            f"recomputation ({compressed_tokens})."
        )

    saved = original_tokens - compressed_tokens

    if saved != recorded.get("tokens_saved"):
        errors.append(
            f"{tool.get('name')}: recorded tokens_saved "
            f"({recorded.get('tokens_saved')}) does not match "
            f"recomputation ({saved})."
        )

    return errors


def main():
    if not RESULTS_PATH.exists():
        print(f"ERROR: Results file not found: {RESULTS_PATH}")
        return

    data = load_json(RESULTS_PATH)
    summary = data.get("summary", {})
    query_results = data.get("query_results", [])

    tools_data = load_json(TOOLS_PATH)
    if isinstance(tools_data, dict):
        tools_data = tools_data.get("tools", [])

    tools_by_name = {
        tool["name"]: tool
        for tool in tools_data
        if isinstance(tool, dict) and "name" in tool
    }

    errors = []
    warnings = []

    # --------------------------------------------------
    # 1. Summary-level consistency.
    # --------------------------------------------------
    if summary.get("query_count") != len(query_results):
        errors.append(
            "Summary query_count does not match the number of query results."
        )

    if len(query_results) != EXPECTED_QUERY_COUNT:
        warnings.append(
            f"Expected {EXPECTED_QUERY_COUNT} queries, "
            f"but found {len(query_results)}."
        )

    if summary.get("top_k") != EXPECTED_TOP_K:
        warnings.append(
            f"Expected top_k={EXPECTED_TOP_K}, "
            f"but found {summary.get('top_k')}."
        )

    if summary.get("compression_method") != EXPECTED_COMPRESSION_METHOD:
        warnings.append(
            "Expected compression_method="
            f"{EXPECTED_COMPRESSION_METHOD!r}, "
            f"but found {summary.get('compression_method')!r}."
        )

    # --------------------------------------------------
    # 2. Check each query result.
    # --------------------------------------------------
    seen_queries = set()
    calculated_original = 0
    calculated_compressed = 0
    calculated_saved = 0
    calculated_retrieval_latency = 0.0
    calculated_compression_latency = 0.0
    calculated_pipeline_latency = 0.0
    calculated_selected_tools = 0
    structural_tools_checked = 0

    for index, result in enumerate(query_results, start=1):
        query = result.get("query")

        if not query:
            errors.append(f"Query {index}: missing query text.")
        elif query in seen_queries:
            warnings.append(f"Duplicate query found: {query}")
        seen_queries.add(query)

        selected_tools = result.get("selected_tools", [])
        tool_count = result.get("selected_tool_count")

        if tool_count is None:
            errors.append(f"Query {index}: missing selected_tool_count.")
            continue

        if len(selected_tools) != tool_count:
            errors.append(
                f"Query {index}: selected_tool_count does not match "
                "the selected_tools list."
            )

        if tool_count > EXPECTED_TOP_K:
            errors.append(
                f"Query {index}: retrieved more than {EXPECTED_TOP_K} tools."
            )

        tool_names = [tool.get("tool_name") for tool in selected_tools]

        if any(name is None for name in tool_names):
            errors.append(f"Query {index}: a selected tool has no name.")

        if len(tool_names) != len(set(tool_names)):
            warnings.append(
                f"Query {index}: duplicate tool names were retrieved."
            )

        # Per-tool recompression and token recomputation.
        for recorded in selected_tools:
            tool_name = recorded.get("tool_name")

            if tool_name not in tools_by_name:
                errors.append(
                    f"Query {index}: tool {tool_name!r} not found "
                    "in the dataset."
                )
                continue

            errors.extend(
                validate_structure_and_recompute(
                    tools_by_name[tool_name],
                    recorded,
                )
            )
            structural_tools_checked += 1

        # Token arithmetic.
        original = result.get("original_tokens", 0)
        compressed = result.get("compressed_tokens", 0)
        saved = result.get("tokens_saved", 0)

        if original < 0 or compressed < 0 or saved < 0:
            errors.append(f"Query {index}: negative token count found.")

        if original != compressed + saved:
            errors.append(
                f"Query {index}: original_tokens != "
                "compressed_tokens + tokens_saved."
            )

        tool_original = sum(
            tool.get("original_tokens", 0) for tool in selected_tools
        )
        tool_compressed = sum(
            tool.get("compressed_tokens", 0) for tool in selected_tools
        )
        tool_saved = sum(
            tool.get("tokens_saved", 0) for tool in selected_tools
        )

        if original != tool_original:
            errors.append(
                f"Query {index}: original token total does not match "
                "the selected tool totals."
            )

        if compressed != tool_compressed:
            errors.append(
                f"Query {index}: compressed token total does not match "
                "the selected tool totals."
            )

        if saved != tool_saved:
            errors.append(
                f"Query {index}: saved token total does not match "
                "the selected tool totals."
            )

        # Latency fields.
        retrieval = result.get("retrieval_latency_ms")
        compression = result.get("compression_latency_ms")
        pipeline = result.get("total_pipeline_latency_ms")

        if retrieval is None or compression is None or pipeline is None:
            errors.append(f"Query {index}: missing latency field(s).")
        elif retrieval < 0 or compression < 0:
            errors.append(f"Query {index}: negative latency found.")
        elif abs((retrieval + compression) - pipeline) > 0.01:
            errors.append(
                f"Query {index}: total_pipeline_latency_ms does not "
                "equal retrieval + compression latency."
            )

        calculated_original += original
        calculated_compressed += compressed
        calculated_saved += saved
        calculated_retrieval_latency += retrieval or 0.0
        calculated_compression_latency += compression or 0.0
        calculated_pipeline_latency += pipeline or 0.0
        calculated_selected_tools += tool_count

    # --------------------------------------------------
    # 3. Aggregate consistency with the summary.
    # --------------------------------------------------
    if calculated_original != summary.get("total_original_tokens"):
        errors.append("Original token total does not match the summary.")

    if calculated_compressed != summary.get("total_compressed_tokens"):
        errors.append("Compressed token total does not match the summary.")

    if calculated_saved != summary.get("total_tokens_saved"):
        errors.append("Saved token total does not match the summary.")

    if calculated_original != calculated_compressed + calculated_saved:
        errors.append("Aggregate token arithmetic is inconsistent.")

    # Reduction percentage.
    if calculated_original > 0:
        reduction = calculated_saved / calculated_original * 100
        reported = summary.get("overall_reduction_percent", 0.0)

        if abs(reduction - reported) > 0.02:
            errors.append(
                "Reported overall reduction percentage does not match "
                "the calculated percentage."
            )

    # Averages.
    if query_results:
        n = len(query_results)

        expected_averages = {
            "average_retrieval_latency_ms": calculated_retrieval_latency / n,
            "average_compression_latency_ms": (
                calculated_compression_latency / n
            ),
            "average_total_pipeline_latency_ms": (
                calculated_pipeline_latency / n
            ),
            "average_selected_tools_per_query": (
                calculated_selected_tools / n
            ),
        }

        for key, expected in expected_averages.items():
            reported = summary.get(key)

            if reported is None:
                errors.append(f"Summary is missing {key}.")
            elif abs(reported - expected) > 0.01:
                errors.append(
                    f"Summary {key} ({reported}) does not match the "
                    f"recomputed value ({expected:.4f})."
                )

    # --------------------------------------------------
    # 4. Display results.
    # --------------------------------------------------
    print("=" * 55)
    print("COMBINED PIPELINE VALIDATION (V3)")
    print("=" * 55)

    print(f"Queries checked:       {len(query_results)}")
    print(f"Tools recompressed:    {structural_tools_checked}")
    print(f"Original tokens:       {calculated_original}")
    print(f"Compressed tokens:     {calculated_compressed}")
    print(f"Tokens saved:          {calculated_saved}")

    if calculated_original > 0:
        print(
            f"Calculated reduction:  "
            f"{calculated_saved / calculated_original * 100:.2f}%"
        )

    print(f"\nErrors:   {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    for error in errors:
        print(f"ERROR: {error}")

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        print("\nVALIDATION FAILED — investigate the reported errors.")
    else:
        print("\nVALIDATION PASSED — no consistency errors found.")

    print(
        "\nNOTE: This validation covers arithmetic, structure, and "
        "consistency. It does not prove semantic equivalence or "
        "successful tool execution."
    )


if __name__ == "__main__":
    main()
