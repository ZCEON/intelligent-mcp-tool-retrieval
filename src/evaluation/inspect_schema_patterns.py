import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.keyword_retriever import load_tools


def inspect_schemas(tools):
    total_properties = 0
    required_properties = 0
    optional_properties = 0

    properties_with_descriptions = 0
    properties_without_descriptions = 0

    properties_with_enums = 0
    properties_with_additional_constraints = 0

    property_types = Counter()
    optional_description_examples = []

    for tool in tools:
        schema = tool.get("inputSchema", {})

        properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))

        for property_name, property_schema in properties.items():
            total_properties += 1

            is_required = property_name in required_fields
            has_description = bool(property_schema.get("description"))

            if is_required:
                required_properties += 1
            else:
                optional_properties += 1

            if has_description:
                properties_with_descriptions += 1
            else:
                properties_without_descriptions += 1

            property_type = property_schema.get("type", "not specified")
            property_types[str(property_type)] += 1

            if "enum" in property_schema:
                properties_with_enums += 1

            # Constraints other than descriptions and types.
            other_constraints = {
                key: value
                for key, value in property_schema.items()
                if key not in ("description", "type")
            }

            if other_constraints:
                properties_with_additional_constraints += 1

            # Collect examples of optional property descriptions.
            if (
                not is_required
                and has_description
                and len(optional_description_examples) < 10
            ):
                optional_description_examples.append({
                    "tool": tool.get("name", "unknown"),
                    "property": property_name,
                    "description": property_schema["description"],
                    "type": property_type,
                    "constraints": other_constraints,
                })

    print("\nSCHEMA PATTERN INSPECTION")
    print("=" * 40)

    print(f"Tools inspected: {len(tools)}")
    print(f"Total properties: {total_properties}")

    print("\nRequired vs Optional Properties")
    print("-" * 40)
    print(f"Required properties: {required_properties}")
    print(f"Optional properties: {optional_properties}")

    print("\nProperty Descriptions")
    print("-" * 40)
    print(f"With descriptions: {properties_with_descriptions}")
    print(f"Without descriptions: {properties_without_descriptions}")

    print("\nProperty Types and Constraints")
    print("-" * 40)
    print(f"Properties with enums: {properties_with_enums}")
    print(
        "Properties with additional constraints: "
        f"{properties_with_additional_constraints}"
    )

    print("\nProperty Type Distribution")
    print("-" * 40)

    for property_type, count in property_types.most_common():
        print(f"{property_type}: {count}")

    print("\nExamples of Optional Property Descriptions")
    print("-" * 40)

    if optional_description_examples:
        for example in optional_description_examples:
            print(f"\nTool: {example['tool']}")
            print(f"Property: {example['property']}")
            print(f"Description: {example['description']}")
            print(f"Type: {example['type']}")
            print(f"Other constraints: {example['constraints']}")
    else:
        print("No optional properties with descriptions were found.")


def main():
    tools = load_tools()
    inspect_schemas(tools)


if __name__ == "__main__":
    main()
