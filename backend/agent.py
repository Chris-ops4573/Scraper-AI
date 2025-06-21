from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import requests
from dotenv import load_dotenv
import openai
import uuid

# Load environment variables
load_dotenv()

# Get API keys from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

# Initialize OpenAI client (v1 SDK)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize FastAPI app
app = FastAPI()

# CORS middleware (allow frontend to access backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Brave Search function
def search_brave(query):
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": BRAVE_API_KEY}
    params = {"q": query, "count": 5}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get("web", {}).get("results"):
            return "No web search results found."

        results = []
        for i, item in enumerate(data["web"]["results"], 1):
            results.append(f"{i}. {item['title']}\n{item['url']}\n{item['description']}")

        return "\n\n".join(results)

    except Exception as e:
        print("Brave API Error:", e)
        return "No web search results found."

# Text chat endpoint
@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")

    web_results = search_brave(user_message)

    system_prompt = (
        f"You are a helpful VR Assistant for daily tasks. "
        f"I have fetched these web search results for you:\n\n{web_results}\n\n"
        "Use these results if they are helpful, otherwise answer using your general knowledge."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )

        reply = response.choices[0].message.content
        return {"reply": reply}

    except Exception as e:
        print("OpenAI API Error:", e)
        return {"reply": f"Error processing request: {e}"}

# Voice chat endpoint (Windows-safe version)
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

        # Continue with Brave search and GPT
        web_results = search_brave(transcribed_text)

        system_prompt = (
            f"You are a helpful VR Assistant for daily tasks. "
            f"I have fetched these web search results for you:\n\n{web_results}\n\n"
            "Use these results if they are helpful, otherwise answer using your general knowledge."
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcribed_text}
            ]
        )

        reply = response.choices[0].message.content
        return {"reply": reply}

    except Exception as e:
        print("Voice Chat Error:", e)
        return {"reply": f"Error processing voice request: {e}"}

