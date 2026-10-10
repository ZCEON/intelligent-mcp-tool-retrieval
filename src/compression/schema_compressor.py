import copy


def compress_schema(tool):
    """
    Conservatively compress an MCP tool schema.

    Preserves:
    - Tool name, description, and category
    - Required properties and their descriptions
    - Property names and types
    - Enum values and other schema constraints
    - The required list

    Removes descriptions from optional properties only.
    """

    compressed_tool = copy.deepcopy(tool)

    input_schema = compressed_tool.get("inputSchema", {})

    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))

    for property_name, property_schema in properties.items():

        # Preserve descriptions for required properties.
        # Remove descriptions only from optional properties.
        if property_name not in required_fields:
            property_schema.pop("description", None)

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
                    "description": "Unique identifier of the order."
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for requesting the refund."
                },
                "notes": {
                    "type": "string",
                    "description": "Optional additional notes."
                }
            },
            "required": ["order_id", "reason"]
        }
    }

    compressed = compress_schema(example_tool)

    import json

    print("Original schema:")
    print(json.dumps(example_tool, indent=2))

    print("\nCompressed schema:")
    print(json.dumps(compressed, indent=2))
