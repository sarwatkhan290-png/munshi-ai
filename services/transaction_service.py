"""
Transaction service — every function here is tenant-scoped.

All reads and writes against customers/transactions/expenses require an
explicit tenant_id. There is no default tenant fallback: passing None
raises immediately, so a missing tenant_id fails loudly in development
instead of silently leaking data across shops in production.
"""

from database import get_connection


class MissingTenantError(ValueError):
    """Raised when a data-access call is made without a tenant scope."""


def _require_tenant(tenant_id):
    if tenant_id is None:
        raise MissingTenantError(
            "tenant_id is required for this operation — every query must be "
            "scoped to the logged-in shop's tenant."
        )
    return tenant_id


def add_customer(tenant_id, name, phone=None, shop_id=1):
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO customers (tenant_id, shop_id, name, phone)
        VALUES (?, ?, ?, ?)
        """,
        (tenant_id, shop_id, name, phone),
    )

    connection.commit()
    customer_id = cursor.lastrowid
    connection.close()
    return customer_id


def get_customer(tenant_id, name):
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, name, phone
        FROM customers
        WHERE tenant_id = ? AND LOWER(name) = LOWER(?)
        """,
        (tenant_id, name),
    )

    customer = cursor.fetchone()
    connection.close()
    return customer


def get_or_create_customer(tenant_id, name, shop_id=1):
    tenant_id = _require_tenant(tenant_id)
    customer = get_customer(tenant_id, name)
    if customer:
        return customer[0]
    return add_customer(tenant_id, name, shop_id=shop_id)


def _validate_amount(value, field_name="amount"):
    if value is None:
        raise ValueError(f"{field_name} is required")
    amount = float(value)
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return amount


def add_sale(tenant_id, customer_name, amount, paid=0, description="", shop_id=1):
    tenant_id = _require_tenant(tenant_id)
    customer_name = (customer_name or "").strip()
    if not customer_name:
        raise ValueError("Customer name is required")

    amount = _validate_amount(amount, "amount")
    paid = _validate_amount(paid, "paid")
    customer_id = get_or_create_customer(tenant_id, customer_name, shop_id=shop_id)
    due = max(amount - paid, 0)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO transactions
        (tenant_id, shop_id, customer_id, transaction_type, description, amount, paid, due)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tenant_id, shop_id, customer_id, "sale", description, amount, paid, due),
    )

    connection.commit()
    transaction_id = cursor.lastrowid
    connection.close()

    return {
        "transaction_id": transaction_id,
        "customer": customer_name,
        "amount": amount,
        "paid": paid,
        "due": due,
    }


def add_payment(tenant_id, customer_name, amount, shop_id=1):
    tenant_id = _require_tenant(tenant_id)
    customer_name = (customer_name or "").strip()
    customer = get_customer(tenant_id, customer_name)
    if not customer:
        return None

    amount = _validate_amount(amount, "amount")
    customer_id = customer[0]

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO transactions
        (tenant_id, shop_id, customer_id, transaction_type, description, amount, paid, due)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tenant_id, shop_id, customer_id, "payment", "Payment received", amount, amount, 0),
    )

    connection.commit()
    transaction_id = cursor.lastrowid
    connection.close()

    return {
        "transaction_id": transaction_id,
        "customer": customer_name,
        "payment": amount,
    }


def add_expense(tenant_id, category, amount, description="", shop_id=1):
    tenant_id = _require_tenant(tenant_id)
    category = (category or "Other").strip() or "Other"
    amount = _validate_amount(amount, "amount")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO expenses (tenant_id, shop_id, category, description, amount)
        VALUES (?, ?, ?, ?, ?)
        """,
        (tenant_id, shop_id, category, description, amount),
    )

    connection.commit()
    expense_id = cursor.lastrowid
    connection.close()

    return {
        "expense_id": expense_id,
        "category": category,
        "amount": amount,
        "description": description,
    }


def get_customer_ledger(tenant_id, customer_name):
    tenant_id = _require_tenant(tenant_id)
    customer = get_customer(tenant_id, customer_name)
    if not customer:
        return []

    customer_id = customer[0]

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            transaction_type,
            description,
            amount,
            paid,
            due,
            date
        FROM transactions
        WHERE tenant_id = ? AND customer_id = ?
        ORDER BY date DESC
        """,
        (tenant_id, customer_id),
    )

    ledger = cursor.fetchall()
    connection.close()
    return ledger


def process_transaction(tenant_id, text, shop_id=1):
    """Parse a natural-language transaction and save it to the database."""
    tenant_id = _require_tenant(tenant_id)
    from services.ai_service import parse_transaction

    transaction = parse_transaction(text)

    if transaction["type"] == "sale":
        if not transaction["customer"]:
            return {"success": False, "message": "Customer name could not be detected."}

        try:
            result = add_sale(
                tenant_id,
                customer_name=transaction["customer"],
                amount=transaction["amount"],
                paid=transaction["paid"],
                description=transaction["description"],
                shop_id=shop_id,
            )
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

        result["success"] = True
        result["source"] = transaction.get("source", "regex")
        return result

    if transaction["type"] == "payment":
        if not transaction["customer"]:
            return {"success": False, "message": "Customer name could not be detected."}

        result = add_payment(
            tenant_id,
            customer_name=transaction["customer"],
            amount=transaction["amount"],
            shop_id=shop_id,
        )

        if result is None:
            return {"success": False, "message": "Customer does not exist."}

        result["success"] = True
        result["source"] = transaction.get("source", "regex")
        return result

    return {
        "success": False,
        "message": "Could not understand the transaction. Try rephrasing, e.g. 'Ali ne 5000 ka maal liya'.",
    }
