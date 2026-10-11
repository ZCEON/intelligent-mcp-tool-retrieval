from src.compression.schema_compressor_v2 import compress_schema_v2


def test_partial_customer_name_description_is_preserved():
    tool = {
        "name": "search_customers",
        "description": "Search customers.",
        "category": "customers",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Customer's full or partial name."
                }
            },
            "required": []
        }
    }

    compressed = compress_schema_v2(tool)

    assert (
        compressed["inputSchema"]["properties"]["name"]["description"]
        == "Customer's full or partial name."
    )


def test_optional_status_description_can_be_removed_when_enum_is_preserved():
    tool = {
        "name": "search_orders",
        "description": "Search orders.",
        "category": "orders",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Current order status.",
                    "enum": [
                        "pending",
                        "processing",
                        "shipped",
                        "delivered",
                        "cancelled"
                    ]
                }
            },
            "required": []
        }
    }

    compressed = compress_schema_v2(tool)

    status = compressed["inputSchema"]["properties"]["status"]

    assert "description" not in status
    assert status["enum"] == [
        "pending",
        "processing",
        "shipped",
        "delivered",
        "cancelled"
    ]


def test_product_category_filter_description_is_preserved():
    tool = {
        "name": "list_products",
        "description": "List products.",
        "category": "products",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Product category used to filter results."
                }
            },
            "required": []
        }
    }

    compressed = compress_schema_v2(tool)

    assert (
        compressed["inputSchema"]["properties"]["category"]["description"]
        == "Product category used to filter results."
    )


def test_update_ticket_description_is_preserved():
    tool = {
        "name": "update_ticket",
        "description": "Update a ticket.",
        "category": "tickets",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Updated ticket information."
                }
            },
            "required": []
        }
    }

    compressed = compress_schema_v2(tool)

    assert (
        compressed["inputSchema"]["properties"]["description"]["description"]
        == "Updated ticket information."
    )
