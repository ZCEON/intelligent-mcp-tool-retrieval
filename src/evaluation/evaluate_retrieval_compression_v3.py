import copy
import json
import sys
import time
from pathlib import Path

import tiktoken


# Resolve the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.semantic_retriever import SemanticRetriever
from src.compression.schema_compressor_v2 import compress_schema_v2


# Input files
TOOLS_PATH = PROJECT_ROOT / "data" / "tools" / "tools.json"
QUERIES_PATH = PROJECT_ROOT / "data" / "queries" / "test_queries.json"

# Save results to a new file.
# Previous experiment results will not be overwritten.
OUTPUT_PATH = (
    PROJECT_ROOT
    / "experiments"
    / "retrieval_compression_v3_results.json"
)

ENCODING = tiktoken.get_encoding("cl100k_base")

TOP_K = 5


def load_json(path):
    """Load a JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def count_tokens(data):
    """
    Count tokens in the compact JSON representation.

    This includes tool names, descriptions, property names,
    schema constraints, and other serialized JSON content.
    """
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return len(ENCODING.encode(serialized))


def extract_tools(data):
    """Extract tools from supported dataset formats."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        return data["tools"]

    raise ValueError(
        "Unexpected tools dataset format. Expected a list "
        "or a dictionary containing a 'tools' list."
    )


def extract_queries(data):
    """Extract queries from supported dataset formats."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("queries"), list):
        return data["queries"]

    raise ValueError(
        "Unexpected query dataset format. Expected a list "
        "or a dictionary containing a 'queries' list."
    )


def get_query_text(query):
    """Extract the text of a query."""
    if isinstance(query, str):
        return query

    if isinstance(query, dict):
        for field in ("query", "text", "user_query", "question"):
            value = query.get(field)

            if isinstance(value, str):
                return value

    raise ValueError(
        f"Could not find query text in record: {query}"
    )


def get_tool_name(tool):
    """Return a tool's name."""
    if isinstance(tool, dict):
        return tool.get("name")

    return None


def retrieve_top_k(retriever, query, tools):
    """Retrieve the top-K tools using semantic retrieval."""
    return retriever.retrieve(query, top_k=TOP_K)


def normalize_retrieved_tools(retrieved, all_tools):
    """
    Normalize retrieval results into complete tool dictionaries.

    Supports:
    - {"tool": {...}, "score": ...}
    - Complete tool dictionaries
    - Tool names as strings
    - Dictionaries containing a 'name' field
    """
    tools_by_name = {
        tool["name"]: tool
        for tool in all_tools
        if isinstance(tool, dict) and "name" in tool
    }

    normalized = []

    for item in retrieved:
        if (
            isinstance(item, dict)
            and isinstance(item.get("tool"), dict)
        ):
            normalized.append(item["tool"])
            continue

        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("name")
        else:
            name = None

        if name in tools_by_name:
            normalized.append(tools_by_name[name])

    return normalized


def evaluate_query(retriever, query_record, tools):
    """Evaluate retrieval and schema compression for one query."""
    query_text = get_query_text(query_record)

    # -----------------------------------------------
    # 1. Measure retrieval latency
    # -----------------------------------------------
    retrieval_start = time.perf_counter()

    retrieved = retrieve_top_k(
        retriever,
        query_text,
        tools,
    )

    retrieval_latency_ms = (
        time.perf_counter() - retrieval_start
    ) * 1000

    selected_tools = normalize_retrieved_tools(
        retrieved,
        tools,
    )

    # Handle queries that return no usable tools.
    if not selected_tools:
        return {
            "query": query_text,
            "selected_tool_count": 0,
            "retrieval_latency_ms": round(
                retrieval_latency_ms, 4
            ),
            "compression_latency_ms": 0.0,
            "total_pipeline_latency_ms": round(
                retrieval_latency_ms, 4
            ),
            "original_tokens": 0,
            "compressed_tokens": 0,
            "tokens_saved": 0,
            "reduction_percent": 0.0,
            "selected_tools": [],
        }

    original_tokens = 0
    compressed_tokens = 0

    tool_results = []

    # -----------------------------------------------
    # 2. Compress the selected schemas
    # 3. Count tokens before and after compression
    # -----------------------------------------------
    compression_start = time.perf_counter()

    compressed_tools = []

    for tool in selected_tools:
        compressed_tool = compress_schema_v2(
            copy.deepcopy(tool)
        )

        compressed_tools.append(compressed_tool)

    compression_latency_ms = (
        time.perf_counter() - compression_start
    ) * 1000

    # Count tokens outside the compression timing measurement.
    for original_tool, compressed_tool in zip(
        selected_tools,
        compressed_tools,
    ):
        original_count = count_tokens(original_tool)
        compressed_count = count_tokens(compressed_tool)

        original_tokens += original_count
        compressed_tokens += compressed_count

        tool_results.append(
            {
                "tool_name": get_tool_name(original_tool),
                "original_tokens": original_count,
                "compressed_tokens": compressed_count,
                "tokens_saved": (
                    original_count - compressed_count
                ),
            }
        )

    # -----------------------------------------------
    # 4. Calculate token savings
    # -----------------------------------------------
    tokens_saved = original_tokens - compressed_tokens

    reduction_percent = (
        (tokens_saved / original_tokens) * 100
        if original_tokens > 0
        else 0.0
    )

    total_pipeline_latency_ms = (
        retrieval_latency_ms + compression_latency_ms
    )

    return {
        "query": query_text,
        "selected_tool_count": len(selected_tools),
        "retrieval_latency_ms": round(
            retrieval_latency_ms, 4
        ),
        "compression_latency_ms": round(
            compression_latency_ms, 4
        ),
        "total_pipeline_latency_ms": round(
            total_pipeline_latency_ms, 4
        ),
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "tokens_saved": tokens_saved,
        "reduction_percent": round(
            reduction_percent, 2
        ),
        "selected_tools": tool_results,
    }


