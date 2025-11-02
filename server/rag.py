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
from motor.motor_asyncio import AsyncIOMotorGridFSBucket, AsyncIOMotorCollection
import chromadb
from pydantic import BaseModel
from fastapi_limiter.depends import RateLimiter

from chunker import semantic_token_chunker
from openrouter import call_openrouter
from utils import col_messages, success_response
from tasks.chat_tasks import embed_chat_task

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

def get_bge_small_embedder(device: str | None = None):
    from langchain_huggingface import HuggingFaceEmbeddings  # moved inside
    import torch
    """
    Return a HuggingFaceEmbeddings instance for BAAI/bge-small-en.
    device: "cuda" or "cpu" or None to auto-detect.
    """


    device = "cuda" if torch.cuda.is_available() else "cpu"
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en",
        model_kwargs={"device": device}
    )

def estimate_tokens(text: str) -> int:
    """A simple token estimation placeholder (replace with tiktoken or similar)."""
    return len(text.split()) // 2

MAX_CONTEXT_TOKENS = 4096


# --------------------------
# Helpers: PDF read & split
# --------------------------
def get_messages_collection(request: Request) -> AsyncIOMotorCollection:
    # We call your utility function here
    return col_messages(request)

async def retrieve_chat_history(
        messages_col: AsyncIOMotorCollection,
        chat_id: str,
        max_turns: int
) -> list[dict]:
    """Retrieves the most recent messages in a single, efficient query."""

    # max_turns * 2 ensures we get both user and bot messages for N turns
    limit = max_turns * 2

    history_cursor = messages_col.find(
        {"chat_id": chat_id}
    ).sort(
        # We want the newest messages, so sort by timestamp descending (-1)
        # Then we reverse the list in Python to process oldest-first
        "timestamp", -1
    ).limit(limit)

    # Execute the query and get the list
    history = await history_cursor.to_list(length=limit)

    # Reverse the list so the oldest messages are at the start (for easy truncation)
    return history[::-1]

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
chroma_client = chromadb.HttpClient(host="rag_chromadb", port=8000)


def store_embeddings_in_chroma(
    chat_id: str,
    chunks: List[str],
    embeddings: List[List[float]],
    collection_name: str = "chat_embeddings"
) -> dict:
    logger.debug(f"🧠 S  tarting to store embeddings for chat_id={chat_id}, "
                 f"collection={collection_name}, num_chunks={len(chunks)}")

    if not chunks or not embeddings or len(chunks) != len(embeddings):
        logger.error("❌ Invalid input: chunks and embeddings must be same non-empty length")
        raise ValueError("Chunks and embeddings must be same non-empty length")

    try:
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.debug(f"✅ Collection ready: {collection_name}")

        ids = [f"{chat_id}_{i}" for i in range(len(chunks))]
        logger.debug(f"🆔 Generated IDs: {ids[:5]}{'...' if len(ids) > 5 else ''}")

        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"chat_id": chat_id, "chunk_index": i} for i in range(len(chunks))]
        )
        logger.debug(f"📦 Added {len(chunks)} embeddings to collection {collection_name}")

        chroma_client.persist()
        logger.debug("💾 Chroma client persisted successfully.")

        result = {
            "chat_id": chat_id,
            "num_chunks_stored": len(chunks),
            "collection_name": collection_name
        }
        logger.debug(f"✅ Store result: {result}")
        return result

    except Exception as e:
        logger.exception(f"🔥 Error while storing embeddings in Chroma: {e}")
        raise



# --------------------------
# Endpoints
# --------------------------
@router.post("/process-chat-pdf/{chat_id}")
async def process_chat_pdf(chat_id: str, request: Request):
    result = await process_chat_pdf_helper(chat_id, request)
    return result


@router.post("/embed-chat/{chat_id}")
async def embed_chat(chat_id: str, request: Request):
    # embeddings, chunks = await embed_chat_helper(chat_id, request)
    # if not embeddings:
    #     raise HTTPException(status_code=404, detail="No chunks found for this chat.")
    # store_info = store_embeddings_in_chroma(chat_id, chunks, embeddings)
    # return store_info
    embed_chat_task.delay(chat_id)
    return success_response({"message": "Embedding task queued", "chat_id": chat_id})


