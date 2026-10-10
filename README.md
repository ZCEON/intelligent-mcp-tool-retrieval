# Intelligent MCP Tool Retrieval and Safe Schema Compression

## Problem

As AI agents use more MCP (Model Context Protocol) tools, providing all available tools and their complete schemas to an LLM can create a large context.

For example, an enterprise AI agent may have hundreds of available tools, while a user's request may require only a few of them.

Providing unnecessary tools and schema information can increase:

* Context/token usage
* Processing latency
* LLM cost
* Complexity of tool selection

This project investigates a focused approach to reduce unnecessary tool and schema information while maintaining accurate tool selection.

## Objective

The main objective of this project is to develop an intelligent pipeline that:

1. Retrieves the most relevant MCP tools for a given user request.
2. Compresses the schemas of the selected tools by removing unnecessary information.
3. Preserves the information required for correct tool execution.
4. Measures the effect of retrieval and schema compression on context usage, latency, and tool-selection accuracy.

This project is designed as a focused research and engineering MVP, with an emphasis on measurable evaluation, practical implementation, and reproducibility.

## Research Question

**Can semantic tool retrieval and task-aware schema compression reduce the context required by enterprise MCP agents while maintaining accurate tool selection?**

## Planned Metrics

The system will be evaluated using the following metrics:

### Tool Retrieval

* Recall@1
* Recall@3
* Recall@5

### Context Efficiency

* Original token count
* Compressed token count
* Token reduction percentage

### Performance

* Retrieval latency
* Schema compression latency
* Total processing latency

### Safety

* Required-field preservation rate
* Successful tool-call rate

Actual results will be added after experiments are completed.

## Technology Stack

| Component            | Technology            |
| -------------------- | --------------------- |
| Programming Language | Python                |
| API                  | FastAPI               |
| Embeddings           | Sentence Transformers |
| Vector Search        | FAISS                 |
| Data Format          | JSON                  |
| Evaluation           | Python, pandas        |
| Testing              | pytest                |
| Containerization     | Docker                |
| Version Control      | Git, GitHub           |
| LLM                  | API / Local Model     |
| Documentation        | Markdown              |

## Project Structure

```
├── data/
│   ├── tools/
│   │   └── tools.json             # Tool registry
│   └── queries/
│       └── test_queries.json      # Evaluation queries
│
├── src/
│   ├── retrieval/                 # Tool retrieval logic
│   ├── compression/               # Schema compression
│   ├── evaluation/                # Evaluation metrics
│   └── api/                       # FastAPI service
│
├── tests/                         # pytest test suite
├── experiments/                   # Experiment scripts and configs
├── notebooks/                     # Analysis notebooks
├── docs/                          # Documentation
├── docker/                        # Docker build files
│
├── requirements.txt
└── README.md
```

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

## Project Status

**Status:** Initial Development

The project is currently starting with dataset design and baseline implementation.

## Planned Development Stages

1. Dataset Design
2. Baseline Implementation
3. Keyword-based Tool Retrieval
4. Semantic Tool Retrieval
5. Retrieval Evaluation
6. Schema Analysis
7. Safe Schema Compression
8. Compression and Safety Evaluation
9. LLM Integration
10. FastAPI Service
11. Dockerization
12. Final Evaluation and Documentation
