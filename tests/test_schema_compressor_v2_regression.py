import copy
import json
from pathlib import Path

import pytest

from src.compression.schema_compressor_v2 import (
    compress_schema_v2,
    get_short_identifier_description,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_FILE = PROJECT_ROOT / "data" / "tools" / "tools.json"


@pytest.fixture(scope="module")
def tools():
    """Load the project's real 100-tool dataset."""
    with TOOLS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # Support either a direct list or a dictionary containing the list.
    if isinstance(data, dict):
        if "tools" in data:
            data = data["tools"]
        else:
            raise AssertionError(
                "Expected tools.json to contain a list or a 'tools' list."
            )

    assert isinstance(data, list), "The tool dataset must be a list."
    return data


def get_properties(tool):
    """Return the input schema's properties."""
    return tool.get("inputSchema", {}).get("properties", {})


def strip_descriptions(value):
    """
    Recursively remove descriptions from a copy of a schema.

    This allows structural comparisons without treating intentional
    description changes as structural changes.
    """
    if isinstance(value, dict):
        return {
            key: strip_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }

    if isinstance(value, list):
        return [strip_descriptions(item) for item in value]

    return value


def test_required_property_descriptions_are_not_removed(tools):
    """Required properties must retain their descriptions."""
    checked = 0

    for tool in tools:
        required = set(
            tool.get("inputSchema", {}).get("required", [])
        )

        original_properties = get_properties(tool)
        compressed = compress_schema_v2(tool)
        compressed_properties = get_properties(compressed)

        for property_name in required:
            original_description = original_properties.get(
                property_name, {}
            ).get("description")

            compressed_description = compressed_properties.get(
                property_name, {}
            ).get("description")

            if original_description:
                assert compressed_description, (
                    f"{tool['name']}.{property_name}: "
                    "required description was removed."
                )

            checked += 1

    assert checked > 0, "No required properties were tested."


@pytest.mark.parametrize(
    ("property_name", "description", "expected"),
    [
        (
            "order_id",
            "Unique identifier of the order.",
            "Order ID.",
        ),
        (
            "customer_id",
            "Unique identifier of the customer.",
            "Customer ID.",
        ),
        (
            "product_id",
            "Unique identifier of the product.",
            "Product ID.",
        ),
        (
            "order_id",
            "Identifier used to find an order.",
            None,
        ),
        (
            "customer_id",
            "Unique identifier of the order.",
            None,
        ),
        (
            "order_id",
            "Unique identifier of the order in another system.",
            None,
        ),
    ],
)
def test_identifier_description_shortening_rules(
    property_name, description, expected
):
    """Only descriptions matching the exact identifier rule are shortened."""
    assert get_short_identifier_description(
        property_name, description
    ) == expected


def test_important_optional_descriptions_are_preserved():
    """Known important optional descriptions must remain unchanged."""
    examples = [
        {
            "name": "search_customers",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Customer's full or partial name.",
                    }
                },
            },
        },
        {
            "name": "list_products",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Product category used to filter results.",
                    }
                },
            },
        },
        {
            "name": "update_ticket",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Updated ticket information.",
                    }
                },
            },
        },
    ]

    for tool in examples:
        original = get_properties(tool)
        compressed = compress_schema_v2(tool)
        compressed_properties = get_properties(compressed)

        for property_name, property_schema in original.items():
            assert (
                compressed_properties[property_name].get("description")
                == property_schema["description"]
            ), f"{tool['name']}.{property_name}: description changed."


def test_schema_structure_is_preserved_for_entire_dataset(tools):
    """
    Compression must not change structure when descriptions are ignored.

    Checks tool metadata, property names, types, enums, required lists,
    and other schema fields.
    """
    for tool in tools:
        original = copy.deepcopy(tool)
        compressed = compress_schema_v2(tool)

        assert strip_descriptions(compressed) == strip_descriptions(
            original
        ), f"Structural difference found in {tool['name']}."


def test_compression_does_not_mutate_original_tool(tools):
    """The compressor must return a modified copy, not mutate its input."""
    for tool in tools:
        original = copy.deepcopy(tool)

        compress_schema_v2(tool)

        assert tool == original, (
            f"Original tool was modified: {tool.get('name')}"
        )


def test_compression_is_deterministic(tools):
    """Compressing the same input twice must produce identical results."""
    for tool in tools:
        first_result = compress_schema_v2(tool)
        second_result = compress_schema_v2(tool)

        assert first_result == second_result, (
            f"Compression was inconsistent for {tool.get('name')}."
        )


def test_repeated_compression_does_not_change_result(tools):
    """Applying V2 to an already compressed schema should be idempotent."""
    for tool in tools:
        once = compress_schema_v2(tool)
        twice = compress_schema_v2(once)

        assert once == twice, (
            f"Repeated compression changed {tool.get('name')}."
        )


def test_semantically_reviewed_optional_descriptions_are_preserved():
    """Descriptions approved for preservation must survive compression."""

    examples = [
        ("update_order", "shipping_address", "New delivery address."),
        ("search_customers", "email", "Customer's email address."),
        ("create_customer", "phone", "Customer's phone number."),
        ("update_customer", "email", "Updated email address."),
        ("update_customer", "phone", "Updated phone number."),
        ("update_invoice", "due_date", "New invoice due date."),
        ("update_product", "name", "Updated product name."),
        ("update_product", "price", "Updated product price."),
        ("update_event", "title", "Updated event title."),
        ("update_event", "start_time", "Updated start date and time."),
        ("update_lead", "status", "Updated lead status."),
        ("update_contact", "phone", "Updated phone number."),
        ("update_user", "email", "Updated email address."),
    ]

    for tool_name, property_name, expected_description in examples:
        tool = {
            "name": tool_name,
            "inputSchema": {
                "type": "object",
                "properties": {
                    property_name: {
                        "type": (
                            "number"
                            if property_name == "price"
                            else "string"
                        ),
                        "description": expected_description,
                    }
                },
            },
        }

        compressed = compress_schema_v2(tool)
        compressed_description = (
            compressed["inputSchema"]["properties"][property_name]
            .get("description")
        )

        assert compressed_description == expected_description, (
            f"{tool_name}.{property_name}: "
            "reviewed description was not preserved."
        )
