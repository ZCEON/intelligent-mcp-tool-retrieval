import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_semantic_review_summary.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_risk_classification.json"
)

IDENTIFIER_PATTERN = re.compile(
    r"^Unique identifier of the ([a-z][a-z ]*?)\.?$",
    re.IGNORECASE,
)


def classify_change(record):
    """
    Assign a preliminary semantic-risk category.

    This is a triage rule, not proof of semantic equivalence.
    All results remain pending manual review.
    """
    property_name = record.get("property_name", "unknown")
    transformation = record.get("transformation")
    original = record.get("original_description")
    compressed = record.get("compressed_description")
    has_enum = record.get("has_enum", False)
    constraints = record.get("other_constraints", [])

    # A failed structural check must be investigated first.
    if record.get("automated_structural_check") is not True:
        return {
            "risk_category": "needs_investigation",
            "reason": (
                "The recorded automated structural check did not pass."
            ),
        }

    # A shortened identifier description is low risk only when
    # the original description and replacement match the expected
    # entity and identifier pattern.
    if transformation == "shortened":
        match = IDENTIFIER_PATTERN.fullmatch(
            original.strip()
            if isinstance(original, str)
            else ""
        )

        if not match:
            return {
                "risk_category": "needs_investigation",
                "reason": (
                    "The original description does not match the "
                    "expected identifier-description pattern."
                ),
            }

        entity = match.group(1).strip()
        expected_property = f"{entity.replace(' ', '_')}_id"
        expected_description = f"{entity.title()} ID."

        if property_name.lower() != expected_property.lower():
            return {
                "risk_category": "needs_investigation",
                "reason": (
                    "The property name does not match the entity "
                    "named in the original description."
                ),
            }

        if compressed != expected_description:
            return {
                "risk_category": "needs_investigation",
                "reason": (
                    "The compressed description differs from the "
                    "expected identifier replacement."
                ),
            }

        return {
            "risk_category": "low_risk",
            "reason": (
                "The original and replacement descriptions identify "
                "the same entity identifier, and the replacement "
                "matches the expected rule."
            ),
        }

    # Unknown transformations must not be silently approved.
    if transformation != "removed":
        return {
            "risk_category": "needs_investigation",
            "reason": (
                "The transformation type is unknown or unsupported."
            ),
        }

    # Only descriptions actually removed should reach this branch.
    if compressed is not None:
        return {
            "risk_category": "needs_investigation",
            "reason": (
                "The record says the description was removed, but "
                "the compressed description is not null."
            ),
        }

    original_text = (
        original.strip().lower()
        if isinstance(original, str)
        else ""
    )

    # An enum can preserve a list of allowed values, but it does
    # not automatically preserve every aspect of a description.
    if has_enum or "enum" in constraints:
        return {
            "risk_category": "low_risk",
            "reason": (
                "The schema has an enum that documents allowed "
                "values. Confirm manually that the removed description "
                "adds no other behavioral information."
            ),
        }

    # These descriptions communicate a possible update or input
    # interpretation. Keep them for human review instead of
    # automatically approving their removal.
    if any(
        phrase in original_text
        for phrase in (
            "new ",
            "updated ",
            "partial",
            "filter",
            "format",
            "must ",
            "required format",
            "used to ",
            "used for ",
            "search ",
            "date and time",
        )
    ):
        return {
            "risk_category": "needs_investigation",
            "reason": (
                "The description may explain the argument's purpose, "
                "interpretation, or behavior. Check whether the "
                "property name and remaining schema preserve that "
                "information."
            ),
        }

    # A removal without an explicit constraint or a verified
    # semantic-preservation rule remains unverified.
    return {
        "risk_category": "needs_investigation",
        "reason": (
            "No explicit schema constraint or verified rule "
            "establishes that removing this description is safe."
        ),
    }


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    records = summary.get("review_items")

    if not isinstance(records, list):
        raise ValueError(
            "The summary must contain a 'review_items' list."
        )

    classified_records = []
    category_counts = Counter()

    for record in records:
        decision = classify_change(record)
        category = decision["risk_category"]
        category_counts[category] += 1

        classified_records.append(
            {
                **record,
                "preliminary_risk_category": category,
                "preliminary_risk_reason": decision["reason"],
                "manual_review_status": "pending",
                "semantic_equivalence_verified": False,
            }
        )

    report = {
        "total_changes": len(classified_records),
        "preliminary_category_counts": dict(category_counts),
        "manual_reviews_completed": 0,
        "manual_reviews_pending": len(classified_records),
        "semantic_equivalence_verified": 0,
        "classification_method": (
            "Rule-based preliminary triage using transformation type, "
            "identifier-description matching, and available schema "
            "constraints. This is not proof of semantic equivalence."
        ),
        "risk_categories": {
            "low_risk": (
                "The change appears to preserve its key meaning under "
                "the implemented rule; manual confirmation is still "
                "required."
            ),
            "needs_investigation": (
                "Available evidence is insufficient to approve the "
                "change automatically."
            ),
            "unsafe_to_remove": (
                "Reserved for a manually confirmed loss of important "
                "meaning. This automated script does not assign this "
                "category automatically."
            ),
        },
        "records": classified_records,
        "limitations": [
            (
                "Low risk is a preliminary assessment, not proof "
                "of semantic equivalence."
            ),
            (
                "Enum values preserve allowed-value information but "
                "may not preserve every instruction in a description."
            ),
            (
                "No change is marked manually reviewed by this script."
            ),
            (
                "Unsafe-to-remove decisions require evidence from "
                "manual schema inspection or tool-execution tests."
            ),
        ],
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("Preliminary Semantic Risk Classification")
    print("=" * 45)
    print(f"Total changes: {len(classified_records)}")
    print(f"Category counts: {dict(category_counts)}")
    print("Manual reviews completed: 0")
    print(f"Manual reviews pending: {len(classified_records)}")
    print("Semantic equivalence verified: 0")
    print()
    print(f"Report saved to: {OUTPUT_FILE}")

    if len(classified_records) != 85:
        print(
            "WARNING: Expected 85 changes. Inspect the input report."
        )


if __name__ == "__main__":
    main()
