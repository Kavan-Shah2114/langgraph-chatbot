from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict,Annotated,Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.graph.message import add_messages 
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from fetch import fetch_threads

load_dotenv()

class ChatState(TypedDict):
    messages: Annotated[Optional[list[BaseMessage]], add_messages]

model = ChatGoogleGenerativeAI(model='gemini-1.5-flash')

graph = StateGraph(ChatState)

def chat_node(state: ChatState):

    messages = state['messages']

    response = model.invoke(state['messages'])

    return {'messages' : [response]}

graph.add_node('chat_node', chat_node)

graph.add_edge(START,'chat_node')
graph.add_edge('chat_node',END)

conn = sqlite3.connect('chatbot.db',check_same_thread=False)

checkpointer = SqliteSaver(conn=conn)

chatbot = graph.compile(checkpointer=checkpointer)