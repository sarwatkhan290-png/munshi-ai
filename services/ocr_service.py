import os
import json
import base64

try:
    from openai import OpenAI

    _client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

except Exception:
    _client = None


OCR_SYSTEM_PROMPT = """You are reading a photo of a handwritten Pakistani \
shopkeeper's khata (credit notebook page). Extract every line as a \
transaction.

Return STRICT JSON: a list of objects, each with exactly these keys:

{"customer": string, "amount": number, "type": "sale" | "payment"}

Rules:
- If a line just has a name and a number, assume it is a "sale" (credit
  given), unless the line clearly says paid/wapis/jama, in which case it's
  a "payment".
- Numbers may be written as plain digits or with "k"/"hazar" suffixes —
  convert everything to a plain number.
- If handwriting is unclear, make your best reasonable guess rather than
  skipping the line, but never invent a name or amount that has no basis
  in the image.
- Reply with ONLY the JSON list — no explanation, no markdown fences.
"""


def extract_transactions_from_image(image_bytes, mime_type="image/jpeg"):
    """
    Turn a photographed khata page into a list of draft transactions:
    [{"customer": ..., "amount": ..., "type": ...}, ...]

    Returns None if no API client is configured or the call fails, so
    the UI can show a clear "OCR unavailable" message instead of crashing.
    These results are drafts only — per the PRD's confirmation
    requirement, the shopkeeper must review/edit and confirm before
    anything is saved to the ledger.
    """

    if _client is None:
        return None

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the transactions from this khata page.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64_image}"
                            },
                        },
                    ],
                },
            ],
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        data = json.loads(raw)

        cleaned = []

        for row in data:
            cleaned.append({
                "customer": (row.get("customer") or "").strip().capitalize(),
                "amount": float(row.get("amount") or 0),
                "type": row.get("type") if row.get("type") in ("sale", "payment") else "sale",
            })

        return cleaned

    except Exception:
        return None
