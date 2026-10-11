import copy
import json
import sys
import time
from pathlib import Path

import tiktoken


# --------------------------------------------------
# Project setup
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retrieval.keyword_retriever import load_tools
from retrieval.semantic_retriever import SemanticRetriever
from compression.schema_compressor_v2 import compress_schema_v2


QUERIES_FILE = PROJECT_ROOT / "data" / "queries" / "test_queries.json"

OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "combined_pipeline_evaluation.json"
)

TOP_K = 5
TOKENIZER_NAME = "cl100k_base"

encoding = tiktoken.get_encoding(TOKENIZER_NAME)


# --------------------------------------------------
# Data loading and token counting
# --------------------------------------------------

def load_queries():
    """Load the labeled test queries."""
    with QUERIES_FILE.open("r", encoding="utf-8") as file:
        queries = json.load(file)

    if isinstance(queries, dict):
        queries = queries.get("queries", [])

    if not isinstance(queries, list):
        raise ValueError("The query dataset must contain a list.")

    if not queries:
        raise ValueError("The query dataset is empty.")

    for index, query in enumerate(queries):
        if not isinstance(query.get("query"), str):
            raise ValueError(
                f"Query at index {index} has no valid query string."
            )

        if not isinstance(query.get("expected_tools"), list):
            raise ValueError(
                f"Query at index {index} has no expected_tools list."
            )

    return queries


def count_tokens(data):
    """
    Count tokens using compact JSON serialization.

    This counts the complete serialized tool definition,
    not only the inputSchema field.
    """
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return len(encoding.encode(serialized))


# --------------------------------------------------
# Structural validation
# --------------------------------------------------

def remove_descriptions(value):
    """
    Return a copy with description fields removed recursively.

    This lets us compare schema structure while ignoring
    intentional description removals and shortenings.
    """
    if isinstance(value, dict):
        return {
            key: remove_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }

    if isinstance(value, list):
        return [remove_descriptions(item) for item in value]

    return copy.deepcopy(value)


def validate_schema_structure(original_tool, compressed_tool):
    """
    Verify that compression has not changed the schema structure.

    Description changes are excluded because they are the
    intended operation of Schema Compression V2.
    """
    original_structure = remove_descriptions(original_tool)
    compressed_structure = remove_descriptions(compressed_tool)

    return original_structure == compressed_structure


# --------------------------------------------------
# Retrieval result normalization
# --------------------------------------------------

def normalize_retrieved_tools(retrieved):
    """
    Convert retriever results into a list of tool dictionaries.

    SemanticRetriever normally returns records containing
    a nested 'tool' dictionary.
    """
    normalized = []

    for item in retrieved:
        if not isinstance(item, dict):
            raise TypeError(
                "A retrieval result must be a dictionary."
            )

        tool = item.get("tool", item)

        if not isinstance(tool, dict) or not isinstance(
            tool.get("name"), str
        ):
            raise ValueError(
                "A retrieved result does not contain a valid tool name."
            )

        normalized.append(tool)

    return normalized


# --------------------------------------------------
# Evaluate one query
# --------------------------------------------------

def evaluate_query(retriever, query_record, all_tools):
    query = query_record["query"]
    expected_tools = set(query_record["expected_tools"])

    # Measure retrieval latency separately.
    retrieval_start = time.perf_counter()

    retrieved_results = retriever.retrieve(
        query,
        top_k=TOP_K,
    )

    retrieval_latency_ms = (
        time.perf_counter() - retrieval_start
    ) * 1000

    retrieved_tools = normalize_retrieved_tools(
        retrieved_results
    )

    retrieved_names = [
        tool["name"] for tool in retrieved_tools
    ]

    # Match the recall methodology used by evaluate_retrieval.py.
    hit_at_1 = bool(
        expected_tools.intersection(retrieved_names[:1])
    )

    hit_at_3 = bool(
        expected_tools.intersection(retrieved_names[:3])
    )

    hit_at_5 = bool(
        expected_tools.intersection(retrieved_names[:5])
    )

    original_tokens = 0
    compressed_tokens = 0
    structure_checks_passed = 0
    selected_tools = []

    compression_start = time.perf_counter()

    for original_tool in retrieved_tools:
        compressed_tool = compress_schema_v2(original_tool)

        original_count = count_tokens(original_tool)
        compressed_count = count_tokens(compressed_tool)

        structure_preserved = validate_schema_structure(
            original_tool,
            compressed_tool,
        )

        original_tokens += original_count
        compressed_tokens += compressed_count

        structure_checks_passed += int(structure_preserved)

        selected_tools.append({
            "tool_name": original_tool["name"],
            "original_tokens": original_count,
            "compressed_tokens": compressed_count,
            "tokens_saved": original_count - compressed_count,
            "structure_preserved": structure_preserved,
        })

    compression_latency_ms = (
        time.perf_counter() - compression_start
    ) * 1000

    tokens_saved = original_tokens - compressed_tokens

    reduction_percent = (
        tokens_saved / original_tokens * 100
        if original_tokens > 0
        else 0.0
    )

    return {
        "id": query_record.get("id"),
        "query": query,
        "expected_tools": sorted(expected_tools),
        "retrieved_tools": retrieved_names,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "selected_tool_count": len(retrieved_tools),
        "retrieval_latency_ms": round(retrieval_latency_ms, 4),
        "compression_latency_ms": round(
            compression_latency_ms, 4
        ),
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "tokens_saved": tokens_saved,
        "reduction_percent": round(reduction_percent, 2),
        "structure_checks_passed": structure_checks_passed,
        "structure_checks_total": len(retrieved_tools),
        "selected_tools": selected_tools,
    }


