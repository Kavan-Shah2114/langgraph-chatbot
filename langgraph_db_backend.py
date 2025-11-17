import sqlite3
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, Annotated, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv

load_dotenv()

# ------------------- DB Setup -------------------
conn = sqlite3.connect("chatbot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    topic TEXT
)
""")
conn.commit()

# ------------------- LangGraph Setup -------------------
class ChatState(TypedDict):
    messages: Annotated[Optional[list[BaseMessage]], add_messages]

model = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

graph = StateGraph(ChatState)

def chat_node(state: ChatState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

checkpointer = SqliteSaver(conn=conn)
chatbot = graph.compile(checkpointer=checkpointer)