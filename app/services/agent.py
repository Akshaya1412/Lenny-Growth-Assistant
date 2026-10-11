from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from app.config import settings
from app.services.artifact import generate_artifact
from app.services.llm import generate_llm_response
from app.services.retrieval import build_context_for_prompt, retrieve_documents


def run_claude_agent(question: str, context: str, system_prompt: Optional[str] = None) -> Union[str, tuple[str, bool]]:
    normalized_prompt = system_prompt or (
        "You are the Lenny Growth Assistant. Answer using only the transcript excerpts provided in the context. "
        "If the material does not support the claim, state that clearly. Cite the relevant source by name using the format 'Source: <filename>' "
        "at the end of the relevant sentence or in a short citations list. Keep answers concise but substantive."
    )
    conversation = [{"role": "user", "content": f"Question: {question}\n\nTranscript context:\n{context}"}]
    return generate_llm_response(conversation, normalized_prompt, provider="claude_agent_sdk")


def answer_question(question: str, recent_messages: Optional[List[Dict[str, str]]] = None, provider: Optional[str] = None) -> Dict[str, Any]:
    selected_provider = provider or settings.model_provider
    docs = retrieve_documents(question, top_k=settings.max_retrieval_chunks)
    recent_messages = recent_messages or []

    if not docs:
        return {
            "answer": "I could not find transcript support for that question in the available Lenny dataset. I would need either a different source excerpt or a narrower question tied to product, growth, or writing concepts from the transcripts.",
            "citations": [],
            "provider": selected_provider,
            "fallback_used": True,
            "artifact": None,
        }

    context = build_context_for_prompt(question, docs)
    system_prompt = (
        "You are the Lenny Growth Assistant. Answer using only the transcript excerpts provided in the context. "
        "If the material does not support the claim, state that clearly. Cite the relevant source by name using the format 'Source: <filename>' "
        "at the end of the relevant sentence or in a short citations list. Keep answers concise but substantive."
    )
    conversation = [{"role": "user", "content": f"Question: {question}\n\nTranscript context:\n{context}"}, *recent_messages]

    if selected_provider == "claude_agent_sdk":
        agent_result = run_claude_agent(question, context, system_prompt)
        if isinstance(agent_result, tuple):
            model_answer, fallback_used = agent_result
        else:
            model_answer = agent_result
            fallback_used = "claude-agent-sdk" in str(agent_result).lower() or "anthropic_api_key" in str(agent_result).lower()
    else:
        model_answer, fallback_used = generate_llm_response(conversation, system_prompt, provider=selected_provider)

    citations = [doc.source for doc in docs]
    return {
        "answer": model_answer,
        "citations": list(dict.fromkeys(citations)),
        "provider": selected_provider,
        "fallback_used": fallback_used,
        "provider_error": selected_provider in {"ollama", "openai", "anthropic", "claude_agent_sdk"} and fallback_used,
        "artifact": None,
    }


def create_ship30_essay(question: str, provider: Optional[str] = None) -> Dict[str, Any]:
    docs = retrieve_documents(question or "Ship 30 for 30 writing system", top_k=settings.max_retrieval_chunks)
    context = build_context_for_prompt(question or "Ship 30 for 30 writing system", docs)
    system_prompt = (
        "You are writing a Ship 30 for 30-style essay in a crisp, skimmable format. Use a strong hook, clear structure, and direct writing principles. "
        "Keep the essay grounded in the transcript excerpts provided. It should be around 1,250 words, include headings and bullets, and end with a practical takeaway. "
        "Do not invent facts or rely on outside knowledge beyond the transcript excerpts."
    )
    essay, fallback_used = generate_llm_response([
        {"role": "user", "content": f"Write the essay based on this question: {question}.\n\nContext:\n{context}"}
    ], system_prompt, provider=provider)
    return {
        "title": "Ship 30 for 30: A grounded writing system",
        "content": essay,
        "citations": [doc.source for doc in docs],
        "fallback_used": fallback_used,
    }


def create_artifact_from_conversation(topic: str, source_text: Optional[str] = None, artifact_type: str = "markdown") -> Dict[str, str]:
    return generate_artifact(topic=topic, source_text=source_text, artifact_type=artifact_type)
