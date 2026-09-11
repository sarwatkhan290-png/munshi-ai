import os
import re
import json

# ==================================================
# LLM CLIENT (optional — falls back to regex parser
# if no API key is set, or if the call fails for any
# reason: no internet, bad key, rate limit, etc.)
# ==================================================

try:
    from openai import OpenAI

    _client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

except Exception:
    _client = None


LLM_SYSTEM_PROMPT = """You are a transaction-extraction engine for a Pakistani \
shopkeeper's digital khata (ledger) app called Munshi AI.

Convert the shopkeeper's message (English, Urdu, or Roman Urdu) into STRICT \
JSON with exactly these keys:

{"type": "sale" | "payment" | "unknown", "customer": string or null, \
"amount": number, "paid": number}

Rules:
- "amount" is the total value of a sale (0 if type is "payment" or "unknown").
- "paid" is how much money the customer actually handed over right now.
- Convert "hazar"/"hazaar" to thousands, and spelled-out Urdu/Roman-Urdu \
numbers (ek, do, teen, char, paanch, chay/chhay, saat, aath, nau, dus...) \
into digits.
- If the message is only about money received with no new sale, set type \
to "payment" and set amount equal to paid.
- If no customer name can be identified, set "customer" to null.
- Never invent a customer name, amount, or paid value that isn't in the text.
- Reply with ONLY the JSON object — no explanation, no markdown fences.
"""


def parse_transaction_llm(text):
    """
    Ask the LLM to extract structured transaction data.

    Returns None (instead of raising) if no client is configured, or the
    call fails for any reason, so callers can fall back to the offline
    regex parser. This function never touches the database directly —
    it only returns structured data for the caller to validate and save,
    per the "LLM never writes to the DB directly" rule.
    """

    if _client is None:
        return None

    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        data = json.loads(raw)

        amount = float(data.get("amount") or 0)
        paid = float(data.get("paid") or 0)

        # Recompute due ourselves rather than trust the LLM's arithmetic.
        due = max(amount - paid, 0)

        return {
            "type": data.get("type", "unknown"),
            "customer": data.get("customer") or None,
            "amount": amount,
            "paid": paid,
            "due": due,
            "description": text,
            "source": "llm",
        }

    except Exception:
        return None


def parse_transaction(text):
    """
    Public entry point used by the rest of the app.

    Tries the LLM parser first (handles word-numbers, reordered
    sentences, mixed Urdu/English far better than regex). Falls back
    to the offline regex parser if no API key is configured or the
    call fails — so the app still works with zero internet/API cost.
    """

    llm_result = parse_transaction_llm(text)

    if llm_result is not None:
        return llm_result

    return _parse_transaction_regex(text)




def parse_amount(text):
    """
    Convert amounts such as:

    5000
    5k
    10 hazar
    10 hazaar
    6000ka

    into numbers.
    """

    text = (
        text.lower()
        .replace(",", "")
        .strip()
    )

    # Examples:
    # 10 hazar
    # 10 hazaar
    # 5k
    # 6000k
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(hazar|hazaar|k)\b",
        text
    )

    if match:

        amount = float(match.group(1))

        return amount * 1000

    # Normal number
    match = re.search(
        r"\b\d+(?:\.\d+)?\b",
        text
    )

    if match:

        return float(match.group())

    return 0


# ==================================================
# CUSTOMER EXTRACTION
# ==================================================

