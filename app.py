# app.py
import os
import io
import uuid
import datetime
import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import google.generativeai as genai

from fetch import (
    authenticate_user, create_user,
    add_thread_to_db, fetch_threads, delete_thread,
    update_thread_topic, touch_thread, set_thread_pinned,
    save_message, load_messages,
    save_document, search_documents
)
from langgraph_backend import generate_reply_stream, generate_title_from_message

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ---------- Session and auth ----------
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
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")
    with col2:
        if st.button("Create account"):
            if username and password:
                create_user(username, password)
                st.success("Created — please login.")
            else:
                st.error("Provide username and password")
    st.stop()

user = st.session_state["user"]
user_id = user["id"]

# initialize session state
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = None
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []
if "thread_topics" not in st.session_state:
    st.session_state["thread_topics"] = {}
if "_rerun_requested" not in st.session_state:
    st.session_state["_rerun_requested"] = False

def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        try:
            st.experimental_rerun()
            return
        except Exception:
            pass
    if hasattr(st, "rerun"):
        try:
            st.rerun()
            return
        except Exception:
            pass
    st.session_state["_rerun_requested"] = True
    st.stop()

# ---------- UI config ----------
st.set_page_config(page_title="SmartLang Chat", layout="wide")

# Sidebar: threads + new chat + mode
st.sidebar.title("Conversations")
mode = st.sidebar.radio("Mode", ["Chat", "Code Assistant"], index=0)

threads = fetch_threads(user_id)
# update local thread topic cache
for t in threads:
    st.session_state["thread_topics"][t["id"]] = t.get("topic", "New Chat")

for t in threads:
    tid = t["id"]
    label = t.get("topic") or "New Chat"
    pinned = t.get("pinned", False)

    row = st.sidebar.container()
    c1, c2, c3 = row.columns([7,1,1])
    if c1.button(f"{'📌 ' if pinned else ''}{label}", key=f"open_{tid}"):
        # load messages from DB
        msgs = load_messages(tid)
        st.session_state["thread_id"] = tid
        st.session_state["message_history"] = msgs

    if c2.button("📌" if not pinned else "❌", key=f"pin_{tid}"):
        set_thread_pinned(tid, not pinned)
        safe_rerun()

    if c3.button("⋮", key=f"menu_{tid}"):
        # show small confirmation area under this thread in sidebar
        st.sidebar.write(f"Delete '{label}'?")
        if st.sidebar.button("Delete Chat", key=f"delete_{tid}"):
            delete_thread(tid)
            # refresh local caches
            threads = fetch_threads(user_id)
            st.session_state["thread_id"] = None
            st.session_state["message_history"] = []
            safe_rerun()

st.sidebar.markdown("---")
if st.sidebar.button("➕ New Chat"):
    new_tid = str(uuid.uuid4())
    add_thread_to_db(new_tid, "New Chat", user_id)
    st.session_state["thread_id"] = new_tid
    st.session_state["message_history"] = []
    safe_rerun()

st.sidebar.markdown("---")
st.sidebar.write("Logged in as:")
st.sidebar.write(user["username"])
if st.sidebar.button("Logout"):
    del st.session_state["user"]
    safe_rerun()

# ---------- Main UI ----------
col_left, col_right = st.columns([3,1])
with col_left:
    st.header("SmartLang Chat")
    if st.session_state["thread_id"] is None:
        st.info("Select a conversation on the left or click New Chat.")
    else:
        # show conversation messages
        for m in st.session_state["message_history"]:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    # Chat input + in-line file uploader
    with st.form("chat_form", clear_on_submit=False):
        uploaded = st.file_uploader("Attach file (optional)", type=["pdf","txt","png","jpg"])
        user_input = st.text_input("Type your message here...", key="chat_input")
        submitted = st.form_submit_button("Send")

    if submitted and (user_input or uploaded):
        tid = st.session_state["thread_id"]
        if tid is None:
            st.error("Create or select a chat first.")
        else:
            # handle file attachment (saved to KB tied to thread)
            if uploaded:
                raw = uploaded.read()
                if uploaded.name.lower().endswith(".pdf"):
                    try:
                        reader = PdfReader(io.BytesIO(raw))
                        text_pages = [p.extract_text() or "" for p in reader.pages]
                        file_text = "\n\n".join(text_pages)
                    except Exception as e:
                        st.error("PDF read failed: " + str(e))
                        file_text = ""
                else:
                    file_text = raw.decode("utf-8", errors="ignore")
                if file_text.strip():
                    save_document(uploaded.name, file_text, tid)
                    # show as a user message that a file was uploaded
                    save_message(tid, "user", f"📎 Uploaded: {uploaded.name}")
                    st.session_state["message_history"].append({"role":"user","content":f"📎 Uploaded: {uploaded.name}"})

            # append user text message
            if user_input:
                save_message(tid, "user", user_input)
                st.session_state["message_history"].append({"role":"user","content":user_input})

            # If first user message and topic is New Chat, auto-title it
            current_topic = None
            for t in threads:
                if t["id"] == tid:
                    current_topic = t.get("topic")
                    break
            if current_topic == "New Chat":
                # generate accurate title
                title = generate_title_from_message(user_input or (uploaded.name if uploaded else "New Chat"))
                update_thread_topic(tid, title)

            # touch thread ordering
            touch_thread(tid)

            # RAG: search documents only for this thread
            docs = search_documents(user_input or "", thread_id=tid, limit=3)
            rag_text = "\n\n".join([f"DOCUMENT: {d['title']}\n{d['content']}" for d in docs]) if docs else ""

            # start streaming assistant reply
            stream = generate_reply_stream(st.session_state["message_history"], kb_text=rag_text, mode=mode)
            assistant_text = ""
            with st.chat_message("assistant"):
                placeholder = st.empty()
                for chunk in stream:
                    # chunk.text contains incremental text for many SDKs
                    text_piece = getattr(chunk, "text", None) or getattr(chunk, "output", None) or ""
                    assistant_text += text_piece
                    placeholder.markdown(assistant_text)

            # save assistant message
            save_message(tid, "assistant", assistant_text)
            st.session_state["message_history"].append({"role":"assistant","content":assistant_text})
            safe_rerun()

with col_right:
    st.header("Knowledge Base (thread)")
    st.write("Files uploaded in this chat (only visible to this chat):")
    if st.session_state["thread_id"]:
        docs = search_documents("", thread_id=st.session_state["thread_id"], limit=50)
        if docs:
            for d in docs:
                st.markdown(f"**{d['title']}**")
                st.write(d["content"][:400] + ("..." if len(d["content"]) > 400 else ""))
        else:
            st.info("No files uploaded for this chat.")
    else:
        st.info("Select a chat to view files uploaded for it.")