import requests
import json
from fastapi import FastAPI, HTTPException

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "deepseek/deepseek-chat-v3.1:free"

def call_openrouter(query: str, context: str = "") -> str:
    """
    Calls the OpenRouter DeepSeek model with a query and optional context.
    Returns the model's reply as plain text.
    """
    try:
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "You are a helpful AI assistant. Answer user queries clearly and concisely."},
                {"role": "user", "content": f"Query: {query}\n\nContext: {context}"}
            ]
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling OpenRouter API: {str(e)}")
