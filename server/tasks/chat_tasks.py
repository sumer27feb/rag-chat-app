from celery import shared_task
import asyncio
from rag_helpers import embed_chat_helper, store_embeddings_in_chroma
from loguru import logger

# Persistent global event loop (Celery-safe)
loop = None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=1)
def embed_chat_task(self, chat_id: str):
    global loop
    try:
        # ✅ Create loop only once, reuse for all retries
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        logger.info(f"🚀 Starting embedding for chat_id={chat_id}")
        embeddings, chunks = loop.run_until_complete(embed_chat_helper(chat_id))

        if not embeddings:
            raise ValueError("No chunks found for this chat")

        logger.success(f"✅ Embedding successful | chat_id={chat_id} | chunks={len(chunks)}")
        return {"chat_id": chat_id, "chunks": len(chunks)}

    except Exception as e:
        logger.error(f"❌ Embedding failed for chat_id={chat_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=10)
