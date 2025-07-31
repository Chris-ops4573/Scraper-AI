# 🧠 Scraper.AI – Semantic Codebase Explorer & AI Assistant

Scraper.AI is an intelligent VS Code extension + backend API that helps developers **understand large unfamiliar codebases** by enabling:

- 🔍 **Semantic Search**: Ask a natural language question like “Where is the model initialized?” and instantly jump to the most relevant line in your project.
- 🤖 **Custom Code Assistant**: Automatically scrapes Brave Search and GitHub to provide contextual answers and code snippets.

Check out the extention [here](https://marketplace.visualstudio.com/items?itemName=Christine-devops1234.scraper) or install it directly in vs Code extensions and start using. 
If you wish to run it locally check out the [How to use](https://github.com/Chris-ops4573/Scraper-AI/blob/main/README.md#%EF%B8%8F-how-to-use) section. 

---

## ✨ Features

- **Semantic Search through uploaded projects**
- **Chunking & Embedding via OpenAI** to store source code in a vector database
- **Persistent project storage** using ChromaDB
- **VS Code Extension UI** to upload and query projects
- **Scraper-based AI Assistant** to fetch relevant answers from the web and public github repos

---

## 🛠️ Tech Stack

- **Frontend**: VS Code Extension
- **Backend**: FastAPI (Python)
- **Vector DB**: ChromaDB
- **Embeddings**: OpenAI
- **Web Scraping**: Brave Search, GitHub
- **AI Logic**: OpenAI LLMs

---

## ⚙️ How to Use

### 1. Backend Setup

#### Clone the Repository
- git clone https://github.com/Chris-ops4573/jarvis-VR.git
- cd scraper-ai

#### Install Requirements
- pip install -r requirements.txt

#### Run the Backend
- uvicorn main:app --reload

#### Make sure your .env contains your OpenAI API key like this:
- OPENAI_API_KEY=your_key_here

Or simply setup the Dockerfile after cloning the repo through these commands:

- docker build -t scraper-ai:v1.0.0 Dockerfile .
- docker run -p 8080:8080 scraper-ai:v1.0.0

Note: You still have to setup your API keys to run the backend locally using a .env file. 

### 2. Frontend Setup

- Go to the extension.js file and click 'Fn + F5':
This will open the vs code extension in vs codes exntension development host

---

## 📦 How to Use
### 🗂️ 1. Upload Your Project
- Press Ctrl + Shift + P (or Cmd + Shift + P on Mac) to open the Command Palette.
- Search for and select: Upload Project to Agent.
- The current folder you are working on will be sentenabing you to perform semantic queries.
- This step sets up your project in a ChromaDB database for fast semantic retrieval.

### 🔎 2. Perform a Semantic Search
- Again open the Command Palette (Ctrl + Shift + P).
- Select: Semantic File Search.
- Enter your natural-language query (e.g., “Where is the JWT token generated?”).
- The extension will:
- Query your indexed project using semantic embeddings.
- Return the top 3 most relevant code snippets.
- Display them as clickable options.
- Click on any option, and VS Code will jump directly to the exact file and line in your project.

---

## 💡 Behind the Scenes
- Uses chromadb with a custom embedding function (OpenAI or other) to store vectorized document chunks.
- Upon upload, your entire project is split into manageable chunks and indexed with their file paths and line ranges.
- Semantic queries are matched against this database for precise and intelligent navigation.
- The coding assistant is a custom AI agent integrated with Brave Search and GitHub scraping capabilities, meaning it adapts to your query in real time and doesn't rely solely on pre-trained data.
