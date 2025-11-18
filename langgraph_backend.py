import google.generativeai as genai

def generate_title_from_message(text):
    prompt = f"Generate a single, short, descriptive chat title (3–6 words) for the following text. Return ONLY the title with no surrounding text, prefixes, numbering, or introductory phrases: {text}"
    model = genai.GenerativeModel("models/gemini-2.0-flash")
    resp = model.generate_content(prompt)
    return resp.text.strip()

def generate_reply_stream(history, kb_text, mode):
    formatted = ""
    for m in history:
        formatted += f"{m['role'].upper()}: {m['content']}\n\n"

    mode_prompt = "You are a helpful AI assistant."
    if mode == "Code Assistant":
        mode_prompt = "You are an expert coding assistant. Explain everything clearly."

    final_prompt = f"""
{mode_prompt}

Conversation so far:
{formatted}

Relevant context:
{kb_text}

Respond and continue the conversation.
"""

    model = genai.GenerativeModel("models/gemini-2.0-flash")

    return model.generate_content(
        final_prompt,
        stream=True
    )