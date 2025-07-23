from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import os
import shutil
from tqdm import tqdm
from chromadb import PersistentClient
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from langchain.text_splitter import RecursiveCharacterTextSplitter

router = APIRouter()

BATCH_SIZE = 100

# ---------- Models ----------
class FileData(BaseModel):
    path: str
    content: str

class UploadFolderRequest(BaseModel):
    machineId: str
    projectName: str
    files: List[FileData]

class SemanticSearchRequest(BaseModel):
    machineId: str
    projectName: str
    query: str

# ---------- Embedding Setup ----------
embedding_function = OpenAIEmbeddingFunction(api_key=os.environ["OPENAI_API_KEY"])

# ---------- Upload Folder ----------
@router.post("/upload-folder")
async def upload_folder(payload: UploadFolderRequest):
    try:
        machine_id = payload.machineId
        files = payload.files
        project_name = payload.projectName
        user_path = f"./chroma_db_{machine_id}_{project_name}"

        client = PersistentClient(path=user_path)

        # Step 2: Create or get collection
        try:
            client.delete_collection(name=f"{machine_id}_{project_name}")
        except:
            pass

        collection = client.create_collection(name=f"{machine_id}_{project_name}", embedding_function=embedding_function)

        # Step 3: Split and prepare docs
        documents = []
        metadatas = []
        ids = []

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=150)

        uid = 0
        for file in files:
            lines = file.content.splitlines()
            for i in range(0, len(lines), 20):
                chunk = "\n".join(lines[i:i + 20])
                docs = splitter.split_text(chunk)
                for doc in docs:
                    documents.append(doc)
                    metadatas.append({"file_path": file.path, "line_start": i + 1})
                    ids.append(f"{machine_id}-{uid}")
                    uid += 1

        # Step 4: Batch add to Chroma
        for i in tqdm(range(0, len(documents), BATCH_SIZE)):
            batch_docs = documents[i:i + BATCH_SIZE]
            batch_ids = ids[i:i + BATCH_SIZE]
            batch_metadatas = metadatas[i:i + BATCH_SIZE]

            collection.add(documents=batch_docs, ids=batch_ids, metadatas=batch_metadatas)

        return {"status": "uploaded", "chunks": len(documents)}

    except Exception as e:
        print("Error in upload_folder:", e)
        return {"error": str(e)}

# ---------- Semantic Search ----------
@router.post("/semantic-search")
async def semantic_search(payload: SemanticSearchRequest):
    try:
        machine_id = payload.machineId
        query = payload.query
        project_name = payload.projectName
        user_path = f"./chroma_db_{machine_id}_{project_name}"

        client = PersistentClient(path=user_path)

        collection = client.get_collection(f"{machine_id}_{project_name}", embedding_function=embedding_function)

        results = collection.query(query_texts=[query], n_results=3)

        if results["documents"] and len(results["documents"][0]) > 0:
            top_matches = []
            for i in range(len(results["documents"][0])):
                metadata = results["metadatas"][0][i]
                top_matches.append({
                    "file_path": metadata["file_path"],
                    "line_number": metadata["line_start"]
                })

            return {"matches": top_matches}
        else:
            return {"error": "No match found"}
    except Exception as e:
        error_message = str(e)
        if "does not exist" in error_message and "Collection" in error_message:
            return {"error": "This project hasn't been uploaded yet. Please upload the folder first."}
        else:
            print("Error in semantic_search:", e)
            return {"error": "An unexpected error occurred. Please try again."}

