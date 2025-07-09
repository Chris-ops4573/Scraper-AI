from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from tools import get_weather, brave_search, get_current_date, github_code_search, vision_analyze
from langgraph.graph import StateGraph, END
import json
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, BaseMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict
import os
import base64
from tools import VisionInput
from dotenv import load_dotenv
import openai
import uuid

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

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
    "You are a helpful AI assistant deployed on a vs code extension frontend. Your main goal is to scrape github for usefule code according to what the user asks on top of their existing code which may be provided to you and assist them."
    "You can use tools like brave_search, get_current_date and github_code_search to do this. You need to provide the full detailed setup for code snippets you find on github, so the user can integrate it easily into their project."
    "This includes the file imports, terminal commands and any necessary configuration. And explain every code snippet in detail."
    "The user can also attach images, which is already processed and given to you. You have to use this information along with the prompt provided, if there is no prompt along with the image the user has uploaded just explain what are the contents of the image given to you donot recommend file imports, terminal commands and any necessary configuration until they ask for that specefically."
    "Also recommend what the user can do after using your code, for example if you have provided scaffolding code + login logic and UI recommend making a signup page next or a home page."
    "The user can also attach files they are currently viewing using the file context button, which will be provided to you as file_context in the request, if it empty and the user has asked a question like - explain, prompt the user to ask the question again this time with clicking the file context button."
    "Dont ask the user for more context just explain what you can do with the information provided to you and what the user can do next."
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
    user_message = data.get("prompt", "")
    image_base64 = data.get("image_base64")
    file_content = data.get("file_context")

    vision_input = VisionInput(image_base64=image_base64, prompt=user_message if user_message else "Describe this image.")

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if image_base64:
        # Use the vision tool to analyze the image and inject the result
        vision_result = vision_analyze(vision_input)
        # Combine user intent and vision result
        messages.append(HumanMessage(content=f"{user_message} : {vision_result}" + (f" : {file_content}" if file_content else "")))
    else:
        messages.append(HumanMessage(content=f"{user_message}" + (f" : {file_content}" if file_content else "")))

    try:
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
        result = chat_graph.invoke({"messages": messages}, config={"configurable": {"thread_id": "1"}})
        last_message = result["messages"][-1]
        reply = getattr(last_message, "content", str(last_message))
        return {"reply": reply, "transcription": transcribed_text}

    except Exception as e:
        print("Voice Chat Error:", e)
        return {"reply": f"Error processing voice request: {e}"}
