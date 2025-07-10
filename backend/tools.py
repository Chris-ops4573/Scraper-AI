from langchain.tools import tool
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

class VisionInput(BaseModel):
    image_base64: Optional[str] = None
    prompt: str 

@tool
def get_weather(city: str) -> str:
    """ Get current weather for a city using OpenWeather API""" 
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
    """Search the web for useful results using Brave Search API and return structured summaries."""
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
    # Return structured summaries
    structured = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "description": r.get("description") or r.get("snippet") or ""
        }
        for r in results
    ]
    print("brave")
    return json.dumps(structured, ensure_ascii=False, indent=2)

@tool
def get_current_date() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d") 

@tool
def github_code_search(query: str) -> str:
    """
    Search GitHub for code snippets matching a query and return structured usable codeblocks the user can use directly.
    """
    if not GITHUB_TOKEN:
        return "GitHub token not set. Set GITHUB_TOKEN in your environment."

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    url = f"https://api.github.com/search/code?q={query}&per_page=3"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return f"GitHub search failed: {response.status_code} - {response.text}"

    items = response.json().get("items", [])
    if not items:
        return "No code snippets found."

    result_blocks = []
    for item in items:
        file_name = item['name']
        repo_name = item['repository']['full_name']
        file_path = item['path']
        file_url = item.get("html_url")
        raw_url = file_url.replace("github.com", "raw.githubusercontent.com").replace("/blob", "")

        # Fetch actual raw code content
        try:
            code_response = requests.get(raw_url)
            if code_response.status_code != 200:
                code_content = f"[Error fetching code: {code_response.status_code}]"
            else:
                code_content = code_response.text
        except Exception as e:
            code_content = f"[Exception fetching code: {str(e)}]"

        block = (
            f"File: {file_name}\n"
            f"Repo: {repo_name}\n"
            f"Path: {file_path}\n"
            f"URL: {raw_url}\n\n"
            f"--- CODE START ---\n"
            f"{code_content[:1500]}...\n"  # limit to 1500 characters for LLM usability
            f"--- CODE END ---\n"
        )

        result_blocks.append(block)
    print("github")

    return "\n\n".join(result_blocks)

@tool
def fetch_github_repo_code_summary(repo_url: str) -> dict:
    """
    Given a public GitHub repo URL, fetch key source code and metadata (README, main files, configs).
    Returns structured dict for LLM to analyze and explain what the repo does.
    """
    import requests
    import base64

    if "github.com" not in repo_url:
        return {"error": "Invalid GitHub URL."}

    try:
        owner, repo = repo_url.strip("/").split("/")[-2:]
    except Exception:
        return {"error": "Could not parse owner/repo from URL."}

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    key_files = ["README.md", "main.py", "index.js", "app.py", "package.json", "requirements.txt"]
    output = {"repo": f"{owner}/{repo}", "files": []}

    for file in key_files:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file}"
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            try:
                data = r.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                output["files"].append({
                    "filename": file,
                    "content": content[:4000]  # Optional: LLM-token-friendly limit
                })
            except Exception as e:
                output["files"].append({
                    "filename": file,
                    "error": f"Decoding error: {str(e)}"
                })
        else:
            output["files"].append({
                "filename": file,
                "error": "File not found or inaccessible."
            })
    
    print("summary")
    return output

def vision_analyze(data: VisionInput) -> str:

    client = OpenAI(api_key=OPENAI_API_KEY)
    image_base64 = data.image_base64
    prompt = data.prompt

    if not image_base64.startswith("data:image"):
        raise ValueError("Invalid image base64 data.")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_base64}}
                ],
            }
        ],
        max_tokens=1000
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content
