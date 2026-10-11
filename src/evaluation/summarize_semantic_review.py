import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_semantic_review.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_semantic_review_summary.json"
)


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        report = json.load(file)

    # Support either a list of records or a report containing a list.
    if isinstance(report, list):
        records = report
    elif isinstance(report, dict):
        records = None

        for key in ("changes", "records", "review_items"):
            if isinstance(report.get(key), list):
                records = report[key]
                break

        if records is None:
            raise ValueError(
                "Could not find the review records. "
                "Check the top-level keys in the JSON report."
            )
    else:
        raise ValueError("Unexpected semantic review report format.")

    transformation_counts = Counter()
    review_status_counts = Counter()
    tool_counts = Counter()
    constraint_counts = Counter()

    structural_failures = []
    missing_fields = []
    review_items = []

    required_fields = {
        "tool_name",
        "property_name",
        "transformation",
        "original_description",
        "compressed_description",
        "required",
        "property_type",
        "has_enum",
        "other_constraints",
        "automated_structural_check",
        "manual_review_status",
    }

    for index, record in enumerate(records, start=1):
        missing = sorted(required_fields - set(record.keys()))

        if missing:
            missing_fields.append(
                {
                    "record_number": index,
                    "missing_fields": missing,
                }
            )

        transformation_counts[
            record.get("transformation", "unknown")
        ] += 1

        review_status_counts[
            record.get("manual_review_status", "unknown")
        ] += 1

        tool_counts[record.get("tool_name", "unknown")] += 1

        for constraint in record.get("other_constraints", []):
            constraint_counts[constraint] += 1

        if record.get("automated_structural_check") is not True:
            structural_failures.append(
                {
                    "tool_name": record.get("tool_name"),
                    "property_name": record.get("property_name"),
                }
            )

        review_items.append(
            {
                "tool_name": record.get("tool_name"),
                "property_name": record.get("property_name"),
                "transformation": record.get("transformation"),
                "required": record.get("required"),
                "property_type": record.get("property_type"),
                "has_enum": record.get("has_enum"),
                "other_constraints": record.get(
                    "other_constraints", []
                ),
                "original_description": record.get(
                    "original_description"
                ),
                "compressed_description": record.get(
                    "compressed_description"
                ),
                "automated_structural_check": record.get(
                    "automated_structural_check"
                ),
                "manual_review_status": record.get(
                    "manual_review_status"
                ),
                "risk_assessment": record.get(
                    "risk_assessment", "not_assessed"
                ),
                "risk_hint": record.get("risk_hint"),
            }
        )

    summary = {
        "total_changes": len(records),
        "transformation_counts": dict(transformation_counts),
        "manual_review_status_counts": dict(review_status_counts),
        "unique_tools_affected": len(tool_counts),
        "constraint_counts": dict(constraint_counts),
        "structural_failure_count": len(structural_failures),
        "structural_failures": structural_failures,
        "records_missing_required_fields": missing_fields,
        "review_items": review_items,
        "limitations": [
            (
                "Automated structural checks do not prove semantic "
                "equivalence."
            ),
            (
                "Risk assessments must be based on the meaning of each "
                "description and its schema context."
            ),
            (
                "A passing manual review is not equivalent to a successful "
                "real-world tool execution test."
            ),
        ],
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    print("Semantic Review Summary")
    print("=" * 40)
    print(f"Total changes: {len(records)}")
    print(f"Transformation counts: {dict(transformation_counts)}")
    print(f"Manual review statuses: {dict(review_status_counts)}")
    print(f"Unique tools affected: {len(tool_counts)}")
    print(f"Structural failures: {len(structural_failures)}")
    print(f"Records missing fields: {len(missing_fields)}")
    print()
    print(f"Summary saved to: {OUTPUT_FILE}")

    if len(records) != 85:
        print(
            "WARNING: Expected 85 changes. "
            "Check the input report and its record count."
        )

    if structural_failures:
        print(
            "WARNING: Some records failed their recorded "
            "structural checks."
        )

    if missing_fields:
        print(
            "WARNING: Some records are missing expected fields."
        )


if __name__ == "__main__":
    main()
