# Experiments — Result Validity and History

This file classifies every result in this directory. It was produced by a
read-only audit (Milestone 2) that verified each number by in-memory replay
against the committed code. **No result file in this directory was modified,
deleted, renamed, or regenerated during the audit.**

Audit date: 2026-10-30. Verification method: each result was recomputed in
memory from the committed implementations and the frozen datasets; recorded
per-tool numbers were compared one by one.

---

## 1. Summary of result classes

| Class | Meaning |
|---|---|
| **Verified (development set)** | Reproduces exactly from committed code + frozen data. Valid as a *development-set* number only. |
| **Historical / superseded** | Arithmetically sound, but produced by an intermediate compressor state that was never committed. Cannot be regenerated from any git revision. Kept for audit trail; must not be quoted as current. |
| **Not an independent benchmark** | Applies to **every file in this directory** — see Section 5. |

---

## 2. Verified results (development set)

All figures below were reproduced exactly during the audit.

| Result file | Metric | Value | Reproduction |
|---|---|---|---|
| `compression_results.json` | V1 corpus compression | **2.10%** (129 of 6137 tokens saved) | Replayed from `src/compression/schema_compressor.py` — identical |
| `compression_v3_results.json` | Current V2 corpus compression | **3.50%** (215 of 6137; 72 description changes: 71 shortened, 1 removed; 100/100 structural checks) | Replayed from `src/compression/schema_compressor_v2.py` at commit `f769aa4` — identical, including all per-change records |
| `retrieval_compression_v3_results.json` | Current pipeline (semantic retrieval + compression) | **3.90%** (366 of 9386 tokens saved) | Replayed from current compressor over the recorded per-query selections — identical, query sums and per-tool sums agree |
| `keyword_baseline_results.json` | Keyword retrieval recall@1/3/5 | **40.00 / 50.00 / 63.33** | All per-query hit flags and averages recomputed — internally consistent |
| `bm25_results.json` | BM25 retrieval recall@1/3/5 | **33.33 / 53.33 / 60.00** | Internally consistent |
| `semantic_results.json` | Semantic retrieval recall@1/3/5 | **63.33 / 90.00 / 93.33** | Internally consistent; selections identical to those inside the pipeline runs |

Conditions attached to this class:

* Dataset: `data/tools/tools.json` — **100 synthetic development tools**.
* Queries: `data/queries/test_queries.json` — **30 hand-written development
  queries**, identical (same texts, same order) in every query-driven result
  file in this directory.
* These are *development-set* results: the retrieval methods were designed and
  tuned while these queries were visible. They measure internal consistency of
  the pipeline, not out-of-sample performance.
* The current compressor's behavior is guarded by the test suite
  (`tests/test_schema_compressor_v2*.py`), so the 3.50% behavior is pinned by
  automated tests.
* Latency figures in the retrieval files are machine-specific and indicative
  only.

---

## 3. Historical / superseded results

| Result file(s) | Recorded metric | Status |
|---|---|---|
| `compression_v2_results.json` | V2 corpus compression **5.07%** (311 of 6137; 71 tools reduced) | Superseded by 3.50% |
| `retrieval_compression_results.json` | Pipeline **5.60%** (526 of 9386) | Superseded by 3.90% |
| `combined_pipeline_evaluation.json` | Pipeline **5.60%** + retrieval recalls | Superseded by 3.90%; duplicates the run above with a different schema |
| `compression_v2_audit.json` | Audit of **85** description changes | Describes the intermediate compressor generation |
| `compression_v2_safety_report.json` | 100 tools checked, 14 warnings | Same generation |
| `compression_v2_semantic_review.json`, `compression_v2_semantic_review_summary.json` | 85 changes reviewed, 71 unique tools | Same generation |
| `compression_v2_risk_classification.json` | 85 changes triaged; **85/85 manual reviews pending; 0 semantic-equivalence verifications** | Same generation; openly incomplete |

These files are **kept unchanged on purpose** (audit trail). They are not
wrong arithmetic — they are results of a code state that no longer exists.

### Why the historical numbers differ from the current numbers

The difference is caused **only by the compressor becoming more
conservative** — not by retrieval changes and not by any error:

* The historical 5.07% / 5.60% figures were produced by an **intermediate
  version of `schema_compressor_v2.py` that was never committed to git**.
  During the audit this missing state was reconstructed (old committed logic
  plus three preserved descriptions: `search_customers/name`,
  `list_products/category`, `update_ticket/description`). The reconstruction
  reproduced the historical files **exactly — all 100 per-tool token numbers
  and the 526-token pipeline total matched with zero mismatches**.
* The *committed* older revision (`20599eb`) actually yields 5.51% on the
  corpus and 6.29% on the pipeline — figures that were never recorded as
  results. This proves no git revision can regenerate 5.07% / 5.60%.
* After the semantic review (2026-10-11, 13:03–13:27), the compressor was
  edited (14:49) to preserve **15** optional-property descriptions instead of
  the intermediate 3. That edit reduced savings by design:
  corpus 5.07% → 3.50% (−96 tokens) and pipeline 5.60% → 3.90% (−160
  tokens), and reduced the change count from 85 to 72.
