import copy
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.compression.schema_compressor_v2 import compress_schema_v2


TOOLS_PATH = PROJECT_ROOT / "data" / "tools" / "tools.json"
OUTPUT_PATH = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_semantic_review.json"
)


def load_tools():
    with TOOLS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def classify_change(original_description, compressed_description):
    """Classify how a description changed."""
    if original_description == compressed_description:
        return "unchanged"

    if compressed_description is None:
        return "removed"

    return "shortened"


def structural_signature(property_schema):
    """
    Everything about a property except its description.

    Used to verify automatically that a transformation did not
    alter types, enums, or other constraints.
    """
    return {
        key: value
        for key, value in property_schema.items()
        if key != "description"
    }


def other_constraints(property_schema):
    """Constraint keys besides type and description."""
    return sorted(
        key
        for key in property_schema
        if key not in ("type", "description")
    )


def assess_risk(required, has_enum, transformation, compressed_description):
    """
    Automated risk hints.

    These are not semantic judgments; they indicate what a
    human reviewer should verify.
    """
    if not has_enum and required:
        return (
            "Verify that the shortened description still conveys "
            "the meaning needed to supply this required argument."
        )

    if has_enum:
        return (
            "Lower risk: allowed values are documented by the enum. "
            "Confirm the remaining schema still communicates purpose."
        )

    if transformation == "removed":
        return (
            "Verify that the property name and tool context alone "
            "communicate the intended meaning of this optional input."
        )

    return (
        "Verify that no unique behavioral or formatting information "
        "was lost in the change."
    )


def main():
    tools = load_tools()

    changes = []
    properties_checked = 0
    unchanged_descriptions = 0

    for tool in tools:
        original_tool = copy.deepcopy(tool)
        compressed_tool = compress_schema_v2(copy.deepcopy(tool))

        tool_name = original_tool.get("name", "unknown_tool")

        original_schema = original_tool.get("inputSchema", {})
        compressed_schema = compressed_tool.get("inputSchema", {})

        original_properties = original_schema.get("properties", {})
        compressed_properties = compressed_schema.get("properties", {})
        required_fields = set(original_schema.get("required", []))

        for property_name, original_property in original_properties.items():
            properties_checked += 1

            compressed_property = compressed_properties.get(property_name, {})

            original_description = original_property.get("description")
            compressed_description = compressed_property.get("description")

            transformation = classify_change(
                original_description,
                compressed_description,
            )

            if transformation == "unchanged":
                unchanged_descriptions += 1
                continue

            required = property_name in required_fields
            has_enum = "enum" in original_property
            structure_preserved = (
                structural_signature(original_property)
                == structural_signature(compressed_property)
            )

            changes.append({
                "tool_name": tool_name,
                "property_name": property_name,
                "transformation": transformation,
                "original_description": original_description,
                "compressed_description": compressed_description,
                "required": required,
                "property_type": original_property.get("type"),
                "has_enum": has_enum,
                "other_constraints": other_constraints(original_property),
                "automated_structural_check": structure_preserved,
                "risk_assessment": "not_assessed",
                "risk_hint": assess_risk(
                    required,
                    has_enum,
                    transformation,
                    compressed_description,
                ),
                "manual_review_status": "pending",
            })

    removed = sum(
        c["transformation"] == "removed" for c in changes
    )
    shortened = sum(
        c["transformation"] == "shortened" for c in changes
    )
    structural_passed = sum(
        c["automated_structural_check"] for c in changes
    )

    output = {
        "summary": {
            "tools_checked": len(tools),
            "properties_checked": properties_checked,
            "total_changes": len(changes),
            "removed_count": removed,
            "shortened_count": shortened,
            "unchanged_descriptions": unchanged_descriptions,
            "automated_structural_checks_passed": structural_passed,
            "automated_structural_checks_total": len(changes),
            "manual_review": {
                "reviewed": 0,
                "pending": len(changes),
            },
        },
        "verification_levels": {
            "automatically_verified": (
                "Structural comparison confirms property names, types, "
                "enums, and constraints are unchanged."
            ),
            "manually_reviewed": (
                "A human reviewer confirms the description change does "
                "not remove information needed for correct tool use. "
                "No changes have been reviewed yet."
            ),
            "not_yet_verified": (
                "Semantic equivalence of original and compressed "
                "descriptions has not been established for any change."
            ),
        },
        "changes": changes,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print("\nSemantic Safety Review of Schema Compression V2")
    print("=" * 52)
    print(f"Tools checked:            {len(tools)}")
    print(f"Properties checked:       {properties_checked}")
    print(f"Description changes:      {len(changes)}")
    print(f"  Removed:                {removed}")
    print(f"  Shortened:              {shortened}")
    print(f"Unchanged descriptions:   {unchanged_descriptions}")
    print(
        f"Structural checks passed: "
        f"{structural_passed}/{len(changes)}"
    )
    print(f"Manual review pending:    {len(changes)}")
    print(f"\nReport saved to:\n{OUTPUT_PATH}")

    print("\nNOTE:")
    print(
        "Automated checks verify schema structure only. "
        "Semantic equivalence requires manual review."
    )


if __name__ == "__main__":
    main()
