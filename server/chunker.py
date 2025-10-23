"""
chunker.py
------------
Utility functions for semantic, token-aware text chunking (Flan-T5 compatible).
"""

import spacy
from transformers import AutoTokenizer

# Load models once at import
_nlp = spacy.load("en_core_web_sm")
_nlp.max_length = 2_000_000

# Use Flan-T5 tokenizer (small/medium/large, depending on your model)
_tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")

def _token_len(text: str) -> int:
    """Return number of tokens for given text using T5 tokenizer."""
    return len(_tokenizer.encode(text, add_special_tokens=False))

def semantic_token_chunker(
    text: str,
    max_tokens: int = 512,
    overlap_sentences: int = 2
) -> list[str]:
    """
    Split text into semantically meaningful chunks (sentence-aware, token-aware).

    Args:
        text (str): Full text to chunk.
        max_tokens (int): Maximum tokens per chunk (Flan-T5 tokens).
        overlap_sentences (int): Number of sentences to overlap between chunks.

    Returns:
        list[str]: List of chunk strings.
    """
    # Sentence segmentation
    sents = [sent.text.strip() for sent in _nlp(text).sents if sent.text.strip()]
    chunks = []
    cur_chunk = []
    cur_tokens = 0

    for sent in sents:
        tlen = _token_len(sent)

        # If sentence longer than max_tokens, hard-split into sub-sentences
        if tlen > max_tokens:
            parts = [p.strip() for p in sent.split(",") if p.strip()]
            for p in parts:
                pt = _token_len(p)
                if cur_tokens + pt > max_tokens and cur_chunk:
                    chunks.append(" ".join(cur_chunk))
                    cur_chunk = []
                    cur_tokens = 0
                cur_chunk.append(p)
                cur_tokens += pt
        else:
            if cur_tokens + tlen <= max_tokens:
                cur_chunk.append(sent)
                cur_tokens += tlen
            else:
                # Save current chunk
                chunks.append(" ".join(cur_chunk))

                # Add overlap: last N sentences
                overlap = cur_chunk[-overlap_sentences:] if overlap_sentences > 0 else []
                cur_chunk = overlap + [sent]
                cur_tokens = sum(_token_len(s) for s in cur_chunk)

    if cur_chunk:
        chunks.append(" ".join(cur_chunk))

    return chunks
