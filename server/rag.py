# app/routers/rag.py
import torch
from fastapi import APIRouter, Request, HTTPException, Body, Depends
from typing import List, Any, Tuple
from bson import ObjectId
import fitz  # PyMuPDF
import asyncio
import io
import asyncio
from asyncio import to_thread

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
import chromadb
from pydantic import BaseModel
from fastapi_limiter.depends import RateLimiter

from chunker import semantic_token_chunker
from openrouter import call_openrouter

router = APIRouter(prefix="/rag", tags=["RAG"])

# --------------------------
# Request models
# --------------------------
class AskRequest(BaseModel):
    query: str
    user_id: str
    chat_id: str
    top_k: int = 3

# --------------------------

device = 0 if torch.cuda.is_available() else -1

# --------------------------
# Local embedder (BAAI bge-small-en)
# --------------------------
from langchain_huggingface import HuggingFaceEmbeddings


def get_bge_small_embedder(device: str | None = None) -> HuggingFaceEmbeddings:
    """
    Return a HuggingFaceEmbeddings instance for BAAI/bge-small-en.
    device: "cuda" or "cpu" or None to auto-detect.
    """
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    embedder = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en",
        model_kwargs={"device": device}
    )
    return embedder


# --------------------------
# Helpers: PDF read & split
# --------------------------
async def read_pdf_from_gridfs(file_id: str, fs: AsyncIOMotorGridFSBucket) -> str:
    try:
        file_id_obj = ObjectId(file_id)
        download_stream = await fs.open_download_stream(file_id_obj)
        pdf_bytes = await download_stream.read()
        try:
            await download_stream.close()
        except Exception:
            try:
                download_stream.close()
            except Exception:
                pass
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")

    text = ""
    with fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text("text") + "\n"

    return text.strip()

async def process_chat_pdf_helper(chat_id: str, request: Request) -> dict:
    chat = await request.app.state.db["chats"].find_one({"chat_id": chat_id})
    if not chat or not chat.get("pdf_file_id"):
        raise HTTPException(status_code=404, detail="Chat or PDF not found")

    fs = request.app.state.fs
    text = await read_pdf_from_gridfs(chat["pdf_file_id"], fs)
    chunks = semantic_token_chunker(text, max_tokens=500)

    return {
        "chat_id": chat_id,
        "chunks": chunks,
        "num_chunks": len(chunks),
        "first_chunk_preview": chunks[0][:200] if chunks else ""
    }


# --------------------------
# Embedding helper (runs sync embed calls in executor)
# --------------------------
async def embed_chat_helper(chat_id: str, request: Request) -> Tuple[List[List[float]], List[str]]:
    result = await process_chat_pdf_helper(chat_id, request)
    chunks: List[str] = result["chunks"]

    if not chunks:
        return [], []

    embedder = get_bge_small_embedder()
    loop = asyncio.get_event_loop()
    embeddings: List[List[float]] = await loop.run_in_executor(None, embedder.embed_documents, chunks)

    return embeddings, chunks


# --------------------------
# Chroma client & storage helper
# --------------------------
chroma_client = chromadb.PersistentClient(path="./chroma_store")


def store_embeddings_in_chroma(
    chat_id: str,
    chunks: List[str],
    embeddings: List[List[float]],
    collection_name: str = "chat_embeddings"
) -> dict:
    if not chunks or not embeddings or len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings must be same non-empty length")

    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    ids = [f"{chat_id}_{i}" for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"chat_id": chat_id, "chunk_index": i} for i in range(len(chunks))]
    )

    try:
        chroma_client.persist()
    except Exception:
        pass

    return {
        "chat_id": chat_id,
        "num_chunks_stored": len(chunks),
        "collection_name": collection_name
    }



# --------------------------
# Endpoints
# --------------------------
@router.post("/process-chat-pdf/{chat_id}")
async def process_chat_pdf(chat_id: str, request: Request):
    result = await process_chat_pdf_helper(chat_id, request)
    return result


@router.post("/embed-chat/{chat_id}")
async def embed_chat(chat_id: str, request: Request):
    embeddings, chunks = await embed_chat_helper(chat_id, request)
    if not embeddings:
        raise HTTPException(status_code=404, detail="No chunks found for this chat.")
    store_info = store_embeddings_in_chroma(chat_id, chunks, embeddings)
    return store_info


@router.post("/ask", dependencies=[Depends(RateLimiter(times=10, seconds=30))])
async def rag_ask(payload: AskRequest = Body(...)):
    query = payload.query
    chat_id = payload.chat_id
    top_k = payload.top_k
    user_id= payload.user_id

    collection = chroma_client.get_or_create_collection("chat_embeddings")

    embedder = get_bge_small_embedder()
    query_embedding = await to_thread(embedder.embed_query, query)


    results = await to_thread(
        collection.query,
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"chat_id": chat_id},
        include=["documents", "metadatas", "distances"]
    )

    docs = results.get("documents", [[]])[0]
    dists = results.get("distances", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return {"chat_id": chat_id, "query": query, "answer": "No relevant context found for this chat."}

    context = "\n\n".join(docs)

    # --- prepare prompt ---
    prompt = f"""
    Extract the exact answer from the context. Do not include extra text.

    Context:
    {context}
    """

    answer = await call_openrouter(query, context)

    problem_token = "<｜begin▁of▁sentence｜>"
    cleaned_answer = answer.replace(problem_token, "").strip()

    return {"answer": cleaned_answer}


@router.get("/test")
async def test_rag():
    return {"message": "RAG router is working!"}
