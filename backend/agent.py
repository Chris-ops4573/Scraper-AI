from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from langchain.tools import tool
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from database.userDatabase import router as user_router
import os
import requests
from dotenv import load_dotenv
import openai
import uuid
from datetime import datetime

# Load environment variables
load_dotenv()

# Get API keys from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Initialize OpenAI client (v1 SDK)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize FastAPI app
app = FastAPI()
app.include_router(user_router)

# CORS middleware (allow frontend to access backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LangChain Tools ---

langchain_llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model="gpt-4o"
)

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city using OpenWeatherMap."""
    api_key = OPENWEATHER_API_KEY
    if not api_key:
        return "Weather API key not set."
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    resp = requests.get(url)
    if resp.status_code != 200:
        return "Weather data not found."
    data = resp.json()
    desc = data['weather'][0]['description']
    temp = data['main']['temp']
    return f"Weather in {city}: {desc}, {temp}°C"

@tool
def brave_search(query: str) -> str:
    """Search the web using Brave Search API."""
    api_key = BRAVE_API_KEY
    if not api_key:
        return "Brave API key not set."
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": api_key}
    params = {"q": query, "count": 3}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        return "No search results."
    data = resp.json()
    results = data.get("web", {}).get("results", [])
    if not results:
        return "No search results."
    return "\n".join([f"{r['title']}: {r['url']}" for r in results])

@tool
def get_current_date() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

tools = [get_weather, brave_search, get_current_date]
agent = initialize_agent(
    tools,
    langchain_llm,
    agent=AgentType.OPENAI_FUNCTIONS,  # or STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION
    verbose=True,
)

# --- Endpoints ---

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    try:
        reply = agent.run(user_message)
        return {"reply": reply}
    except Exception as e:
        print("LangChain Agent Error:", e)
        return {"reply": f"Error processing request: {e}"}

@app.post("/chat-voice")
async def chat_voice(audio: UploadFile = File(...)):
    try:
        # Read uploaded file into memory first
        contents = await audio.read()

        # Generate a unique filename
        safe_filename = f"temp_{uuid.uuid4()}.m4a"

        # Save to disk
        with open(safe_filename, "wb") as f:
            f.write(contents)  # Now fully written and file closed

        # Now open for Whisper reading
        with open(safe_filename, "rb") as file_for_whisper:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=file_for_whisper
            )

        transcribed_text = transcription.text
        print("Transcription:", transcribed_text) 

        # Delete temp file after transcription
        os.remove(safe_filename)

        # Use LangChain agent for the transcribed text
        reply = agent.run(transcribed_text)
        return {"reply": reply, "transcription": transcribed_text}

    except Exception as e:
        print("Voice Chat Error:", e)
        return {"reply": f"Error processing voice request: {e}"}

