from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from database.userDatabase import router as user_router
from tools import get_weather, brave_search, get_current_date, github_code_search
from langgraph.graph import StateGraph, END
import json
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, BaseMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict
import os
import requests
import sqlite3
from dotenv import load_dotenv
import openai
import uuid

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
app.include_router(user_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- LangChain Tools ----------

langchain_llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o")

memory = MemorySaver()

tools = [get_weather, brave_search, get_current_date, github_code_search]

# ---------- LangGraph Flow ----------

# Bind tools to LLM
llm_with_tools = langchain_llm.bind_tools(tools)

def ensure_base_message(msg):
    """Convert dict or string to BaseMessage if needed."""
    if isinstance(msg, BaseMessage):
        return msg
    if isinstance(msg, dict):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            return HumanMessage(content=content)
        elif role == "assistant" or role == "ai":
            return AIMessage(content=content)
        elif role == "tool":
            return ToolMessage(content=content, name=msg.get("name", ""), tool_call_id=msg.get("tool_call_id", ""))
    if isinstance(msg, str):
        return HumanMessage(content=msg)
    raise ValueError(f"Cannot convert to BaseMessage: {msg}")

# System prompt for the chatbot
SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Your main goal is to scrape github for usefule code according to what the user asks on top of their existing code which may be provided to you and assist them."
    "You can use tools like get_weather, brave_search, get_current_date and github_code_search to do this. "
)

# Tool node
class BasicToolNode:
    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    def __call__(self, inputs: dict):
        messages = [ensure_base_message(m) for m in inputs.get("messages", [])]
        message = messages[-1]
        outputs = []
        for tool_call in getattr(message, "tool_calls", []):
            tool_result = self.tools_by_name[tool_call["name"]].invoke(
                tool_call["args"]
            )
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        # Append tool outputs to the message history
        return {"messages": messages + outputs}
    
tool_node = BasicToolNode(tools)

# LangGraph state
class ChatState(TypedDict):
    messages: list

def chatbot_node(state: ChatState) -> ChatState:
    try:
        messages = [ensure_base_message(m) for m in state["messages"]]
        response = llm_with_tools.invoke(messages)
        print("hi")
        return {"messages": messages + [response]}
    except Exception as e:
        print("error in chatbot_node:", e)
        # Append an AIMessage with the error
        return {"messages": state["messages"] + [AIMessage(content=f"Error: {str(e)}")]}
        
    
def chatbot_to_tools_or_end(state: ChatState) -> str:
    """Decide whether to go to tools or end after chatbot."""
    last_message = state["messages"][-1]
    # If the last message has tool_calls attribute and it's non-empty, go to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# Build the graph
builder = StateGraph(ChatState)
builder.add_node("chatbot", chatbot_node)
builder.add_node("tools", tool_node)
builder.set_entry_point("chatbot")
builder.add_conditional_edges("chatbot", chatbot_to_tools_or_end)
builder.add_edge("tools", "chatbot")
builder.add_edge("chatbot", END)
chat_graph = builder.compile(checkpointer=memory)

# ---------- Endpoints ----------

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    username = data.get("username")
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ]
        # Use HumanMessage for user input
        result = chat_graph.invoke({"messages": messages}, config={"configurable": {"thread_id": "1"}})
        last_message = result["messages"][-1]
        reply = getattr(last_message, "content", str(last_message))
        return {"reply": reply} 
    except Exception as e:
        print("LangGraph Error:", e)
        return {"reply": f"Error processing request: {e}"}

@app.post("/chat-voice")
async def chat_voice(
    audio: UploadFile = File(...),
    username: str = Form(...),
    role: str = Form(...)
):
    try:
        contents = await audio.read()
        safe_filename = f"temp_{uuid.uuid4()}.m4a"

        with open(safe_filename, "wb") as f:
            f.write(contents)

        with open(safe_filename, "rb") as file_for_whisper:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=file_for_whisper
            )

        transcribed_text = transcription.text
        print("Transcription:", transcribed_text)

        os.remove(safe_filename)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=transcribed_text)
        ]
        # Use HumanMessage for user input
        result = chat_graph.invoke({"messages": messages}, config={"configurable": {"thread_id": username}})
        last_message = result["messages"][-1]
        reply = getattr(last_message, "content", str(last_message))
        return {"reply": reply, "transcription": transcribed_text}

    except Exception as e:
        print("Voice Chat Error:", e)
        return {"reply": f"Error processing voice request: {e}"}
