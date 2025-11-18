# langgraph_backend.py
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")

def generate_title_from_message(message):
    """Return a short title (few-shot) using Gemini (non-stream)."""
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = (
        "Create a concise conversation title (3-6 words, no punctuation) based on the user's message.\n\n"
        "Example:\nUser: Explain blockchain simply\nTitle: Blockchain explained\n\n"
        "Example:\nUser: Help me write a resume for software engineer\nTitle: Software engineer resume tips\n\n"
        f"User: {message}\nTitle:"
    )
    resp = model.generate_content(prompt)
    return (resp.text or "").strip().splitlines()[0][:100] if resp and getattr(resp, "text", None) else "New Chat"

def generate_reply_stream(messages, kb_text="", mode="Chat"):
    """
    Stream generator for model replies. Yields chunk objects from SDK (each chunk has .text).
    The app will iterate over it to stream token-by-token.
    """
    model = genai.GenerativeModel(GEMINI_MODEL)

    # Compose instruction based on mode
    if mode == "Code Assistant":
        instruction = (
            "You are a senior programming assistant. Provide runnable code examples, explain briefly, "
            "and point out pitfalls. Prefer clear, tested snippets and mention required imports."
        )
    else:
        instruction = "You are a helpful assistant. Keep responses clear and concise."

    convo = ""
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        convo += f"{role.capitalize()}: {content}\n"

    prompt = f"{instruction}\n\nKnowledge:\n{kb_text}\n\nConversation:\n{convo}\nAssistant:"

    # stream=True returns an iterator of pieces
    return model.generate_content(prompt, stream=True)