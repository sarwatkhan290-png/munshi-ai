"""
Analytics service — every query here is tenant-scoped.

All aggregate/report functions take tenant_id as their first argument and
filter every query by it, so one shop's dashboard can never surface another
shop's sales, expenses, or customer data.
"""

from database import get_connection
from datetime import datetime

OVERDUE_THRESHOLD_DAYS = 30


class MissingTenantError(ValueError):
    """Raised when an analytics call is made without a tenant scope."""


def _require_tenant(tenant_id):
    if tenant_id is None:
        raise MissingTenantError(
            "tenant_id is required for this operation — every query must be "
            "scoped to the logged-in shop's tenant."
        )
    return tenant_id


def _parse_date(date_str):
    try:
        return datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def get_total_sales(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE tenant_id = ? AND transaction_type = 'sale'
        """,
        (tenant_id,),
    )

    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_total_paid(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COALESCE(SUM(paid), 0)
        FROM transactions
        WHERE tenant_id = ? AND transaction_type = 'sale'
        """,
        (tenant_id,),
    )

    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_total_due(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COALESCE(SUM(due), 0)
        FROM transactions
        WHERE tenant_id = ? AND transaction_type = 'sale'
        """,
        (tenant_id,),
    )

    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_total_expenses(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE tenant_id = ?
        """,
        (tenant_id,),
    )

    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_estimated_profit(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    return get_total_sales(tenant_id) - get_total_expenses(tenant_id)


def get_collection_rate(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    total_sales = get_total_sales(tenant_id)
    if total_sales <= 0:
        return 0.0
    return (get_total_paid(tenant_id) / total_sales) * 100


def get_dashboard_summary(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    sales = get_total_sales(tenant_id)
    paid = get_total_paid(tenant_id)
    due = get_total_due(tenant_id)
    expenses = get_total_expenses(tenant_id)
    profit = get_estimated_profit(tenant_id)

    return {
        "sales": sales,
        "paid": paid,
        "due": due,
        "expenses": expenses,
        "profit": profit,
        "collection_rate": get_collection_rate(tenant_id),
        "net_cashflow": paid - expenses,
    }


# ==================================================
# FR-05 — Per-customer balances (digital ledger)
# ==================================================

def get_customer_balances(tenant_id):
    """Return one row per customer with totals and recent activity."""
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            c.id,
            c.name,
            COALESCE(SUM(CASE WHEN t.transaction_type = 'sale' THEN t.amount ELSE 0 END), 0) AS total_credit,
            COALESCE(SUM(t.paid), 0) AS total_paid,
            COALESCE(SUM(CASE WHEN t.transaction_type = 'sale' THEN t.due ELSE 0 END), 0) AS total_due,
            MAX(t.date) AS last_transaction_date
        FROM customers c
        LEFT JOIN transactions t ON t.customer_id = c.id AND t.tenant_id = c.tenant_id
        WHERE c.tenant_id = ?
        GROUP BY c.id, c.name
        ORDER BY total_due DESC
        """,
        (tenant_id,),
    )

    rows = cursor.fetchall()
    connection.close()
    return rows


def get_top_debtors(tenant_id, limit=5):
    """Customers with the highest outstanding balance, highest first."""
    tenant_id = _require_tenant(tenant_id)
    balances = get_customer_balances(tenant_id)
    debtors = [row for row in balances if row[4] > 0]
    return debtors[:limit]


def get_recent_transactions(tenant_id, limit=5):
    """Return the most recent business activity for a quick dashboard summary."""
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            c.name,
            t.transaction_type,
            t.description,
            t.amount,
            t.paid,
            t.due,
            t.date
        FROM transactions t
        JOIN customers c ON c.id = t.customer_id
        WHERE t.tenant_id = ?
        ORDER BY datetime(t.date) DESC
        LIMIT ?
        """,
        (tenant_id, limit),
    )

    rows = cursor.fetchall()
    connection.close()
    return rows


def get_transaction_history(tenant_id, limit=100, customer_name=None, transaction_type=None):
    """Return a richer transaction ledger that can be filtered by customer or type."""
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            c.name,
            t.transaction_type,
            t.description,
            t.amount,
            t.paid,
            t.due,
            t.date
        FROM transactions t
        JOIN customers c ON c.id = t.customer_id
        WHERE t.tenant_id = ?
    """
    params = [tenant_id]

    if customer_name:
        query += " AND LOWER(c.name) LIKE LOWER(?)"
        params.append(f"%{customer_name}%")
    if transaction_type and transaction_type != "all":
        query += " AND t.transaction_type = ?"
        params.append(transaction_type)

    query += " ORDER BY datetime(t.date) DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    connection.close()
    return rows


def get_expense_summary(tenant_id):
    """Summarize expenses by category for dashboard and reporting."""
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT category, COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE tenant_id = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (tenant_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def get_monthly_business_data(tenant_id, months=6):
    """Return recent monthly sales and collection totals for trend charts."""
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            strftime('%Y-%m', date) AS month,
            COALESCE(SUM(CASE WHEN transaction_type = 'sale' THEN amount ELSE 0 END), 0) AS sales,
            COALESCE(SUM(CASE WHEN transaction_type = 'payment' THEN paid ELSE 0 END), 0) AS collected,
            COALESCE(SUM(CASE WHEN transaction_type = 'sale' THEN due ELSE 0 END), 0) AS outstanding
        FROM transactions
        WHERE tenant_id = ?
        GROUP BY month
        ORDER BY month DESC
        LIMIT ?
        """,
        (tenant_id, months),
    )
    rows = cursor.fetchall()
    connection.close()
    return list(reversed(rows))


# ==================================================
# FR-09 — Overdue detection
# ==================================================

def get_overdue_customers(tenant_id, threshold_days=OVERDUE_THRESHOLD_DAYS):
    """Return customers whose unpaid balances are overdue by threshold_days or more."""
    tenant_id = _require_tenant(tenant_id)
    now = datetime.now()
    overdue = []

    for customer_id, name, credit, paid, due, last_date in get_customer_balances(tenant_id):
        if due <= 0 or not last_date:
            continue

        last_dt = _parse_date(last_date)
        if last_dt is None:
            continue

        days_overdue = (now - last_dt).days
        if days_overdue >= threshold_days:
            overdue.append({
                "customer_id": customer_id,
                "name": name,
                "due": due,
                "days_overdue": days_overdue,
            })

    overdue.sort(key=lambda row: row["days_overdue"], reverse=True)
    return overdue


# ==================================================
# FR-12 — Udhaar Reliability Score
# (an internal indicator, NOT a formal credit score)
# ==================================================

def get_udhaar_score(tenant_id, customer_id):
    """Return a 0-100 internal readiness score for the customer."""
    tenant_id = _require_tenant(tenant_id)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT transaction_type, amount, paid, due, date
        FROM transactions
        WHERE tenant_id = ? AND customer_id = ?
        ORDER BY date ASC
        """,
        (tenant_id, customer_id),
    )

    rows = cursor.fetchall()
    connection.close()

    sales = [row for row in rows if row[0] == "sale"]
    if not sales:
        return {"score": None, "risk_level": "No history yet"}

    total_credit = sum(row[1] for row in sales)
    total_due = sum(row[3] for row in sales)
    paid_ratio = 1 - (total_due / total_credit) if total_credit else 1

    now = datetime.now()
    recency_penalty = 0
    for row in sales:
        if row[3] > 0:
            sale_date = _parse_date(row[4])
            if sale_date:
                days_unpaid = (now - sale_date).days
                recency_penalty += min(days_unpaid, 90) / 90 * 20

    score = max(0, min(100, round(paid_ratio * 100 - recency_penalty)))

    if score >= 75:
        risk_level = "🟢 LOW RISK"
    elif score >= 45:
        risk_level = "🟡 MEDIUM RISK"
    else:
        risk_level = "🔴 HIGH RISK"

    return {"score": score, "risk_level": risk_level}


def get_sales_forecast(tenant_id):
    """Estimate next month's sales using a simple linear trend."""
    tenant_id = _require_tenant(tenant_id)
    import numpy as np

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT strftime('%Y-%m', date) AS month, SUM(amount)
        FROM transactions
        WHERE tenant_id = ? AND transaction_type = 'sale'
        GROUP BY month
        ORDER BY month ASC
        """,
        (tenant_id,),
    )

    rows = cursor.fetchall()
    connection.close()

    if len(rows) < 2:
        return None

    months = list(range(len(rows)))
    sales = [row[1] for row in rows]
    coefficients = np.polyfit(months, sales, 1)
    forecast = coefficients[0] * len(rows) + coefficients[1]

    return {
        "history": rows,
        "forecast": max(0, forecast),
    }


def get_business_insights(tenant_id):
    tenant_id = _require_tenant(tenant_id)
    insights = []

    balances = get_customer_balances(tenant_id)
    debtors = [row for row in balances if row[4] > 0]
    total_due = sum(row[4] for row in balances)

    if debtors and total_due > 0:
        top3_due = sum(row[4] for row in sorted(debtors, key=lambda r: r[4], reverse=True)[:3])
        share = (top3_due / total_due) * 100 if total_due else 0
        insights.append(
            f"Your top 3 customers account for {share:.0f}% of your outstanding credit (Rs. {top3_due:,.0f})."
        )

    overdue = get_overdue_customers(tenant_id)
    if overdue:
        insights.append(
            f"{len(overdue)} customer(s) are overdue by {OVERDUE_THRESHOLD_DAYS}+ days, totaling Rs. {sum(row['due'] for row in overdue):,.0f}."
        )

    collection_rate = get_collection_rate(tenant_id)
    if collection_rate > 0:
        insights.append(
            f"Collection efficiency is at {collection_rate:.1f}% across recorded sales."
        )

    forecast = get_sales_forecast(tenant_id)
    if forecast:
        insights.append(
            f"Based on your recent sales trend, next month's sales are estimated at Rs. {forecast['forecast']:,.0f}."
        )

    if not insights:
        insights.append("Keep recording transactions so Munshi can start surfacing insights about your business.")

    return insights