@router.post("/ask", dependencies=[Depends(RateLimiter(times=10, seconds=30))])
async def rag_ask(
    payload: AskRequest = Body(...),
    messages_col: AsyncIOMotorCollection = Depends(get_messages_collection)
):
    query = payload.query
    chat_id = payload.chat_id
    top_k = payload.top_k
    user_id = payload.user_id

    logger.debug(f"📩 Received query: '{query}' | chat_id={chat_id}, user_id={user_id}, top_k={top_k}")

    collection = chroma_client.get_or_create_collection("chat_embeddings")

    embedder = get_bge_small_embedder()
    query_embedding = await to_thread(embedder.embed_query, query)
    logger.debug(f"🔹 Query embedding generated. Vector length = {len(query_embedding)}")

    # Fetch chat history
    history_messages = await retrieve_chat_history(messages_col, chat_id, max_turns=5)
    logger.debug(f"🕓 Retrieved {len(history_messages)} messages from chat history.")

    formatted_history = []
    for msg in history_messages:
        role = msg.get("role", "Bot").capitalize()
        content = msg.get("content", "")
        formatted_history.append(f"{role}: {content}")

    # Query the vector DB
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

    logger.debug(f"📚 Retrieved {len(docs)} docs from Chroma. Distances: {dists}")
    if not docs and not formatted_history:
        logger.warning("⚠️ No RAG docs and no chat history found.")
        return {"chat_id": chat_id, "query": query, "answer": "No relevant context found for this chat."}

    context = "\n\n".join(docs)
    logger.debug(f"🧩 Context preview (first 300 chars): {context[:300]}...")

    base_prompt_template = f"""
    # ROLE
    You are a specialist assistant answering questions based *only* on the provided context.
    
    # INSTRUCTIONS
    1.  Read the 'RAG Context' and the 'Current User Query'.
    2.  Use the 'Conversation History' to understand the user's question, especially if it's a follow-up.
    3.  Formulate an answer that directly responds to the 'Current User Query'.
    4.  **IMPORTANT:** Base your answer **strictly** on the information found in the 'RAG Context'.
    5.  If the answer is not in the context, state that you cannot find the information in the provided document.
    6.  Do not use any external knowledge.
    
    # RAG CONTEXT (Document Snippets)
    ---
    {context}
    ---
    
    # CONVERSATION HISTORY
    ---
    {{history_placeholder}}
    ---
    
    # CURRENT USER QUERY
    User: {query}
    
    # ANSWER
    Assistant:
    """

    history_list = formatted_history[:]
    final_history_string = "\n".join(history_list)

    # Truncation Loop
    while True:
        current_prompt = base_prompt_template.replace("{history_placeholder}", final_history_string)
        total_tokens = estimate_tokens(current_prompt)

        if total_tokens <= MAX_CONTEXT_TOKENS - 100:
            logger.debug(f"✅ Context size OK: {total_tokens} tokens.")
            break

        if len(history_list) >= 2:
            history_list.pop(0)
            history_list.pop(0)
            final_history_string = "\n".join(history_list)
            logger.warning(f"✂️ Truncated 2 messages. Remaining history: {len(history_list)} turns.")
        else:
            final_history_string = ""
            logger.warning("🚫 History fully truncated to fit context window.")
            break

    final_prompt = base_prompt_template.replace("{history_placeholder}", final_history_string)
    logger.info(f"🧠 Final prompt sent to LLM:\n{'-'*60}\n{final_prompt[:800]}...\n{'-'*60}")

    answer = await call_openrouter(final_prompt, context)

    problem_token = "<｜begin▁of▁sentence｜>"
    cleaned_answer = answer.replace(problem_token, "").strip()

    logger.debug(f"💬 Model response (first 200 chars): {cleaned_answer[:200]}...")
    return {"answer": cleaned_answer}


@router.get("/test")
async def test_rag():
    return {"message": "RAG router is working!"}
