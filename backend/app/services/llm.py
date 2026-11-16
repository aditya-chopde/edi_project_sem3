import json
import os
from dataclasses import dataclass

from google import genai
from google.genai import types

from app import config


SYSTEM_PROMPT = """You are an Indian historical information assistant. Answer using only the provided
historical evidence. Answer in the user's selected language. Do not invent facts, dates
or events. If the context is insufficient, say the answer cannot be verified. Cite
supporting evidence using the chunk_db_id values. Preserve historical names. If sources
disagree, explain the disagreement. Return STRICT JSON:
{answer, citations:[{chunk_db_id, claim}]}"""


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    cited_chunk_ids: list[int]


def generate_answer(question: str, language: str, context: str) -> GeneratedAnswer:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=(
            f"Selected answer language: {language}\n"
            f"Question: {question}\n\n"
            f"Historical evidence:\n{context}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    try:
        result = json.loads(response.text)
        answer = result["answer"]
        citations = result["citations"]
        if not isinstance(answer, str) or not isinstance(citations, list):
            raise ValueError("Unexpected response fields")
        cited_ids = [
            citation["chunk_db_id"]
            for citation in citations
            if isinstance(citation, dict)
            and type(citation.get("chunk_db_id")) is int
        ]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Gemini returned invalid answer JSON") from error
    return GeneratedAnswer(answer=answer, cited_chunk_ids=cited_ids)
