import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REPORT_PATH = (
    PROJECT_ROOT
    / "experiments"
    / "compression_v2_safety_report.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "experiments"
    / "optional_description_review.json"
)


def main():
    with REPORT_PATH.open("r", encoding="utf-8") as file:
        report = json.load(file)

    warnings = report.get("optional_description_warnings", [])

    review_records = []

    for warning in warnings:
        tool_name = warning["tool_name"]
        property_name = warning["property_name"]
        original_description = warning["original_description"]

        review_records.append(
            {
                "tool_name": tool_name,
                "property_name": property_name,
                "original_description": original_description,
                "compressed_description": None,
                "review_status": "needs_manual_review",
                "information_loss_risk": "not_assessed",
                "reason": (
                    "Determine whether the original description contains "
                    "useful information not represented by the property "
                    "name or remaining schema constraints."
                ),
                "recommended_action": "review_before_accepting",
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(review_records, file, indent=2, ensure_ascii=False)

    print("\nOptional Description Review")
    print("=" * 45)
    print(f"Descriptions requiring review: {len(review_records)}")

    for index, record in enumerate(review_records, start=1):
        print(f"\n{index}. {record['tool_name']}.{record['property_name']}")
        print(f"   Original: {record['original_description']}")
        print("   Status: Needs manual review")

    print(f"\nReview report saved to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
