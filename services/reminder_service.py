import os
import urllib.parse

try:
    from openai import OpenAI

    _client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

except Exception:
    _client = None


COLLECTION_SAFETY_RULE = (
    "The message must be polite and respectful, never threatening, "
    "shaming, or pressuring. The shopkeeper — not the AI — has final "
    "say over whether and how to follow up."
)


def generate_whatsapp_link(message, phone_number=""):
    """Build a WhatsApp URL that opens a prefilled message for the shopkeeper."""
    encoded = urllib.parse.quote(message)
    if phone_number:
        return f"https://wa.me/{phone_number}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def generate_reminder(customer_name, due_amount, shop_name="the shop"):
    """
    A short, culturally appropriate Urdu/English payment reminder.
    Works even with no API key — falls back to a fixed template
    matching the one in the original product brief.
    """

    if _client is not None:
        try:
            prompt = (
                f"Write a short, polite WhatsApp-style payment reminder in "
                f"Roman Urdu from {shop_name} to a customer named "
                f"{customer_name} who owes Rs. {due_amount:,.0f}. "
                f"{COLLECTION_SAFETY_RULE} Keep it under 40 words."
            )

            response = _client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.choices[0].message.content.strip()

        except Exception:
            pass

    return (
        f"Assalam-o-Alaikum {customer_name} bhai,\n\n"
        f"Aap ke account mein Rs. {due_amount:,.0f} baqi hain. "
        f"Jab aap ko sahulat ho, payment kar dein.\n\n"
        f"Shukriya."
    )


def generate_call_script(customer_name, due_amount, days_overdue):
    """
    A short script the shopkeeper can read out loud when following up —
    a stand-in for the PRD's "AI-assisted voice collection call", which
    needs telephony infrastructure (e.g. Twilio) that's out of scope
    for this build. This still delivers the useful part: knowing what
    to say, respectfully.
    """

    if _client is not None:
        try:
            prompt = (
                f"Write a short, friendly phone call script (Roman Urdu, "
                f"under 60 words) for a shopkeeper calling a customer named "
                f"{customer_name} whose payment of Rs. {due_amount:,.0f} is "
                f"{days_overdue} days overdue. {COLLECTION_SAFETY_RULE}"
            )

            response = _client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.choices[0].message.content.strip()

        except Exception:
            pass

    return (
        f"Assalam-o-Alaikum {customer_name} bhai, kaisay hain aap?\n\n"
        f"Main sirf yaad dilana chahta tha ke aap ka Rs. {due_amount:,.0f} "
        f"ka hisaab {days_overdue} din se pending hai. Jab aap ke liye "
        f"mumkin ho, payment kar dijiyega.\n\n"
        f"Shukriya, apna khayal rakhiyega."
    )
