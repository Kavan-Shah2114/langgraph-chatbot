# app.py — final (inject uploaded file text into convo, robust RAG, safe rerun)
import os
import io
import uuid
import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import google.generativeai as genai

from fetch import (
    authenticate_user, create_user,
    add_thread_to_db, fetch_threads, delete_thread,
    update_thread_topic, touch_thread, set_thread_pinned,
    save_message, load_messages,
    save_document, search_documents
)
from langgraph_backend import generate_reply_stream, generate_title_from_message

# Load env and configure model
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# ---------- safe rerun ----------
def safe_rerun():
    """Use st.rerun if available; otherwise stop the script."""
    try:
        if hasattr(st, "rerun"):
            st.rerun()
            return
    except Exception:
        pass
    # fallback: no experimental rerun usage to avoid AttributeError
    st.stop()

# ---------- page config ----------
st.set_page_config(page_title="SmartLang Chat", layout="wide")
st.sidebar.title("Conversations")

# ---------- auth ----------
if "user" not in st.session_state:
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            user = authenticate_user(username, password)
            if user:
                st.session_state["user"] = user
                safe_rerun()
            else:
                st.error("Incorrect username or password.")
    with col2:
        if st.button("Create Account"):
            if username and password:
                create_user(username, password)
                st.success("Account created. Please login.")
            else:
                st.error("Provide both username and password.")
    st.stop()

user = st.session_state["user"]
user_id = user["id"]

# ---------- session init ----------
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = None
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []
if "delete_confirm" not in st.session_state:
    st.session_state["delete_confirm"] = None

# ---------- mode ----------
mode = st.sidebar.radio("Mode", ["Chat", "Code Assistant"], index=0)

# ---------- sidebar: always load fresh threads ----------
threads = fetch_threads(user_id)

for t in threads:
    tid = t["id"]
    topic = t.get("topic") or "New Chat"
    pinned = t.get("pinned", False)

    row = st.sidebar.container()
    c1, c2, c3 = row.columns([6, 1.5, 1.5])

    # Open thread
    if c1.button(f"{'📌 ' if pinned else ''}{topic}", key=f"open_{tid}"):
        st.session_state["thread_id"] = tid
        st.session_state["message_history"] = load_messages(tid)
        st.session_state["delete_confirm"] = None
        safe_rerun()

    # Pin/unpin
    if c2.button("📌" if not pinned else "📍", key=f"pin_{tid}"):
        set_thread_pinned(tid, not pinned)
        safe_rerun()

    # Delete (ask confirmation in sidebar)
    if c3.button("🗑", key=f"menu_{tid}"):
        st.session_state["delete_confirm"] = tid
        safe_rerun()

# Show delete confirmation if set
if st.session_state.get("delete_confirm"):
    confirm_tid = st.session_state["delete_confirm"]
    confirm_thread = next((x for x in threads if x["id"] == confirm_tid), None)
    if confirm_thread:
        st.sidebar.warning(f"⚠️ Delete '{confirm_thread.get('topic', 'New Chat')}'?")
        col_yes, col_no = st.sidebar.columns(2)
        if col_yes.button("✓ Yes", key=f"confirm_delete_{confirm_tid}"):
            delete_thread(confirm_tid)
            if st.session_state.get("thread_id") == confirm_tid:
                st.session_state["thread_id"] = None
                st.session_state["message_history"] = []
            st.session_state["delete_confirm"] = None
            safe_rerun()
        if col_no.button("✗ Cancel", key=f"cancel_delete_{confirm_tid}"):
            st.session_state["delete_confirm"] = None
            safe_rerun()

st.sidebar.markdown("---")
if st.sidebar.button("➕ New Chat"):
    new_tid = str(uuid.uuid4())
    add_thread_to_db(new_tid, "New Chat", user_id)
    st.session_state["thread_id"] = new_tid
    st.session_state["message_history"] = []
    st.session_state["delete_confirm"] = None
    safe_rerun()

st.sidebar.markdown("---")
st.sidebar.write(f"Logged in as **{user['username']}**")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    safe_rerun()

# ---------- main layout ----------
col_left, col_right = st.columns([3, 1])

