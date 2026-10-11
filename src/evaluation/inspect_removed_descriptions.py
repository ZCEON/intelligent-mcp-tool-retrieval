import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"

CLASSIFICATION_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_risk_classification.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "removed_description_schema_inspection.json"
)


def load_tools():
    with TOOLS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("tools")

    if not isinstance(data, list):
        raise ValueError(
            "tools.json must contain a list of tools."
        )

    return {
        tool["name"]: tool
        for tool in data
        if isinstance(tool, dict) and "name" in tool
    }


def main():
    tools = load_tools()

    with CLASSIFICATION_FILE.open("r", encoding="utf-8") as file:
        classification = json.load(file)

    records = classification.get("records", [])

    removed_records = [
        record
        for record in records
        if record.get("transformation") == "removed"
    ]

    inspections = []

    for record in removed_records:
        tool_name = record.get("tool_name")
        property_name = record.get("property_name")

        tool = tools.get(tool_name)

        if tool is None:
            inspections.append(
                {
                    "tool_name": tool_name,
                    "property_name": property_name,
                    "inspection_error": "Tool not found in dataset.",
                }
            )
            continue

        input_schema = tool.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        property_schema = properties.get(property_name)

        if property_schema is None:
            inspections.append(
                {
                    "tool_name": tool_name,
                    "property_name": property_name,
                    "inspection_error": (
                        "Property not found in the original schema."
                    ),
                }
            )
            continue

        inspection = {
            "tool_name": tool_name,
            "tool_description": tool.get("description"),
            "property_name": property_name,
            "original_description": property_schema.get("description"),
            "required": property_name
            in input_schema.get("required", []),
            "property_schema": property_schema,
            "required_properties": input_schema.get("required", []),
            "schema_level_constraints": {
                key: value
                for key, value in input_schema.items()
                if key not in ("properties", "required", "type")
            },
            "preliminary_risk_category": record.get(
                "preliminary_risk_category"
            ),
            "manual_review_status": "pending",
        }

        inspections.append(inspection)

    report = {
        "removed_descriptions_found": len(removed_records),
        "inspections": inspections,
        "limitations": [
            (
                "Schema inspection reveals declared constraints but "
                "does not prove actual tool runtime behavior."
            ),
            (
                "Descriptions must be evaluated in the context of "
                "the full tool purpose and schema."
            ),
            (
                "No manual review is marked complete by this script."
            ),
        ],
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("Removed Description Schema Inspection")
    print("=" * 42)
    print(f"Descriptions found: {len(removed_records)}")
    print(f"Inspection records: {len(inspections)}")

    errors = sum(
        "inspection_error" in record
        for record in inspections
    )

    print(f"Inspection errors: {errors}")
    print()
    print(f"Report saved to: {OUTPUT_FILE}")

    for item in inspections:
        print(
            f"- {item['tool_name']}.{item['property_name']}"
            if "inspection_error" not in item
            else (
                f"- ERROR: {item['tool_name']}."
                f"{item['property_name']}: "
                f"{item['inspection_error']}"
            )
        )


if __name__ == "__main__":
    main()
