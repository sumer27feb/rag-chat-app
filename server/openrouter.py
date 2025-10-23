import httpx
from fastapi import HTTPException
from loguru import logger  # Assuming logger is imported globally

# Configuration (These can remain the same)
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "deepseek/deepseek-chat-v3.1:free"


# It's best practice to create an async client session once (e.g., at app startup)
# but for a simple function, we can create it within a context manager.

async def call_openrouter(query: str, context: str = "") -> str:
    """
    Calls the OpenRouter DeepSeek model asynchronously using httpx.
    Returns the model's reply as plain text.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system",
             "content": "You are a helpful AI assistant. Extract the exact answer from the context. Do not include extra text."},
            # Integrating the RAG prompt from your router function for completeness
            {"role": "user", "content": f"Context:\n{context}\n\nQuery: {query}"}
        ]
    }

    try:
        # Use an asynchronous HTTP client
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload  # httpx handles JSON serialization with 'json' argument
            )
            response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter API returned HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=502, detail=f"LLM API error: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting OpenRouter: {e}")
        raise HTTPException(status_code=503, detail="Could not connect to LLM API.")
    except Exception as e:
        logger.error(f"Unexpected error in LLM call: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during the LLM call.")