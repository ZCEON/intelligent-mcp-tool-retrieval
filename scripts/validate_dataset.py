import json
from pathlib import Path


# ------------------------------------------------------------
# File paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent

TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"
QUERIES_FILE = PROJECT_ROOT / "data" / "queries" / "test_queries.json"


# ------------------------------------------------------------
# Load JSON files
# ------------------------------------------------------------

def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


# ------------------------------------------------------------
# Validate tools
# ------------------------------------------------------------

def validate_tools(tools):
    print("\nChecking tools...")

    errors = []

    if not isinstance(tools, list):
        errors.append("tools.json must contain a list.")
        return errors

    tool_names = []

    for index, tool in enumerate(tools):

        # Required top-level fields
        required_fields = [
            "name",
            "description",
            "category",
            "inputSchema"
        ]

        for field in required_fields:
            if field not in tool:
                errors.append(
                    f"Tool #{index + 1} is missing '{field}'."
                )

        # Tool name
        if "name" in tool:
            name = tool["name"]

            if name in tool_names:
                errors.append(
                    f"Duplicate tool name: {name}"
                )

            tool_names.append(name)

            if not name.islower():
                errors.append(
                    f"Tool name is not lowercase: {name}"
                )

            if " " in name:
                errors.append(
                    f"Tool name contains spaces: {name}"
                )

        # Description
        if "description" in tool:
            if not isinstance(tool["description"], str):
                errors.append(
                    f"Invalid description for tool: {tool.get('name')}"
                )

        # Input schema
        if "inputSchema" in tool:
            schema = tool["inputSchema"]

            if schema.get("type") != "object":
                errors.append(
                    f"Invalid schema type for: {tool.get('name')}"
                )

            if "properties" not in schema:
                errors.append(
                    f"Missing properties in: {tool.get('name')}"
                )

            if "required" not in schema:
                errors.append(
                    f"Missing required list in: {tool.get('name')}"
                )

    print(f"Tools checked: {len(tools)}")

    return errors


# ------------------------------------------------------------
# Validate queries
# ------------------------------------------------------------

def validate_queries(queries, valid_tool_names):
    print("\nChecking test queries...")

    errors = []

    if not isinstance(queries, list):
        errors.append(
            "test_queries.json must contain a list."
        )
        return errors

    query_ids = []

    for index, query in enumerate(queries):

        required_fields = [
            "id",
            "query",
            "expected_tools",
            "difficulty"
        ]

        for field in required_fields:
            if field not in query:
                errors.append(
                    f"Query #{index + 1} is missing '{field}'."
                )

        # Query ID
        if "id" in query:
            query_id = query["id"]

            if query_id in query_ids:
                errors.append(
                    f"Duplicate query ID: {query_id}"
                )

            query_ids.append(query_id)

        # Query text
        if "query" in query:
            if not isinstance(query["query"], str):
                errors.append(
                    f"Invalid query text: {query.get('id')}"
                )

            elif not query["query"].strip():
                errors.append(
                    f"Empty query: {query.get('id')}"
                )

        # Expected tools
        if "expected_tools" in query:
            expected_tools = query["expected_tools"]

            if not isinstance(expected_tools, list):
                errors.append(
                    f"expected_tools must be a list: {query.get('id')}"
                )

            else:
                for tool_name in expected_tools:
                    if tool_name not in valid_tool_names:
                        errors.append(
                            f"Query {query.get('id')} references "
                            f"unknown tool: {tool_name}"
                        )

        # Difficulty
        if "difficulty" in query:
            valid_difficulties = {
                "easy",
                "medium",
                "hard"
            }

            if query["difficulty"] not in valid_difficulties:
                errors.append(
                    f"Invalid difficulty in query: {query.get('id')}"
                )

    print(f"Queries checked: {len(queries)}")

    return errors


# ------------------------------------------------------------
# Main validation
# ------------------------------------------------------------

def main():

    print("=" * 60)
    print("MCP TOOL RETRIEVAL DATASET VALIDATION")
    print("=" * 60)

    # Check files exist
    if not TOOLS_FILE.exists():
        print("\nERROR: Tools file not found:")
        print(TOOLS_FILE)
        return

    if not QUERIES_FILE.exists():
        print("\nERROR: Queries file not found:")
        print(QUERIES_FILE)
        return

    # Load files
    try:
        tools = load_json(TOOLS_FILE)
        queries = load_json(QUERIES_FILE)

    except json.JSONDecodeError as error:
        print("\nERROR: Invalid JSON")
        print(error)
        return

    # Validate tools
    tool_errors = validate_tools(tools)

    valid_tool_names = {
        tool["name"]
        for tool in tools
        if "name" in tool
    }

    # Validate queries
    query_errors = validate_queries(
        queries,
        valid_tool_names
    )

    all_errors = tool_errors + query_errors

    # Final result
    print("\n" + "=" * 60)

    if all_errors:
        print("DATASET VALIDATION FAILED")
        print("=" * 60)

        print("\nProblems found:")

        for error in all_errors:
            print(f"- {error}")

    else:
        print("DATASET VALIDATION PASSED")
        print("=" * 60)

        print(f"\nTotal tools: {len(tools)}")
        print(f"Total queries: {len(queries)}")

        print("\nDataset is ready for retrieval experiments.")


if __name__ == "__main__":
    main()
