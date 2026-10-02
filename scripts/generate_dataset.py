import json
from pathlib import Path


def create_tool(name, description, category, properties, required):
    """Create one MCP-style tool definition."""
    return {
        "name": name,
        "description": description,
        "category": category,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }


def string_field(description):
    return {
        "type": "string",
        "description": description
    }


def integer_field(description):
    return {
        "type": "integer",
        "description": description
    }


def number_field(description):
    return {
        "type": "number",
        "description": description
    }


def boolean_field(description):
    return {
        "type": "boolean",
        "description": description
    }


tools = [

    # ============================================================
    # ORDERS
    # ============================================================

    create_tool(
        "get_order",
        "Retrieve detailed information about a customer order.",
        "orders",
        {
            "order_id": string_field("Unique identifier of the order.")
        },
        ["order_id"]
    ),

    create_tool(
        "search_orders",
        "Search customer orders using customer information or order status.",
        "orders",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "status": {
                "type": "string",
                "description": "Current order status.",
                "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]
            }
        },
        ["customer_id"]
    ),

    create_tool(
        "create_order",
        "Create a new customer order.",
        "orders",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "product_id": string_field("Unique identifier of the product."),
            "quantity": integer_field("Number of units to order.")
        },
        ["customer_id", "product_id", "quantity"]
    ),

    create_tool(
        "update_order",
        "Update information associated with an existing customer order.",
        "orders",
        {
            "order_id": string_field("Unique identifier of the order."),
            "shipping_address": string_field("New delivery address.")
        },
        ["order_id"]
    ),

    create_tool(
        "cancel_order",
        "Cancel an existing customer order.",
        "orders",
        {
            "order_id": string_field("Unique identifier of the order."),
            "reason": string_field("Reason for cancelling the order.")
        },
        ["order_id", "reason"]
    ),

    create_tool(
        "refund_order",
        "Refund an existing customer order.",
        "orders",
        {
            "order_id": string_field("Unique identifier of the order."),
            "reason": string_field("Reason for requesting the refund.")
        },
        ["order_id", "reason"]
    ),

    create_tool(
        "get_order_items",
        "Retrieve the products and quantities included in an order.",
        "orders",
        {
            "order_id": string_field("Unique identifier of the order.")
        },
        ["order_id"]
    ),

    create_tool(
        "update_order_status",
        "Change the current status of an existing order.",
        "orders",
        {
            "order_id": string_field("Unique identifier of the order."),
            "status": {
                "type": "string",
                "description": "New status for the order.",
                "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]
            }
        },
        ["order_id", "status"]
    ),

    # ============================================================
    # CUSTOMERS
    # ============================================================

    create_tool(
        "get_customer",
        "Retrieve customer profile information.",
        "customers",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "search_customers",
        "Search for customers using their name or email address.",
        "customers",
        {
            "name": string_field("Customer's full or partial name."),
            "email": string_field("Customer's email address.")
        },
        []
    ),

    create_tool(
        "create_customer",
        "Create a new customer profile.",
        "customers",
        {
            "name": string_field("Customer's full name."),
            "email": string_field("Customer's email address."),
            "phone": string_field("Customer's phone number.")
        },
        ["name", "email"]
    ),

    create_tool(
        "update_customer",
        "Update information in an existing customer profile.",
        "customers",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "email": string_field("Updated email address."),
            "phone": string_field("Updated phone number.")
        },
        ["customer_id"]
    ),

    create_tool(
        "delete_customer",
        "Remove an existing customer profile.",
        "customers",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "get_customer_orders",
        "Retrieve all orders associated with a customer.",
        "customers",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "get_customer_address",
        "Retrieve the saved address of a customer.",
        "customers",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "update_customer_address",
        "Update the saved address of a customer.",
        "customers",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "address": string_field("New customer address.")
        },
        ["customer_id", "address"]
    ),

    # ============================================================
    # PAYMENTS
    # ============================================================

    create_tool(
        "get_payment",
        "Retrieve details about a specific payment.",
        "payments",
        {
            "payment_id": string_field("Unique identifier of the payment.")
        },
        ["payment_id"]
    ),

    create_tool(
        "charge_payment",
        "Charge a payment method for a specified amount.",
        "payments",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "amount": number_field("Amount to charge.")
        },
        ["customer_id", "amount"]
    ),

    create_tool(
        "refund_payment",
        "Refund a completed payment to the customer.",
        "payments",
        {
            "payment_id": string_field("Unique identifier of the payment."),
            "amount": number_field("Amount to refund.")
        },
        ["payment_id", "amount"]
    ),

    create_tool(
        "list_payments",
        "List payments associated with a customer.",
        "payments",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "get_payment_status",
        "Check the current status of a payment.",
        "payments",
        {
            "payment_id": string_field("Unique identifier of the payment.")
        },
        ["payment_id"]
    ),

    create_tool(
        "create_payment_method",
        "Add a payment method to a customer account.",
        "payments",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "payment_token": string_field("Token representing the payment method.")
        },
        ["customer_id", "payment_token"]
    ),

    create_tool(
        "remove_payment_method",
        "Remove a saved payment method from a customer account.",
        "payments",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "payment_method_id": string_field("Unique identifier of the payment method.")
        },
        ["customer_id", "payment_method_id"]
    ),

    create_tool(
        "verify_payment",
        "Verify whether a payment has been successfully completed.",
        "payments",
        {
            "payment_id": string_field("Unique identifier of the payment.")
        },
        ["payment_id"]
    ),

    # ============================================================
    # INVOICES
    # ============================================================

    create_tool(
        "get_invoice",
        "Retrieve details of a customer invoice.",
        "invoices",
        {
            "invoice_id": string_field("Unique identifier of the invoice.")
        },
        ["invoice_id"]
    ),

    create_tool(
        "create_invoice",
        "Create a new invoice for a customer.",
        "invoices",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "amount": number_field("Total invoice amount.")
        },
        ["customer_id", "amount"]
    ),

    create_tool(
        "update_invoice",
        "Update information on an existing invoice.",
        "invoices",
        {
            "invoice_id": string_field("Unique identifier of the invoice."),
            "due_date": string_field("New invoice due date.")
        },
        ["invoice_id"]
    ),

    create_tool(
        "cancel_invoice",
        "Cancel an existing invoice.",
        "invoices",
        {
            "invoice_id": string_field("Unique identifier of the invoice."),
            "reason": string_field("Reason for cancelling the invoice.")
        },
        ["invoice_id", "reason"]
    ),

    create_tool(
        "send_invoice",
        "Send an invoice to the customer's email address.",
        "invoices",
        {
            "invoice_id": string_field("Unique identifier of the invoice."),
            "email": string_field("Recipient email address.")
        },
        ["invoice_id", "email"]
    ),

    create_tool(
        "list_invoices",
        "List invoices belonging to a customer.",
        "invoices",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "mark_invoice_paid",
        "Mark an invoice as paid.",
        "invoices",
        {
            "invoice_id": string_field("Unique identifier of the invoice.")
        },
        ["invoice_id"]
    ),

    create_tool(
        "get_invoice_status",
        "Retrieve the current status of an invoice.",
        "invoices",
        {
            "invoice_id": string_field("Unique identifier of the invoice.")
        },
        ["invoice_id"]
    ),

    # ============================================================
    # PRODUCTS
    # ============================================================

    create_tool(
        "get_product",
        "Retrieve detailed information about a product.",
        "products",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "search_products",
        "Search the product catalog using keywords.",
        "products",
        {
            "query": string_field("Search keywords for finding products.")
        },
        ["query"]
    ),

    create_tool(
        "create_product",
        "Create a new product in the catalog.",
        "products",
        {
            "name": string_field("Product name."),
            "price": number_field("Product price.")
        },
        ["name", "price"]
    ),

    create_tool(
        "update_product",
        "Update product information in the catalog.",
        "products",
        {
            "product_id": string_field("Unique identifier of the product."),
            "name": string_field("Updated product name."),
            "price": number_field("Updated product price.")
        },
        ["product_id"]
    ),

    create_tool(
        "delete_product",
        "Remove a product from the catalog.",
        "products",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "get_product_price",
        "Retrieve the current price of a product.",
        "products",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "update_product_price",
        "Change the price of an existing product.",
        "products",
        {
            "product_id": string_field("Unique identifier of the product."),
            "price": number_field("New product price.")
        },
        ["product_id", "price"]
    ),

    create_tool(
        "list_products",
        "Retrieve a list of products from the catalog.",
        "products",
        {
            "category": string_field("Product category used to filter results.")
        },
        []
    ),

    # ============================================================
    # INVENTORY
    # ============================================================

    create_tool(
        "check_inventory",
        "Check the available inventory quantity for a product.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "update_inventory",
        "Update the inventory quantity for a product.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product."),
            "quantity": integer_field("New inventory quantity.")
        },
        ["product_id", "quantity"]
    ),

    create_tool(
        "reserve_inventory",
        "Reserve inventory units for an order.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product."),
            "quantity": integer_field("Number of units to reserve.")
        },
        ["product_id", "quantity"]
    ),

    create_tool(
        "release_inventory",
        "Release previously reserved inventory units.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product."),
            "quantity": integer_field("Number of units to release.")
        },
        ["product_id", "quantity"]
    ),

    create_tool(
        "get_inventory_location",
        "Find the warehouse location where a product is stored.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "list_low_stock_products",
        "List products whose inventory is below the configured threshold.",
        "inventory",
        {
            "threshold": integer_field("Inventory quantity threshold.")
        },
        ["threshold"]
    ),

    create_tool(
        "add_inventory",
        "Increase inventory quantity for a product.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product."),
            "quantity": integer_field("Number of units to add.")
        },
        ["product_id", "quantity"]
    ),

    create_tool(
        "remove_inventory",
        "Decrease inventory quantity for a product.",
        "inventory",
        {
            "product_id": string_field("Unique identifier of the product."),
            "quantity": integer_field("Number of units to remove.")
        },
        ["product_id", "quantity"]
    ),

    # ============================================================
    # SHIPPING
    # ============================================================

    create_tool(
        "track_shipment",
        "Retrieve the current tracking information for a shipment.",
        "shipping",
        {
            "tracking_number": string_field("Unique shipment tracking number.")
        },
        ["tracking_number"]
    ),

    create_tool(
        "create_shipment",
        "Create a shipment for an existing order.",
        "shipping",
        {
            "order_id": string_field("Unique identifier of the order."),
            "address": string_field("Delivery address.")
        },
        ["order_id", "address"]
    ),

    create_tool(
        "cancel_shipment",
        "Cancel an existing shipment.",
        "shipping",
        {
            "shipment_id": string_field("Unique identifier of the shipment.")
        },
        ["shipment_id"]
    ),

    create_tool(
        "get_shipping_rate",
        "Calculate the shipping cost for a destination and package.",
        "shipping",
        {
            "destination": string_field("Delivery destination."),
            "weight": number_field("Package weight.")
        },
        ["destination", "weight"]
    ),

    create_tool(
        "update_shipping_address",
        "Update the delivery address for a shipment.",
        "shipping",
        {
            "shipment_id": string_field("Unique identifier of the shipment."),
            "address": string_field("New delivery address.")
        },
        ["shipment_id", "address"]
    ),

    create_tool(
        "get_shipment",
        "Retrieve detailed information about a shipment.",
        "shipping",
        {
            "shipment_id": string_field("Unique identifier of the shipment.")
        },
        ["shipment_id"]
    ),

    create_tool(
        "list_shipments",
        "List shipments associated with an order.",
        "shipping",
        {
            "order_id": string_field("Unique identifier of the order.")
        },
        ["order_id"]
    ),

    create_tool(
        "mark_shipment_delivered",
        "Mark a shipment as delivered.",
        "shipping",
        {
            "shipment_id": string_field("Unique identifier of the shipment.")
        },
        ["shipment_id"]
    ),

    # ============================================================
    # SUPPORT
    # ============================================================

    create_tool(
        "create_ticket",
        "Create a new customer support ticket.",
        "support",
        {
            "customer_id": string_field("Unique identifier of the customer."),
            "subject": string_field("Support ticket subject."),
            "description": string_field("Description of the customer's issue.")
        },
        ["customer_id", "subject", "description"]
    ),

    create_tool(
        "get_ticket",
        "Retrieve details about a support ticket.",
        "support",
        {
            "ticket_id": string_field("Unique identifier of the support ticket.")
        },
        ["ticket_id"]
    ),

    create_tool(
        "update_ticket",
        "Update an existing support ticket.",
        "support",
        {
            "ticket_id": string_field("Unique identifier of the support ticket."),
            "description": string_field("Updated ticket information.")
        },
        ["ticket_id"]
    ),

    create_tool(
        "close_ticket",
        "Close an existing support ticket.",
        "support",
        {
            "ticket_id": string_field("Unique identifier of the support ticket.")
        },
        ["ticket_id"]
    ),

    create_tool(
        "search_tickets",
        "Search customer support tickets using keywords.",
        "support",
        {
            "query": string_field("Keywords describing the support issue.")
        },
        ["query"]
    ),

    create_tool(
        "assign_ticket",
        "Assign a support ticket to an agent.",
        "support",
        {
            "ticket_id": string_field("Unique identifier of the support ticket."),
            "agent_id": string_field("Unique identifier of the support agent.")
        },
        ["ticket_id", "agent_id"]
    ),

    create_tool(
        "reopen_ticket",
        "Reopen a previously closed support ticket.",
        "support",
        {
            "ticket_id": string_field("Unique identifier of the support ticket.")
        },
        ["ticket_id"]
    ),

    # ============================================================
    # EMAIL
    # ============================================================

    create_tool(
        "send_email",
        "Send an email message to one or more recipients.",
        "email",
        {
            "recipient": string_field("Email address of the recipient."),
            "subject": string_field("Email subject."),
            "body": string_field("Email message content.")
        },
        ["recipient", "subject", "body"]
    ),

    create_tool(
        "search_emails",
        "Search email messages using keywords.",
        "email",
        {
            "query": string_field("Keywords used to search email messages.")
        },
        ["query"]
    ),

    create_tool(
        "get_email",
        "Retrieve a specific email message.",
        "email",
        {
            "email_id": string_field("Unique identifier of the email.")
        },
        ["email_id"]
    ),

    create_tool(
        "delete_email",
        "Delete an email message.",
        "email",
        {
            "email_id": string_field("Unique identifier of the email.")
        },
        ["email_id"]
    ),

    create_tool(
        "mark_email_read",
        "Mark an email message as read.",
        "email",
        {
            "email_id": string_field("Unique identifier of the email.")
        },
        ["email_id"]
    ),

    create_tool(
        "archive_email",
        "Archive an email message.",
        "email",
        {
            "email_id": string_field("Unique identifier of the email.")
        },
        ["email_id"]
    ),

    create_tool(
        "reply_to_email",
        "Send a reply to an existing email message.",
        "email",
        {
            "email_id": string_field("Unique identifier of the original email."),
            "body": string_field("Reply message content.")
        },
        ["email_id", "body"]
    ),

    # ============================================================
    # CALENDAR
    # ============================================================

    create_tool(
        "create_event",
        "Create a new calendar event.",
        "calendar",
        {
            "title": string_field("Title of the calendar event."),
            "start_time": string_field("Event start date and time."),
            "end_time": string_field("Event end date and time.")
        },
        ["title", "start_time", "end_time"]
    ),

    create_tool(
        "get_event",
        "Retrieve details of a calendar event.",
        "calendar",
        {
            "event_id": string_field("Unique identifier of the calendar event.")
        },
        ["event_id"]
    ),

    create_tool(
        "update_event",
        "Update an existing calendar event.",
        "calendar",
        {
            "event_id": string_field("Unique identifier of the event."),
            "title": string_field("Updated event title."),
            "start_time": string_field("Updated start date and time.")
        },
        ["event_id"]
    ),

    create_tool(
        "cancel_event",
        "Cancel an existing calendar event.",
        "calendar",
        {
            "event_id": string_field("Unique identifier of the calendar event.")
        },
        ["event_id"]
    ),

    create_tool(
        "list_events",
        "List calendar events within a specified date range.",
        "calendar",
        {
            "start_date": string_field("Beginning of the date range."),
            "end_date": string_field("End of the date range.")
        },
        ["start_date", "end_date"]
    ),

    create_tool(
        "find_available_time",
        "Find available calendar time slots for scheduling.",
        "calendar",
        {
            "date": string_field("Date on which to find an available slot.")
        },
        ["date"]
    ),

    create_tool(
        "add_event_attendee",
        "Add an attendee to an existing calendar event.",
        "calendar",
        {
            "event_id": string_field("Unique identifier of the event."),
            "email": string_field("Email address of the attendee.")
        },
        ["event_id", "email"]
    ),

    # ============================================================
    # CRM
    # ============================================================

    create_tool(
        "create_lead",
        "Create a new sales lead in the CRM.",
        "crm",
        {
            "name": string_field("Lead's full name."),
            "email": string_field("Lead's email address.")
        },
        ["name", "email"]
    ),

    create_tool(
        "get_lead",
        "Retrieve information about a CRM lead.",
        "crm",
        {
            "lead_id": string_field("Unique identifier of the lead.")
        },
        ["lead_id"]
    ),

    create_tool(
        "update_lead",
        "Update information about an existing CRM lead.",
        "crm",
        {
            "lead_id": string_field("Unique identifier of the lead."),
            "status": string_field("Updated lead status.")
        },
        ["lead_id"]
    ),

    create_tool(
        "delete_lead",
        "Delete a lead from the CRM.",
        "crm",
        {
            "lead_id": string_field("Unique identifier of the lead.")
        },
        ["lead_id"]
    ),

    create_tool(
        "create_contact",
        "Create a new CRM contact.",
        "crm",
        {
            "name": string_field("Contact's full name."),
            "email": string_field("Contact's email address.")
        },
        ["name", "email"]
    ),

    create_tool(
        "get_contact",
        "Retrieve information about a CRM contact.",
        "crm",
        {
            "contact_id": string_field("Unique identifier of the contact.")
        },
        ["contact_id"]
    ),

    create_tool(
        "update_contact",
        "Update information about an existing CRM contact.",
        "crm",
        {
            "contact_id": string_field("Unique identifier of the contact."),
            "phone": string_field("Updated phone number.")
        },
        ["contact_id"]
    ),

    # ============================================================
    # AUTHENTICATION
    # ============================================================

    create_tool(
        "create_user",
        "Create a new user account.",
        "authentication",
        {
            "username": string_field("Desired username."),
            "email": string_field("User's email address.")
        },
        ["username", "email"]
    ),

    create_tool(
        "get_user",
        "Retrieve information about a user account.",
        "authentication",
        {
            "user_id": string_field("Unique identifier of the user.")
        },
        ["user_id"]
    ),

    create_tool(
        "update_user",
        "Update information associated with a user account.",
        "authentication",
        {
            "user_id": string_field("Unique identifier of the user."),
            "email": string_field("Updated email address.")
        },
        ["user_id"]
    ),

    create_tool(
        "delete_user",
        "Delete an existing user account.",
        "authentication",
        {
            "user_id": string_field("Unique identifier of the user.")
        },
        ["user_id"]
    ),

    create_tool(
        "reset_password",
        "Reset the password for a user account.",
        "authentication",
        {
            "user_id": string_field("Unique identifier of the user.")
        },
        ["user_id"]
    ),

    create_tool(
        "verify_user",
        "Verify the identity or status of a user account.",
        "authentication",
        {
            "user_id": string_field("Unique identifier of the user.")
        },
        ["user_id"]
    ),

    create_tool(
        "disable_user",
        "Disable an active user account.",
        "authentication",
        {
            "user_id": string_field("Unique identifier of the user."),
            "reason": string_field("Reason for disabling the account.")
        },
        ["user_id", "reason"]
    ),

    # ============================================================
    # ANALYTICS
    # ============================================================

    create_tool(
        "get_sales_report",
        "Generate a sales report for a specified date range.",
        "analytics",
        {
            "start_date": string_field("Beginning of the reporting period."),
            "end_date": string_field("End of the reporting period.")
        },
        ["start_date", "end_date"]
    ),

    create_tool(
        "get_customer_metrics",
        "Retrieve metrics describing customer activity.",
        "analytics",
        {
            "customer_id": string_field("Unique identifier of the customer.")
        },
        ["customer_id"]
    ),

    create_tool(
        "get_order_metrics",
        "Retrieve metrics describing order activity.",
        "analytics",
        {
            "start_date": string_field("Beginning of the reporting period."),
            "end_date": string_field("End of the reporting period.")
        },
        ["start_date", "end_date"]
    ),

    create_tool(
        "get_product_metrics",
        "Retrieve performance metrics for a product.",
        "analytics",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "get_revenue_report",
        "Generate a revenue report for a specified date range.",
        "analytics",
        {
            "start_date": string_field("Beginning of the reporting period."),
            "end_date": string_field("End of the reporting period.")
        },
        ["start_date", "end_date"]
    ),

    create_tool(
        "get_inventory_metrics",
        "Retrieve metrics describing inventory activity.",
        "analytics",
        {
            "product_id": string_field("Unique identifier of the product.")
        },
        ["product_id"]
    ),

    create_tool(
        "get_payment_metrics",
        "Retrieve metrics describing payment activity.",
        "analytics",
        {
            "start_date": string_field("Beginning of the reporting period."),
            "end_date": string_field("End of the reporting period.")
        },
        ["start_date", "end_date"]
    ),

    create_tool(
        "get_support_metrics",
        "Retrieve metrics describing customer support activity.",
        "analytics",
        {
            "start_date": string_field("Beginning of the reporting period."),
            "end_date": string_field("End of the reporting period.")
        },
        ["start_date", "end_date"]
    ),


    create_tool(
        "get_refund_metrics",
        "Retrieve metrics describing customer refund activity.",
        "analytics",
        {
            "start_date": string_field("Beginning of the reporting period."),
            "end_date": string_field("End of the reporting period.")
        },
        ["start_date", "end_date"]
    ),
]


