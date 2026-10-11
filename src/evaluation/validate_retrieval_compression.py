import json
from pathlib import Path


RESULTS_PATH = Path("experiments/retrieval_compression_results.json")
EXPECTED_QUERY_COUNT = 30
EXPECTED_TOP_K = 5


def main():
    if not RESULTS_PATH.exists():
        print(f"ERROR: Results file not found: {RESULTS_PATH}")
        return

    with RESULTS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    summary = data["summary"]
    query_results = data["query_results"]

    errors = []
    warnings = []

    # 1. Validate the experiment summary.
    if summary["query_count"] != len(query_results):
        errors.append(
            "Summary query_count does not match the number of query results."
        )

    if len(query_results) != EXPECTED_QUERY_COUNT:
        warnings.append(
            f"Expected {EXPECTED_QUERY_COUNT} queries, "
            f"but found {len(query_results)}."
        )

    if summary["top_k"] != EXPECTED_TOP_K:
        warnings.append(
            f"Expected top_k={EXPECTED_TOP_K}, "
            f"but found {summary['top_k']}."
        )

    # 2. Check each query result.
    seen_queries = set()
    calculated_original = 0
    calculated_compressed = 0
    calculated_saved = 0

    for index, result in enumerate(query_results, start=1):
        query = result.get("query", f"Query {index}")

        if query in seen_queries:
            warnings.append(f"Duplicate query found: {query}")
        seen_queries.add(query)

        selected_tools = result.get("selected_tools", [])

        if len(selected_tools) != result.get("selected_tool_count"):
            errors.append(
                f"Query {index}: selected_tool_count does not match "
                "the selected_tools list."
            )

        if len(selected_tools) > EXPECTED_TOP_K:
            errors.append(
                f"Query {index}: retrieved more than {EXPECTED_TOP_K} tools."
            )

        tool_names = [
            tool.get("tool_name")
            for tool in selected_tools
        ]

        if len(tool_names) != len(set(tool_names)):
            warnings.append(
                f"Query {index}: duplicate tool names were retrieved."
            )

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
            tool.get("original_tokens", 0)
            for tool in selected_tools
        )
        tool_compressed = sum(
            tool.get("compressed_tokens", 0)
            for tool in selected_tools
        )
        tool_saved = sum(
            tool.get("tokens_saved", 0)
            for tool in selected_tools
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

        calculated_original += original
        calculated_compressed += compressed
        calculated_saved += saved

    # 3. Compare query-level totals with the summary.
    if calculated_original != summary["total_original_tokens"]:
        errors.append("Original token total does not match the summary.")

    if calculated_compressed != summary["total_compressed_tokens"]:
        errors.append("Compressed token total does not match the summary.")

    if calculated_saved != summary["total_tokens_saved"]:
        errors.append("Saved token total does not match the summary.")

    if calculated_original != calculated_compressed + calculated_saved:
        errors.append("Aggregate token arithmetic is inconsistent.")

    # 4. Recalculate the reduction percentage.
    if calculated_original > 0:
        reduction = (
            calculated_saved / calculated_original
        ) * 100

        reported_reduction = summary["overall_reduction_percent"]

        if abs(reduction - reported_reduction) > 0.02:
            errors.append(
                "Reported overall reduction percentage does not match "
                "the calculated percentage."
            )

    # 5. Display results.
    print("=" * 55)
    print("RETRIEVAL + COMPRESSION VALIDATION")
    print("=" * 55)

    print(f"Queries checked:       {len(query_results)}")
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


if __name__ == "__main__":
    main()
