import os

try:
    from openai import OpenAI

    _client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

except Exception:
    _client = None


def transcribe_audio(uploaded_file):
    """
    Transcribe an uploaded audio file (wav/mp3/m4a) to text using
    Whisper, so a shopkeeper can speak a transaction in Urdu/Roman Urdu
    instead of typing it.

    `uploaded_file` is a Streamlit UploadedFile — it already behaves
    like a file object, so it can be passed straight to the API.

    Returns None if no API client is configured or the call fails.
    """

    if _client is None:
        return None

    try:
        # Whisper needs a name with an extension to infer the format.
        uploaded_file.name = uploaded_file.name or "audio.wav"

        transcript = _client.audio.transcriptions.create(
            model="whisper-1",
            file=uploaded_file,
        )

        return transcript.text.strip()

    except Exception:
        return None