def extract_customer(text):
    """
    Detect customer names from common Roman Urdu
    sentence patterns.

    Supports:

    Ahmed ne 6000 ka maal liya
    Ahmed ny 6000 ka sawda liya
    Ahmedny6000ka sawda liya
    Ahmed 6000 ka maal liya
    Ahmed ko 6000 ka maal diya
    """

    patterns = [

        # Ahmed ne ...
        # Ahmed ny ...
        r"^([a-zA-Z]+)\s*(?:ne|ny)\s*",

        # Ahmed ka ...
        # Ahmed ko ...
        r"^([a-zA-Z]+)\s*(?:ka|ko)\s*",

        # Ahmed 6000 ...
        r"^([a-zA-Z]+)\s+\d",

        # Ahmed6000...
        r"^([a-zA-Z]+)(?=\d)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(1).capitalize()

    return None


# ==================================================
# SALE AMOUNT
# ==================================================

def extract_sale_amount(text):
    """
    Detect the main sale amount.

    Supports:

    6000
    6k
    6 hazar
    6000 ka
    6000ka
    """

    # 6 hazar
    # 6 hazaar
    # 6k
    # 6000ka
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*"
        r"(hazar|hazaar|k)\b"
        r"\s*(?:ka|ki)?",
        text,
        re.IGNORECASE
    )

    if match:

        amount = float(match.group(1))

        if match.group(2).lower() in [
            "hazar",
            "hazaar",
            "k"
        ]:

            amount *= 1000

        return amount

    # 6000 ka
    # 6000 ki
    # 6000ka
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:ka|ki)",
        text,
        re.IGNORECASE
    )

    if match:

        return float(match.group(1))

    # Fallback
    return parse_amount(text)


# ==================================================
# PAID AMOUNT
# ==================================================

def extract_paid_amount(text):
    """
    Detect money actually paid by customer.

    Supports:

    200 diye
    200 diya
    200 paid
    200 jama
    2 hazar diye
    2k paid

    IMPORTANT:
    'wapis' is NOT treated as paid.
    """

    patterns = [

        # 200 diye
        # 200 diya
        # 200 paid
        # 200 jama
        # 2 hazar diye
        # 2k paid
        r"(\d+(?:\.\d+)?)\s*"
        r"(hazar|hazaar|k)?\s*"
        r"(?:de\s+)?"
        r"(?:diye|diya|paid|pay|jama)\b",

        # paid 200
        # pay 200
        # jama 200
        r"(?:paid|pay|jama)\s*"
        r"(\d+(?:\.\d+)?)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            amount = float(match.group(1))

            # First pattern has a unit group
            if len(match.groups()) >= 2:

                unit = match.group(2)

                if unit:

                    amount *= 1000

            return amount

    return 0


# ==================================================
# TRANSACTION PARSER
# ==================================================

def _parse_transaction_regex(text):
    """
    Convert natural-language business transactions
    into structured financial data.

    Supports:

    English
    Roman Urdu
    Compact typing
    """

    original_text = text

    text = (
        text.lower()
        .replace(",", "")
        .strip()
    )

    # ==================================================
    # CUSTOMER
    # ==================================================

    customer = extract_customer(text)

    # ==================================================
    # SALE DETECTION
    # ==================================================

    sale_words = [
        "sale",
        "maal",
        "sawda",
        "sauda",
        "liya",
        "sold",
        "bought",
        "becha"
    ]

    is_sale = any(
        word in text
        for word in sale_words
    )

    # ==================================================
    # PAYMENT DETECTION
    # ==================================================

    payment_words = [
        "paid",
        "pay",
        "payment",
        "diye",
        "diya",
        "jama"
    ]

    is_payment = any(
        word in text
        for word in payment_words
    )

    # ==================================================
    # SALE
    # ==================================================

    if is_sale:

        amount = extract_sale_amount(text)

        paid = extract_paid_amount(text)

        due = max(
            amount - paid,
            0
        )

        return {
            "type": "sale",
            "customer": customer,
            "amount": amount,
            "paid": paid,
            "due": due,
            "description": original_text,
            "source": "regex"
        }

    # ==================================================
    # PAYMENT
    # ==================================================

    if is_payment:

        amount = parse_amount(text)

        return {
            "type": "payment",
            "customer": customer,
            "amount": amount,
            "paid": amount,
            "due": 0,
            "description": original_text,
            "source": "regex"
        }

    # ==================================================
    # UNKNOWN
    # ==================================================

    return {
        "type": "unknown",
        "customer": customer,
        "amount": 0,
        "paid": 0,
        "due": 0,
        "description": original_text,
        "source": "regex"
    }
