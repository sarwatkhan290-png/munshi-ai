from datetime import datetime


def generate_receipt_text(customer_name, amount, paid, due, shop_name="Your Shop"):
    """
    Plain-text digital receipt, ready to copy/share or download.
    No AI needed here — it's just formatting real transaction numbers.
    """

    date_str = datetime.now().strftime("%d %b %Y")

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "       MUNSHI AI\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Shop: {shop_name}\n"
        f"Customer: {customer_name}\n\n"
        f"Purchase:   Rs. {amount:,.0f}\n"
        f"Paid:       Rs. {paid:,.0f}\n"
        f"Udhaar:     Rs. {due:,.0f}\n\n"
        f"Date: {date_str}\n\n"
        "Thank you!\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