def main():
    # -----------------------------------------------
    # 1. Load the dataset and test queries
    # -----------------------------------------------
    tools_data = load_json(TOOLS_PATH)
    queries_data = load_json(QUERIES_PATH)

    tools = extract_tools(tools_data)
    queries = extract_queries(queries_data)

    if not tools:
        raise ValueError("The tools dataset is empty.")

    if not queries:
        raise ValueError("The query dataset is empty.")

    # -----------------------------------------------
    # 2. Build the semantic retriever once
    # -----------------------------------------------
    retriever = SemanticRetriever(tools)

    results = []

    for query_record in queries:
        result = evaluate_query(
            retriever,
            query_record,
            tools,
        )

        results.append(result)

    # -----------------------------------------------
    # 3. Calculate aggregate metrics
    # -----------------------------------------------
    total_queries = len(results)

    total_original_tokens = sum(
        result["original_tokens"]
        for result in results
    )

    total_compressed_tokens = sum(
        result["compressed_tokens"]
        for result in results
    )

    total_tokens_saved = (
        total_original_tokens - total_compressed_tokens
    )

    overall_reduction = (
        (total_tokens_saved / total_original_tokens) * 100
        if total_original_tokens > 0
        else 0.0
    )

    average_retrieval_latency = (
        sum(
            result["retrieval_latency_ms"]
            for result in results
        ) / total_queries
    )

    average_compression_latency = (
        sum(
            result["compression_latency_ms"]
            for result in results
        ) / total_queries
    )

    average_total_pipeline_latency = (
        sum(
            result["total_pipeline_latency_ms"]
            for result in results
        ) / total_queries
    )

    average_selected_tools = (
        sum(
            result["selected_tool_count"]
            for result in results
        ) / total_queries
    )

    # -----------------------------------------------
    # 4. Prepare the experiment report
    # -----------------------------------------------
    summary = {
        "retrieval_method": "semantic",
        "compression_method": "revised_schema_compressor_v2",
        "top_k": TOP_K,
        "query_count": total_queries,
        "average_selected_tools_per_query": round(
            average_selected_tools, 2
        ),
        "total_original_tokens": total_original_tokens,
        "total_compressed_tokens": total_compressed_tokens,
        "total_tokens_saved": total_tokens_saved,
        "overall_reduction_percent": round(
            overall_reduction, 2
        ),
        "average_retrieval_latency_ms": round(
            average_retrieval_latency, 4
        ),
        "average_compression_latency_ms": round(
            average_compression_latency, 4
        ),
        "average_total_pipeline_latency_ms": round(
            average_total_pipeline_latency, 4
        ),
        "tokenizer": "cl100k_base",
    }

    output = {
        "summary": summary,
        "query_results": results,
    }

    # -----------------------------------------------
    # 5. Save without overwriting earlier experiments
    # -----------------------------------------------
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # -----------------------------------------------
    # 6. Print the results
    # -----------------------------------------------
    print("\nSemantic Retrieval + Revised Schema Compression V3")
    print("=" * 58)

    print(f"Tools available: {len(tools)}")
    print(f"Queries evaluated: {total_queries}")
    print(f"Top-K: {TOP_K}")

    print("\nToken Evaluation")
    print("-" * 30)
    print(f"Original tokens: {total_original_tokens}")
    print(f"Compressed tokens: {total_compressed_tokens}")
    print(f"Tokens saved: {total_tokens_saved}")
    print(f"Overall reduction: {overall_reduction:.2f}%")

    print("\nLatency Evaluation")
    print("-" * 30)
    print(
        "Average retrieval latency: "
        f"{average_retrieval_latency:.4f} ms"
    )
    print(
        "Average compression latency: "
        f"{average_compression_latency:.4f} ms"
    )
    print(
        "Average total pipeline latency: "
        f"{average_total_pipeline_latency:.4f} ms"
    )

    print(f"\nResults saved to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
