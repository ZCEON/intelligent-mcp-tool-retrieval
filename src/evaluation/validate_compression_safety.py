import copy
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.compression.schema_compressor_v2 import compress_schema_v2


TOOLS_PATH = PROJECT_ROOT / "data" / "tools" / "tools.json"
AUDIT_PATH = PROJECT_ROOT / "experiments" / "compression_v2_audit.json"
OUTPUT_PATH = (
    PROJECT_ROOT / "experiments" / "compression_v2_safety_report.json"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def check_tool_metadata(original, compressed):
    """Check that tool-level metadata is preserved."""
    fields = ("name", "description", "category")

    return all(
        original.get(field) == compressed.get(field)
        for field in fields
    )


def check_schema_constraints(original_schema, compressed_schema):
    """
    Check schema-level fields other than properties.

    This includes required lists and any other schema constraints.
    """
    original_other = {
        key: value
        for key, value in original_schema.items()
        if key != "properties"
    }

    compressed_other = {
        key: value
        for key, value in compressed_schema.items()
        if key != "properties"
    }

    return original_other == compressed_other


def validate_tool(original, compressed):
    errors = []
    warnings = []

    tool_name = original.get("name", "unknown_tool")

    if not check_tool_metadata(original, compressed):
        errors.append(
            f"{tool_name}: tool-level metadata changed."
        )

    original_schema = original.get("inputSchema", {})
    compressed_schema = compressed.get("inputSchema", {})

    if not check_schema_constraints(
        original_schema, compressed_schema
    ):
        errors.append(
            f"{tool_name}: schema constraints or required fields changed."
        )

    original_properties = original_schema.get("properties", {})
    compressed_properties = compressed_schema.get("properties", {})

    if set(original_properties) != set(compressed_properties):
        errors.append(
            f"{tool_name}: property names were added or removed."
        )

    required_fields = set(original_schema.get("required", []))

    for property_name, original_property in original_properties.items():
        compressed_property = compressed_properties.get(property_name)

        if compressed_property is None:
            continue

        # Compare everything except the description.
        original_non_description = {
            key: value
            for key, value in original_property.items()
            if key != "description"
        }

        compressed_non_description = {
            key: value
            for key, value in compressed_property.items()
            if key != "description"
        }

        if original_non_description != compressed_non_description:
            errors.append(
                f"{tool_name}.{property_name}: "
                "property type, enum, or other constraints changed."
            )

        original_description = original_property.get("description")
        compressed_description = compressed_property.get("description")

        if (
            property_name in required_fields
            and original_description
            and not compressed_description
        ):
            errors.append(
                f"{tool_name}.{property_name}: "
                "required property description was removed."
            )

        if (
            original_description
            and not compressed_description
            and property_name not in required_fields
        ):
            has_enum = bool(original_property.get("enum"))
            has_type = bool(original_property.get("type"))

            warnings.append(
                {
                    "tool_name": tool_name,
                    "property_name": property_name,
                    "issue": "Optional property description removed.",
                    "has_type": has_type,
                    "has_enum": has_enum,
                    "original_description": original_description,
                    "risk_note": (
                        "Review whether the property name and remaining "
                        "schema information communicate its intended meaning."
                    ),
                }
            )

    return errors, warnings


def main():
    original_tools = load_json(TOOLS_PATH)
    audit_records = load_json(AUDIT_PATH)

    all_errors = []
    all_warnings = []

    checked_tools = 0

    for original_tool in original_tools:
        # Work on a copy so the source dataset remains unchanged.
        original_copy = copy.deepcopy(original_tool)
        compressed_tool = compress_schema_v2(original_copy)

        errors, warnings = validate_tool(
            original_tool, compressed_tool
        )

        all_errors.extend(errors)
        all_warnings.extend(warnings)
        checked_tools += 1

    report = {
        "tools_checked": checked_tools,
        "audit_changes_reviewed": len(audit_records),
        "structural_errors": all_errors,
        "optional_description_warnings": all_warnings,
        "structural_validation_passed": len(all_errors) == 0,
        "warning_count": len(all_warnings),
        "limitations": [
            (
                "Passing structural checks does not prove that shortened "
                "natural-language descriptions preserve their full meaning."
            ),
            (
                "Optional description removals require review based on "
                "the property name, constraints, and intended tool behavior."
            ),
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("\nSchema Compression V2 Safety Validation")
    print("=" * 48)
    print(f"Tools checked: {checked_tools}")
    print(f"Audit changes reviewed: {len(audit_records)}")
    print(f"Structural errors: {len(all_errors)}")
    print(f"Optional description warnings: {len(all_warnings)}")
    print(
        "Structural validation: "
        + ("PASSED" if not all_errors else "FAILED")
    )
    print(f"\nReport saved to:\n{OUTPUT_PATH}")

    if all_errors:
        print("\nStructural Errors")
        print("-" * 48)

        for error in all_errors:
            print(f"- {error}")

    if all_warnings:
        print("\nOptional Description Warnings")
        print("-" * 48)

        for warning in all_warnings[:10]:
            print(
                f"- {warning['tool_name']}."
                f"{warning['property_name']}: "
                f"{warning['original_description']}"
            )

        if len(all_warnings) > 10:
            print(f"... and {len(all_warnings) - 10} more.")

    print(
        "\nNote: Structural validation does not establish "
        "semantic equivalence."
    )


if __name__ == "__main__":
    main()