* The audit also confirmed that **retrieval did not change between the two
  pipeline runs**: both selected the identical set of tools for all 30
  queries. The entire 5.60% → 3.90% delta is attributable to the compressor.

---

## 4. Reproducibility facts

* Current results (Section 2) reproduce exactly from the repository at
  commit `f769aa4` or later, with `data/tools/tools.json` and
  `data/queries/test_queries.json` unchanged.
* Token counting for every compression number: `tiktoken` `cl100k_base`,
  compact JSON serialization (`ensure_ascii=False`, separators `(",", ":")`).
* Semantic retrieval model: `sentence-transformers/all-MiniLM-L6-v2`
  (defined in `src/retrieval/semantic_retriever.py`).
* Known environment gap: `requirements.txt` pins most packages but currently
  **omits `tiktoken`**, and the embedding-model revision is not pinned.
  Treat these as items for the provenance retrofit (Phase B).

---

## 5. Independent benchmark status — read this before quoting any number

**None of the results in this directory represents independent benchmark
performance.** Every result was produced on the same synthetic 100-tool
development dataset with the same 30 hand-written development queries, and
the retrieval methods were tuned against those very queries.

**The real MCP benchmark dataset — 117 tools extracted from 19 servers and 2
repositories under `data/independent_benchmark/` (with dated, SHA-256-verified
backups in `data/independent_benchmark/backup/`) — has not yet been evaluated
by any experiment in this directory.** It postdates every result file here
(2026-10-15 vs 2026-10-11). Until retrieval and compression are evaluated on
that dataset with pre-reviewed queries, all numbers above are development-set
figures only and must be labeled as such in any report or presentation.

---

## 6. Experiment generation table

| # | When (2026) | Result file(s) | Generator script | Compressor state | Headline | Class |
|---|---|---|---|---|---|---|
| 1 | Oct 11, 00:18 | `keyword_baseline_results.json`, `bm25_results.json`, `semantic_results.json` | `evaluate_retrieval.py` | — (retrieval only) | R@1/3/5: 40/50/63.33, 33.33/53.33/60, 63.33/90/93.33 | Verified (dev set) |
| 2 | Oct 11, 00:49 / 12:49 | `compression_results.json` | `evaluate_compression.py` | V1 (`schema_compressor.py`) | 2.10% | Verified (dev set) |
| 3 | Oct 11, 01:00–01:18 | `schema_token_analysis.json`, `required_property_descriptions.json` | `analyze_schema_tokens.py`, `analyze_required_descriptions.py` | — (analysis) | token/component survey | Supporting analysis |
| 4 | Oct 11, 10:32–10:57 | `optional_description_review.json` | `audit_compression_v2.py`, `review_optional_descriptions.py` | intermediate | preservation candidates | Historical (process record) |
| 5 | Oct 11, 11:53 | `compression_v2_results.json`, `compression_v2_audit.json`, `compression_v2_safety_report.json` | `evaluate_compression_v2.py`, `audit_compression_v2.py`, `validate_compression_safety.py` | **intermediate (uncommitted)** | 5.07% | **Historical / superseded** |
| 6 | Oct 11, 12:11 / 12:50 | `retrieval_compression_results.json`, `combined_pipeline_evaluation.json` | `evaluate_retrieval_compression.py`, `evaluate_combined_pipeline.py` | **intermediate (uncommitted)** | 5.60% | **Historical / superseded** |
| 7 | Oct 11, 13:03–13:27 | `compression_v2_semantic_review.json` (+`_summary`), `compression_v2_risk_classification.json` | `evaluate_semantic_safety.py`, `summarize_semantic_review.py`, `classify_semantic_risks.py` | intermediate (85 changes) | review of 85 changes; 85/85 manual reviews pending | **Historical / superseded** |
| 8 | Oct 11, 14:38 | `removed_description_schema_inspection.json` | `inspect_removed_descriptions.py` | intermediate | 14 removed descriptions inspected | Historical (process record) |
| 9 | Oct 11, 14:49 | — (code edit, committed Oct 12 as `f769aa4`) | — | **current** (15 preserved descriptions) | — | — |
| 10 | Oct 11, 14:54 | `compression_v3_results.json` | `evaluate_compression_v3.py` | **current** | 3.50% | **Verified (dev set)** |
| 11 | Oct 11, 16:55 | `retrieval_compression_v3_results.json` | `evaluate_retrieval_compression_v3.py` | **current** | 3.90% | **Verified (dev set)** |

---

## 7. Rules for using this directory

1. Quote Section 2 figures as "development-set results"; never present them as
   independent benchmark performance (Section 5).
2. Quote 5.07% / 5.60% only when describing history, always labeled
   "superseded intermediate state, not reproducible from git."
3. Do not modify, delete, rename, or regenerate any file here without an
   explicit, separately approved task.
4. New results must record provenance (git SHA, dataset hash, tokenizer,
   model, date, configuration) — pending the Phase B retrofit.
