from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
from tqdm import tqdm
from chromadb import PersistentClient
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
    files: List[FileData]                    # for full upload OR changed files for incremental
    incremental: Optional[bool] = False      # False = full rebuild, True = upsert changed files
    deleted: Optional[List[str]] = []        # list of file paths to delete from the collection

class SemanticSearchRequest(BaseModel):
    machineId: str
    projectName: str
    query: str

# ---------- Embedding Setup ----------
embedding_function = OpenAIEmbeddingFunction(api_key=os.environ["OPENAI_API_KEY"])

# ---------- Classic 500/150 splitter in 20-line windows ----------
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=150,
)

def classic_500_chunks(content: str):
    content = content or ""
    lines = content.splitlines()
    for i in range(0, len(lines), 20):
        block = "\n".join(lines[i:i + 20])
        docs = SPLITTER.split_text(block)
        for doc in docs:
            yield doc, (i + 1)

# ---------- Upload Folder (full or incremental) ----------
@router.post("/upload-folder")
async def upload_folder(payload: UploadFolderRequest):
    try:
        machine_id   = payload.machineId
        project_name = payload.projectName
        files        = payload.files or []
        deleted      = payload.deleted or []
        incremental  = bool(payload.incremental)

        user_path = f"./chroma_db/{machine_id}"
        coll_name = f"{machine_id}-{project_name}"

        client = PersistentClient(path=user_path)

        if not incremental:
            # -------- FULL REBUILD --------
            try:
                client.delete_collection(name=coll_name)
            except Exception:
                pass

            collection = client.create_collection(
                name=coll_name,
                embedding_function=embedding_function
            )

            documents, metadatas, ids = [], [], []

            for f in files:
                for ch, line_start in classic_500_chunks(f.content):
                    documents.append(ch)
                    metadatas.append({
                        "file_path":  f.path,
                        "line_start": line_start,
                    })
                    ids.append(str(uuid.uuid4()))

            for i in tqdm(range(0, len(documents), BATCH_SIZE)):
                collection.add(
                    documents=documents[i:i + BATCH_SIZE],
                    metadatas=metadatas[i:i + BATCH_SIZE],
                    ids=ids[i:i + BATCH_SIZE]
                )

            return {"status": "uploaded_full", "chunks": len(documents)}

        # -------- INCREMENTAL UPSERT --------
        # Ensure collection exists
        try:
            collection = client.get_collection(coll_name, embedding_function=embedding_function)
        except Exception:
            collection = client.create_collection(coll_name, embedding_function=embedding_function)

        # 1) Delete removed files entirely
        for rel_path in deleted:
            collection.delete(where={"file_path": rel_path})

        # 2) For each changed/new file: delete old chunks for that path, then add new chunks
        total_added = 0
        for f in files:
            # remove old chunks for this file
            collection.delete(where={"file_path": f.path})

            documents, metadatas, ids = [], [], []
            for ch, line_start in classic_500_chunks(f.content):
                documents.append(ch)
                metadatas.append({
                    "file_path":  f.path,
                    "line_start": line_start,
                })
                ids.append(str(uuid.uuid4()))

            for i in range(0, len(documents), BATCH_SIZE):
                collection.add(
                    documents=documents[i:i + BATCH_SIZE],
                    metadatas=metadatas[i:i + BATCH_SIZE],
                    ids=ids[i:i + BATCH_SIZE]
                )
            total_added += len(documents)

        return {
            "status": "uploaded_incremental",
            "changed_files": len(files),
            "deleted_files": len(deleted),
            "chunks_added": total_added
        }

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
        user_path = f"./chroma_db/{machine_id}"

        client = PersistentClient(path=user_path)

        collection = client.get_collection(f"{machine_id}-{project_name}", embedding_function=embedding_function)

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