import streamlit as st
from langgraph_chatbot import chatbot  
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import uuid

# **************************************** utility functions *************************

def generate_thread_id():
    return str(uuid.uuid4())

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(thread_id, "New Chat")
    st.session_state['message_history'] = []

def add_thread(thread_id, topic_name="New Chat"):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)
        st.session_state['thread_topics'][thread_id] = topic_name

def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    return state.values.get('messages', [])


# **************************************** Session Setup *****************************
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

if 'thread_topics' not in st.session_state:
    st.session_state['thread_topics'] = {}

add_thread(st.session_state['thread_id'], "New Chat")


# **************************************** Sidebar UI ********************************
st.sidebar.title('LangGraph Chatbot')

if st.sidebar.button('New Chat'):
    reset_chat()

st.sidebar.header('My Conversations')

for thread_id in st.session_state['chat_threads'][::-1]:
    topic_name = st.session_state['thread_topics'].get(thread_id, "New Chat")
    if st.sidebar.button(topic_name, key=f"topic_button_{thread_id}"):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []
        for msg in messages:
            role = 'user' if isinstance(msg, HumanMessage) else 'assistant'
            temp_messages.append({'role': role, 'content': msg.content})

        st.session_state['message_history'] = temp_messages


# **************************************** Main UI ***********************************

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

user_input = st.chat_input('Type here')

if user_input:
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

    if st.session_state['thread_topics'][st.session_state['thread_id']] == "New Chat":
        rename_prompt = f"Summarize this user request into a short, clear conversation title (max 5 words): {user_input}"
        title_response = model.invoke([HumanMessage(content=rename_prompt)])
        title = title_response.content.strip()
        st.session_state['thread_topics'][st.session_state['thread_id']] = title

    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    with st.chat_message("assistant"):
        def ai_only_stream():
            full_history = []
            for m in st.session_state["message_history"]:
                if m["role"] == "user":
                    full_history.append(HumanMessage(content=m["content"]))
                else:
                    full_history.append(AIMessage(content=m["content"]))

            full_history.append(HumanMessage(content=user_input))

            for chunk in model.stream(full_history):
                if chunk.content:
                    yield chunk.content

        ai_message = st.write_stream(ai_only_stream())

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})

    chatbot.invoke(
        {"messages": [HumanMessage(content=user_input), AIMessage(content=ai_message)]},
        config={'configurable': {'thread_id': st.session_state['thread_id']}}
    )