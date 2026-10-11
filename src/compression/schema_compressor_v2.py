import copy
import re


# V2 uses deterministic, conservative transformations.
# A description is shortened only when its meaning matches
# the property name and the approved identifier pattern.

IDENTIFIER_DESCRIPTION_PATTERN = re.compile(
    r"^Unique identifier of the ([a-z][a-z ]*?)\.?$",
    re.IGNORECASE,
)

# Optional-property descriptions that document tool behavior
# or disambiguate a property name, reviewed explicitly.
PRESERVED_OPTIONAL_DESCRIPTIONS = {
    # Existing descriptions preserved by V2
    ("search_customers", "name"),
    ("list_products", "category"),
    ("update_ticket", "description"),

    # Additional descriptions preserved after semantic review
    ("update_order", "shipping_address"),
    ("search_customers", "email"),
    ("create_customer", "phone"),
    ("update_customer", "email"),
    ("update_customer", "phone"),
    ("update_invoice", "due_date"),
    ("update_product", "name"),
    ("update_product", "price"),
    ("update_event", "title"),
    ("update_event", "start_time"),
    ("update_lead", "status"),
    ("update_contact", "phone"),
    ("update_user", "email"),
}


def get_short_identifier_description(
    property_name,
    description,
):
    """
    Shorten a standard identifier description only when
    the property name matches the entity in the description.

    Example:
        property_name: order_id
        description: Unique identifier of the order.
        result: Order ID.

    Return None when the description does not match safely.
    """
    if not isinstance(property_name, str):
        return None

    if not isinstance(description, str):
        return None

    match = IDENTIFIER_DESCRIPTION_PATTERN.fullmatch(
        description.strip()
    )

    if not match:
        return None

    entity = match.group(1).strip()
    expected_property_name = f"{entity.replace(' ', '_')}_id"

    if property_name.lower() != expected_property_name.lower():
        return None

    return f"{entity.title()} ID."


def compress_schema_v2(tool):
    """
    Compress an MCP tool schema using conservative V2 rules.

    Preserves:
    - Tool name, description, and category
    - Property names and types
    - Required-field lists
    - Enum values and other constraints
    - Required-property descriptions, except for
      approved identifier-description transformations

    Optional-property descriptions are removed as in V1.
    """
    compressed_tool = copy.deepcopy(tool)

    input_schema = compressed_tool.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))

    for property_name, property_schema in properties.items():
        description = property_schema.get("description")

        if property_name not in required_fields:
            tool_name = compressed_tool.get("name")

            preservation_key = (tool_name, property_name)

            if preservation_key not in PRESERVED_OPTIONAL_DESCRIPTIONS:
                property_schema.pop("description", None)
            continue

        if description:
            replacement = get_short_identifier_description(
                property_name,
                description,
            )

            if replacement:
                property_schema["description"] = replacement

    return compressed_tool


if __name__ == "__main__":
    example_tool = {
        "name": "refund_order",
        "description": "Refund an existing customer order.",
        "category": "orders",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Unique identifier of the order.",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for requesting the refund.",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes about the refund.",
                },
            },
            "required": ["order_id", "reason"],
        },
    }

    result = compress_schema_v2(example_tool)

    print("Original schema:")
    print(example_tool)

    print("\nCompressed schema V2:")
    print(result)