with col_left:
    st.header("SmartLang Chat")

    # show current conversation
    if not st.session_state.get("thread_id"):
        st.info("Select a conversation or create a new one.")
    else:
        for msg in st.session_state.get("message_history", []):
            # map unknown roles to assistant for display
            role = msg.get("role", "assistant")
            display_role = role if role in ("user", "assistant") else "assistant"
            with st.chat_message(display_role):
                st.markdown(msg.get("content", ""))

    # chat input + file uploader
    with st.form("chat_form", clear_on_submit=True):
        uploaded = st.file_uploader("Attach file (optional)", type=["pdf", "txt", "md"])
        user_input = st.text_input("Message...")
        send = st.form_submit_button("Send")

    if send and (user_input or uploaded):
        tid = st.session_state.get("thread_id")
        if not tid:
            st.error("Create or select a chat first.")
        else:
            # --- handle uploads ---
            if uploaded:
                raw = uploaded.read()
                file_text = ""
                if uploaded.name.lower().endswith(".pdf"):
                    try:
                        reader = PdfReader(io.BytesIO(raw))
                        pages = [p.extract_text() or "" for p in reader.pages]
                        file_text = "\n\n".join(pages)
                    except Exception as e:
                        st.error("Could not extract PDF text: " + str(e))
                        file_text = ""
                    finally:
                        # Ensure we always close the reader/file handle if necessary (though PyPDF2 should manage this)
                        pass
                else:
                    try:
                        file_text = raw.decode("utf-8", errors="ignore")
                    except Exception:
                        file_text = ""

                if file_text.strip():
                    # Save to DB (per-thread)
                    save_document(uploaded.name, file_text, tid)

                    # Save a user-visible upload message
                    save_message(tid, "user", f"📎 Uploaded: {uploaded.name}")
                    st.session_state["message_history"].append({"role": "user", "content": f"📎 Uploaded: {uploaded.name}"})

                    # Inject file text into the conversation as a system message (so model can immediately use it)
                    # We add a truncated preview to the chat to avoid huge UI messages, but we store full text in DB.
                    preview = file_text[:1200] + ("..." if len(file_text) > 1200 else "")
                    system_content = f"File uploaded: {uploaded.name}\n\nFull file text has been saved to the chat's knowledge base. Preview:\n\n{preview}"
                    # Save system message in messages table so it is persisted
                    save_message(tid, "system", system_content)
                    # Also append to session history for immediate availability
                    st.session_state["message_history"].append({"role": "system", "content": system_content})
                else:
                    st.warning("Uploaded file had no extractable text.")

            # --- handle user text ---
            if user_input:
                save_message(tid, "user", user_input)
                st.session_state["message_history"].append({"role": "user", "content": user_input})

            # --- Auto-title: only if thread has default title ---
            # Get fresh thread topics from DB to avoid stale state
            fresh_threads = fetch_threads(user_id)
            topic_map = {x["id"]: x.get("topic") for x in fresh_threads}
            current_topic = topic_map.get(tid, "")

            if not current_topic or current_topic.strip().lower() in ("new chat", "untitled", "chat"):
                # *** START OF TITLE GENERATION CHANGE ***
                # Construct a more descriptive base string for better title generation
                if uploaded and user_input:
                    # Combine file and user input for the most descriptive title
                    base = f"Query on '{uploaded.name}': {user_input}"
                elif uploaded:
                    # Title based on just the uploaded file
                    base = f"Analysis of '{uploaded.name}'"
                elif user_input:
                    # Title based on just the user input
                    base = user_input
                else:
                    base = "New Chat"
                # *** END OF TITLE GENERATION CHANGE ***
                
                try:
                    # Request the title based on the descriptive 'base' input
                    new_title = generate_title_from_message(base)
                except Exception:
                    # Fallback if LLM call fails
                    new_title = base[:80]
                update_thread_topic(tid, new_title)

            touch_thread(tid)

            # --- RAG: ALWAYS fetch this thread's docs so the model can use uploaded file text ---
            docs = search_documents("", thread_id=tid, limit=10)  # empty query -> return docs for thread
            kb_text = "\n\n".join([f"DOCUMENT: {d['title']}\n{d['content']}" for d in docs]) if docs else ""

            # --- streaming reply from model ---
            stream = generate_reply_stream(st.session_state["message_history"], kb_text=kb_text, mode=mode)
            assistant_text = ""
            with st.chat_message("assistant"):
                placeholder = st.empty()
                for chunk in stream:
                    # chunk may have .text or .output depending on SDK / bindings
                    piece = getattr(chunk, "text", None) or getattr(chunk, "output", None) or ""
                    assistant_text += piece
                    placeholder.markdown(assistant_text)

            # Save assistant response
            save_message(tid, "assistant", assistant_text)
            st.session_state["message_history"].append({"role": "assistant", "content": assistant_text})

            # finally rerun to update UI & sidebar (fresh threads)
            safe_rerun()

with col_right:
    st.header("Knowledge Base (This Chat)")
    tid = st.session_state.get("thread_id")
    if tid:
        docs = search_documents("", thread_id=tid, limit=50)
        if docs:
            for d in docs:
                st.markdown(f"**{d['title']}**")
                # show short preview in KB
                preview = d["content"][:400] + ("..." if len(d["content"]) > 400 else "")
                st.write(preview)
        else:
            st.info("No files uploaded for this chat.")
    else:
        st.info("Select a chat to view its documents.")