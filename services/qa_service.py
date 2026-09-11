from services.analytics_service import (
    get_dashboard_summary,
    get_top_debtors,
    get_overdue_customers,
)


def answer_business_question(tenant_id, question):
    """
    Answer common business questions using
    real data from the Munshi AI database, scoped to the caller's tenant.
    """

    question = question.lower().strip()

    summary = get_dashboard_summary(tenant_id)

    sales = summary["sales"]
    paid = summary["paid"]
    due = summary["due"]
    expenses = summary["expenses"]
    profit = summary["profit"]

    # -----------------------------------
    # Total Sales
    # -----------------------------------

    if (
        "total sale" in question
        or "total sales" in question
        or "sale kitna" in question
        or "sales kitni" in question
        or "sales kitna" in question
    ):

        return (
            f"💰 Aapki total sales "
            f"**Rs. {sales:,.0f}** hain."
        )

    # -----------------------------------
    # Expenses
    # -----------------------------------

    if (
        "expense" in question
        or "expenses" in question
        or "kharcha" in question
        or "kharchay" in question
        or "kitna kharch" in question
    ):

        return (
            f"💸 Aapke total business expenses "
            f"**Rs. {expenses:,.0f}** hain."
        )

    # -----------------------------------
    # Top debtors ("sab se zyada udhaar kis ka hai?")
    # -----------------------------------

    if (
        "sab se zyada udhaar" in question
        or "highest due" in question
        or "top debtor" in question
        or "sab se zyada kis" in question
        or "zyada kis ka" in question
    ):

        debtors = get_top_debtors(tenant_id, 5)

        if not debtors:
            return "🎉 Abhi koi customer par udhaar baqi nahi hai."

        lines = [
            f"🔴 {name} — Rs. {due:,.0f}"
            for (_, name, _, _, due, _) in debtors
        ]

        return "**Top Udhaar (Outstanding):**\n\n" + "\n\n".join(lines)

    # -----------------------------------
    # Overdue / payment priority
    # -----------------------------------

    if (
        "kis se payment" in question
        or "payment leni" in question
        or "overdue" in question
        or "kon paisay nahi de raha" in question
        or "kon paise nahi de raha" in question
    ):

        overdue = get_overdue_customers(tenant_id)

        if not overdue:
            return "✅ Abhi koi customer 30 din se zyada overdue nahi hai."

        lines = [
            f"⚠️ {row['name']} — Rs. {row['due']:,.0f} — "
            f"{row['days_overdue']} din overdue"
            for row in overdue
        ]

        return "**Payment Priority:**\n\n" + "\n\n".join(lines)

    # -----------------------------------
    # Outstanding / Due
    # -----------------------------------

    if (
        "due" in question
        or "outstanding" in question
        or "lena hai" in question
        or "customers se" in question
        or "udhaar" in question
    ):

        return (
            f"📒 Customers se aapko total "
            f"**Rs. {due:,.0f}** lena hai."
        )

    # -----------------------------------
    # Paid / Collected
    # -----------------------------------

    if (
        "paid" in question
        or "receive" in question
        or "received" in question
        or "jama" in question
        or "vasool" in question
        or "collect" in question
    ):

        return (
            f"💵 Aapne total **Rs. {paid:,.0f}** "
            f"collect kiye hain."
        )

    # -----------------------------------
    # Profit
    # -----------------------------------

    if (
        "profit" in question
        or "munafa" in question
        or "faida" in question
        or "bachat" in question
    ):

        return (
            f"📈 Aapka estimated profit "
            f"**Rs. {profit:,.0f}** hai.\n\n"
            f"Sales: Rs. {sales:,.0f}\n\n"
            f"Expenses: Rs. {expenses:,.0f}"
        )

    # -----------------------------------
    # Complete Business Summary
    # -----------------------------------

    if (
        "summary" in question
        or "overview" in question
        or "business kaisa" in question
        or "business ka haal" in question
        or "business status" in question
    ):

        return (
            f"📊 **Business Summary**\n\n"
            f"💰 Sales: Rs. {sales:,.0f}\n\n"
            f"💵 Collected: Rs. {paid:,.0f}\n\n"
            f"📒 Outstanding: Rs. {due:,.0f}\n\n"
            f"💸 Expenses: Rs. {expenses:,.0f}\n\n"
            f"📈 Estimated Profit: Rs. {profit:,.0f}"
        )

    # -----------------------------------
    # Unknown question
    # -----------------------------------

    return (
        "🤵 Main abhi sales, expenses, payments, "
        "outstanding aur profit ke questions answer kar sakta hoon.\n\n"
        "Try asking:\n"
        "• Mera profit kitna hai?\n"
        "• Total sale kitni hai?\n"
        "• Customers se kitna lena hai?\n"
        "• Total kharcha kitna hua?"
    )