# ============================================================
# VALIDATION
# ============================================================

def validate_tools(tool_list):
    """Check that the generated dataset follows our basic rules."""

    names = [tool["name"] for tool in tool_list]

    # Check unique names
    if len(names) != len(set(names)):
        raise ValueError("Duplicate tool names found.")

    # Check required fields
    required_fields = {
        "name",
        "description",
        "category",
        "inputSchema"
    }

    for tool in tool_list:
        missing = required_fields - tool.keys()

        if missing:
            raise ValueError(
                f"Tool '{tool.get('name')}' is missing: {missing}"
            )

        if not tool["name"].islower():
            raise ValueError(
                f"Tool name '{tool['name']}' must use lowercase."
            )

        if " " in tool["name"]:
            raise ValueError(
                f"Tool name '{tool['name']}' must not contain spaces."
            )

        if tool["inputSchema"]["type"] != "object":
            raise ValueError(
                f"Tool '{tool['name']}' must use an object input schema."
            )


# Validate
validate_tools(tools)


# ============================================================
# SAVE DATASET
# ============================================================

output_path = Path(__file__).parent.parent / "data" / "tools" / "tools.json"

output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding="utf-8") as file:
    json.dump(tools, file, indent=2, ensure_ascii=False)


print("=" * 50)
print("Dataset generation completed successfully!")
print("=" * 50)
print(f"Total tools: {len(tools)}")
print(f"Output file: {output_path}")
print("=" * 50)
