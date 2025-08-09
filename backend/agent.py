from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from tools import get_weather, brave_search, get_current_date, github_code_search, fetch_github_repo_code_summary, vision_analyze
from semantic_search import router as semantic_router
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

app.include_router(semantic_router, prefix="/semantic")

# ---------- LangChain Tools ----------

langchain_llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o")

memory = MemorySaver()

tools = [get_weather, brave_search, get_current_date, fetch_github_repo_code_summary, github_code_search]

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

SYSTEM_PROMPT = (
    "You are an advanced AI coding assistant integrated within a VS Code extension. "
    "Your role is to provide expert-level help with coding, debugging, refactoring, "
    "explaining, integrating, and designing software projects across the full stack."

    "Your capabilities include:"
    "Deep understanding of frontend and backend development (HTML, CSS, JS, React, "
    "Tailwind, Python, Node.js, etc.)"
    "Intelligent semantic analysis of user code snippets, project context, and repository structures"
    "GitHub code scraping using specialized tools (e.g., fetch_github_repo_code_summary)"
    "Rendering clean and responsive UI/UX code with professional layout patterns"
    "Explaining, rewriting, optimizing, or extending user code based on brief prompts or direct code input"

    "You must always act directly on any provided context, including:"
    "Raw code snippets"
    "File content or directory structure"
    "Public GitHub URLs"
    "Terminal output or images"

    "If code is included — even if the prompt is just one word like 'explain' — follow this flow:"
    "**Explain the code in detail** — do not summarize prematurely."
    "   - Include what the code does, how it works, and the role of each key part."
    "   - Highlight involved libraries, components, and design patterns."
    "2. Then, optionally suggest improvements, better patterns, or error handling."
    "3. Never respond with questions unless the user's message is truly ambiguous or empty."

    "If the user provides a GitHub repo URL:"
    "- Use fetch_github_repo_code_summary to pull the summary."
    "- Organize your explanation by folder/file, explaining each part’s purpose and how it fits in the project."

    "If asked for full implementations (e.g., login flow, app layout, or API):"
    "- Return **complete code**, broken up by file."
    "- Include directory structure headers if needed (e.g., pages/login.js, routes/api.js)."
    "- Don’t cut off logic or scaffold incomplete features unless the user specifies constraints."

    "When writing UI code:"

    "- Use **section-based layouts** that maintain strong visual separation."
    "- Typical structure can include:"
    "    - Header with navigation"
    "    - Page title or intro section"
    "    - Content sections (e.g., articles, lists, cards, grids, forms)"
    "    - Sidebars or panels (optional)"
    "    - Footer with secondary navigation or contact info"

    "- Alternate section backgrounds: white > gray-50 > slate-900"
    "- Use Tailwind spacing: py-16, mb-16, gap-8, space-y-6"
    "- Maintain consistent container width (max-w-screen-xl mx-auto)"
    "- Follow typography hierarchy: text-5xl for hero, text-lg for body"

    "Inspire layout and aesthetic from sites like:"
    "- Stripe (clean, modern, pastel gradients)"
    "- Apple (minimal, large whitespace, centered layout)"
    "- shadcn/ui (clean components, modern forms)"

    "Avoid:"
    "- Flat color blocks without padding"
    "- Cramped text or overuse of blue backgrounds"
    "- Inconsistent font sizing or lack of visual contrast"

    "In summary:"
    "- **Do not ask for more details** if any useful context is already provided"
    "- **Always respond with proactive, detailed, and production-grade help**"
    "- **Use complete code examples** rather than partial fragments unless brevity is requested"
    "- **Explain, refactor, debug, and expand code with expertise** in both frontend and backend domains"
    "- **If the user asks for styling, design, layout — write beautiful and practical UI code**"

    "Stay concise, but never cut corners in technical quality. Prioritize clarity, completeness, and actionable advice."
)

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

# ---------- Endpoints ---------

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("prompt", "")
    image_base64 = data.get("image_base64")
    file_content = data.get("file_context")

    vision_input = VisionInput(image_base64=image_base64, prompt=user_message if user_message else "Describe this image.")

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if image_base64:
        vision_result = vision_analyze(vision_input)
        messages.append(HumanMessage(content=f"{user_message if user_message else 'Describe this image.'}"))
        messages.append(HumanMessage(content=f"Image Analysis: {vision_result}"))
        if file_content:
            messages.append(HumanMessage(content=f"Code Context:\n{file_content}"))
    else:
        messages.append(HumanMessage(content=user_message if user_message else ""))
        if file_content:
            messages.append(HumanMessage(content=f"Code Context:\n{file_content}"))


    try:
        result = chat_graph.invoke({"messages": messages}, config={"configurable": {"thread_id": "1"}})
        last_message = result["messages"][-1]
        reply = getattr(last_message, "content", str(last_message))
        return {"reply": reply}
    except Exception as e:
        print("LangGraph Error:", e)
        return {"reply": f"Error processing request: {e}"}
