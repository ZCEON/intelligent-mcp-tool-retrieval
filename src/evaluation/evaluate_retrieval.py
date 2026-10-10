import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.keyword_retriever import load_tools, retrieve_tools
from retrieval.bm25_retriever import BM25Retriever
from retrieval.semantic_retriever import SemanticRetriever


PROJECT_ROOT = Path(__file__).parent.parent.parent
QUERIES_FILE = PROJECT_ROOT / "data" / "queries" / "test_queries.json"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"


def load_queries():
    """Load the test queries from the JSON dataset."""
    with open(QUERIES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_retrieval(retrieve_function, tools, queries, top_k=5):
    """Evaluate a retriever using Recall@1, Recall@3, and Recall@5."""

    total_queries = len(queries)

    if total_queries == 0:
        raise ValueError("The test query dataset is empty.")

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    query_results = []
    total_latency_ms = 0.0

    for query_data in queries:
        query = query_data["query"]
        expected_tools = set(query_data["expected_tools"])

        start_time = time.perf_counter()
        retrieved = retrieve_function(query, tools, top_k)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        total_latency_ms += elapsed_ms

        retrieved_names = [
            item["tool"]["name"] for item in retrieved
        ]

        hit_at_1 = bool(expected_tools.intersection(retrieved_names[:1]))
        hit_at_3 = bool(expected_tools.intersection(retrieved_names[:3]))
        hit_at_5 = bool(expected_tools.intersection(retrieved_names[:5]))

        hits_at_1 += int(hit_at_1)
        hits_at_3 += int(hit_at_3)
        hits_at_5 += int(hit_at_5)

        query_results.append({
            "id": query_data["id"],
            "query": query,
            "expected_tools": sorted(expected_tools),
            "retrieved_tools": retrieved_names,
            "hit_at_1": hit_at_1,
            "hit_at_3": hit_at_3,
            "hit_at_5": hit_at_5,
            "latency_ms": round(elapsed_ms, 4),
        })

    return {
        "total_queries": total_queries,
        "recall_at_1": round(hits_at_1 / total_queries * 100, 2),
        "recall_at_3": round(hits_at_3 / total_queries * 100, 2),
        "recall_at_5": round(hits_at_5 / total_queries * 100, 2),
        "average_latency_ms": round(total_latency_ms / total_queries, 4),
        "query_results": query_results,
    }


def keyword_adapter(query, tools, top_k):
    """Adapt the keyword retriever to the evaluation interface."""
    return retrieve_tools(query, tools, top_k=top_k)


def bm25_adapter(query, retriever, top_k):
    """Adapt the BM25 retriever to the evaluation interface."""
    return retriever.retrieve(query, top_k=top_k)


def semantic_adapter(query, retriever, top_k):
    """Adapt semantic retrieval to the evaluation interface."""
    return retriever.retrieve(query, top_k=top_k)


def save_results(results):
    """Save each retrieval method's results as a JSON file."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    for method_name, metrics in results.items():
        output_file = EXPERIMENTS_DIR / f"{method_name}_results.json"

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(metrics, file, indent=2)

        print(f"Saved: {output_file.relative_to(PROJECT_ROOT)}")


def print_results(method_name, metrics):
    """Print the evaluation metrics for one retrieval method."""
    print(f"\n{method_name}")
    print("=" * len(method_name))
    print(f"Total queries: {metrics['total_queries']}")
    print(f"Recall@1: {metrics['recall_at_1']:.2f}%")
    print(f"Recall@3: {metrics['recall_at_3']:.2f}%")
    print(f"Recall@5: {metrics['recall_at_5']:.2f}%")
    print(f"Average retrieval latency: {metrics['average_latency_ms']:.4f} ms")


if __name__ == "__main__":
    tools = load_tools()
    queries = load_queries()

    print(f"Loaded tools: {len(tools)}")
    print(f"Loaded queries: {len(queries)}")

    # Build BM25 once and reuse it for every query.
    bm25_retriever = BM25Retriever(tools)

    # Build semantic retriever once and reuse it for every query.
    semantic_retriever = SemanticRetriever(tools)

    # Evaluate both methods on the same dataset.
    keyword_results = evaluate_retrieval(
        keyword_adapter,
        tools,
        queries,
        top_k=5,
    )

    bm25_results = evaluate_retrieval(
        lambda query, _tools, top_k: bm25_adapter(
            query, bm25_retriever, top_k
        ),
        tools,
        queries,
        top_k=5,
    )

    semantic_results = evaluate_retrieval(
        lambda query, _tools, top_k: semantic_adapter(
            query, semantic_retriever, top_k
        ),
        tools,
        queries,
        top_k=5,
    )

    results = {
        "keyword_baseline": keyword_results,
        "bm25": bm25_results,
        "semantic": semantic_results,
    }

    print_results("Keyword Baseline", keyword_results)
    print_results("BM25 Retrieval", bm25_results)
    print_results("Semantic Retrieval", semantic_results)

    save_results(results)