# --------------------------------------------------
# Evaluate the complete benchmark
# --------------------------------------------------

def main():
    print("=" * 65)
    print("SEMANTIC RETRIEVAL + SCHEMA COMPRESSION V2 EVALUATION")
    print("=" * 65)

    tools = load_tools()
    queries = load_queries()

    print(f"Loaded tools: {len(tools)}")
    print(f"Loaded queries: {len(queries)}")
    print(f"Top-K: {TOP_K}")

    # Build the semantic retriever once for the benchmark.
    retriever = SemanticRetriever(tools)

    query_results = [
        evaluate_query(retriever, query_record, tools)
        for query_record in queries
    ]

    query_count = len(query_results)

    hits_at_1 = sum(
        result["hit_at_1"] for result in query_results
    )

    hits_at_3 = sum(
        result["hit_at_3"] for result in query_results
    )

    hits_at_5 = sum(
        result["hit_at_5"] for result in query_results
    )

    total_original_tokens = sum(
        result["original_tokens"] for result in query_results
    )

    total_compressed_tokens = sum(
        result["compressed_tokens"] for result in query_results
    )

    total_tokens_saved = (
        total_original_tokens - total_compressed_tokens
    )

    total_selected_tools = sum(
        result["selected_tool_count"] for result in query_results
    )

    total_structure_checks_passed = sum(
        result["structure_checks_passed"] for result in query_results
    )

    total_structure_checks = sum(
        result["structure_checks_total"] for result in query_results
    )

    average_retrieval_latency_ms = sum(
        result["retrieval_latency_ms"]
        for result in query_results
    ) / query_count

    average_compression_latency_ms = sum(
        result["compression_latency_ms"]
        for result in query_results
    ) / query_count

    overall_reduction_percent = (
        total_tokens_saved / total_original_tokens * 100
        if total_original_tokens > 0
        else 0.0
    )

    summary = {
        "retrieval_method": "semantic",
        "compression_method": "schema_compressor_v2",
        "top_k": TOP_K,
        "query_count": query_count,
        "recall_at_1": round(hits_at_1 / query_count * 100, 2),
        "recall_at_3": round(hits_at_3 / query_count * 100, 2),
        "recall_at_5": round(hits_at_5 / query_count * 100, 2),
        "total_selected_tools": total_selected_tools,
        "total_original_tokens": total_original_tokens,
        "total_compressed_tokens": total_compressed_tokens,
        "total_tokens_saved": total_tokens_saved,
        "overall_reduction_percent": round(
            overall_reduction_percent, 2
        ),
        "average_retrieval_latency_ms": round(
            average_retrieval_latency_ms, 4
        ),
        "average_compression_latency_ms": round(
            average_compression_latency_ms, 4
        ),
        "structure_checks_passed": total_structure_checks_passed,
        "structure_checks_total": total_structure_checks,
        "all_structures_preserved": (
            total_structure_checks_passed == total_structure_checks
        ),
        "tokenizer": TOKENIZER_NAME,
    }

    results = {
        "summary": summary,
        "query_results": query_results,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    # Display the main results.
    print("\n" + "-" * 65)
    print("EVALUATION RESULTS")
    print("-" * 65)

    print(f"Queries evaluated:          {query_count}")
    print(f"Recall@1:                   {summary['recall_at_1']:.2f}%")
    print(f"Recall@3:                   {summary['recall_at_3']:.2f}%")
    print(f"Recall@5:                   {summary['recall_at_5']:.2f}%")

    print(f"\nOriginal tokens:            {total_original_tokens}")
    print(f"Compressed tokens:          {total_compressed_tokens}")
    print(f"Tokens saved:               {total_tokens_saved}")
    print(f"Overall reduction:          {overall_reduction_percent:.2f}%")

    print(
        f"\nAverage retrieval latency:  "
        f"{average_retrieval_latency_ms:.4f} ms"
    )

    print(
        f"Average compression latency: "
        f"{average_compression_latency_ms:.4f} ms"
    )

    print(
        f"\nStructural checks passed:  "
        f"{total_structure_checks_passed}/{total_structure_checks}"
    )

    print(
        f"All structures preserved:   "
        f"{summary['all_structures_preserved']}"
    )

    print(f"\nResults saved to:\n{OUTPUT_FILE}")

    print("\nIMPORTANT:")
    print(
        "Structural checks ignore description changes. "
        "They do not prove semantic equivalence or valid tool execution."
    )


if __name__ == "__main__":
    main()
