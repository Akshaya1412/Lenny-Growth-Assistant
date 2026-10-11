from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _claude_agent_sdk_available() -> bool:
    try:
        import claude_agent_sdk  # noqa: F401

        return True
    except Exception:
        return False


def build_claude_agent_sdk_missing_credentials_message() -> str:
    return (
        "Claude Agent SDK is enabled, but no API key is configured. Set ANTHROPIC_API_KEY or CLAUDE_AGENT_API_KEY "
        "and install the official SDK with `pip install claude-agent-sdk`."
    )


def build_claude_agent_sdk_missing_package_message() -> str:
    return (
        "Claude Agent SDK is configured but the official package is not installed. Install it with "
        "`pip install claude-agent-sdk` before using the `claude_agent_sdk` provider."
    )


def normalize_ollama_model_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    normalized = str(model_name).strip().lower().replace("\\", "/")
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0]
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[1]
    return normalized


def extract_ollama_model_names(payload: Any) -> List[str]:
    if isinstance(payload, dict):
        models = payload.get("models", [])
    elif isinstance(payload, list):
        models = payload
    else:
        models = []

    names: List[str] = []
    for item in models:
        if isinstance(item, dict):
            for key in ("name", "model"):
                value = item.get(key)
                if value:
                    names.append(str(value))
        elif isinstance(item, str):
            names.append(item)
    return names


def build_ollama_unavailable_message(detail: Optional[str] = None) -> str:
    model_name = settings.ollama_model or "llama3.2"
    message = (
        f"Ollama is required for the local provider '{model_name}', but it is unavailable. "
        f"Start it with `ollama serve`, then run `ollama pull {model_name}` and retry the request."
    )
    if detail:
        message = f"{message} Details: {detail}"
    return message


def check_ollama() -> Tuple[bool, Optional[str]]:
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        if response.status_code != 200:
            return False, f"Ollama API returned HTTP {response.status_code}. Start it with `ollama serve` and confirm the model is installed."

        payload = response.json()
        model_names = extract_ollama_model_names(payload)
        if not model_names:
            return False, f"Ollama is running but no models are installed. Run `ollama pull {settings.ollama_model}`."

        requested_model = normalize_ollama_model_name(settings.ollama_model)
        if requested_model and not any(normalize_ollama_model_name(name) == requested_model for name in model_names):
            return False, f"Ollama is running, but the model '{settings.ollama_model}' is not installed. Run `ollama pull {settings.ollama_model}`."

        return True, ", ".join(model_names)
    except httpx.TimeoutException:
        return False, "Ollama request timed out. Start it with `ollama serve` and confirm the model is installed."
    except httpx.RequestError as exc:  # pragma: no cover - environment-specific
        return False, f"Ollama connection failed: {exc}. Start it with `ollama serve` and confirm the model is installed."
    except Exception as exc:  # pragma: no cover - environment-specific
        return False, str(exc)


def provider_status() -> Dict[str, Any]:
    ollama_ok, ollama_detail = check_ollama()
    return {
        "provider": settings.model_provider,
        "ollama_available": ollama_ok,
        "ollama_detail": ollama_detail,
        "openai_configured": bool(settings.openai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "claude_agent_sdk_configured": bool(settings.claude_agent_api_key or settings.anthropic_api_key),
        "claude_agent_sdk_available": _claude_agent_sdk_available(),
    }


def _run_claude_agent_sdk(messages: List[Dict[str, str]], system_prompt: str) -> str:
    prompt = "\n".join(f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages)
    prompt = f"{system_prompt}\n\n{prompt}".strip()

    async def _query() -> str:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

        collected: List[str] = []
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                system_prompt=system_prompt,
                allowed_tools=[],
                permission_mode="default",
                max_turns=3,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in getattr(message, "content", []):
                    if isinstance(block, TextBlock):
                        collected.append(block.text)
            elif isinstance(message, ResultMessage):
                if getattr(message, "result", None):
                    collected.append(message.result)
        return "\n".join(part for part in collected if part).strip() or "Claude Agent SDK responded without any final text."

    return asyncio.run(_query())


def generate_llm_response(messages: List[Dict[str, str]], system_prompt: str, provider: Optional[str] = None) -> Tuple[str, bool]:
    provider = provider or settings.model_provider

    if provider == "ollama":
        ok, detail = check_ollama()
        if not ok:
            message = build_ollama_unavailable_message(detail)
            logger.warning(message)
            return message, True
        try:
            payload = {
                "model": settings.ollama_model,
                "messages": [{"role": "system", "content": system_prompt}, *messages],
                "stream": False,
                "options": {"temperature": 0.2},
            }
            response = httpx.post(f"{settings.ollama_base_url}/api/chat", json=payload, timeout=60.0)
            if response.status_code != 200:
                message = (
                    f"Ollama returned HTTP {response.status_code} while generating a local response. "
                    f"Start it with `ollama serve` and confirm the model with `ollama list`."
                )
                logger.warning(message)
                return message, True
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content")
            if isinstance(content, str) and content.strip():
                return content.strip(), False
            return "Ollama responded without content. Check the local model and retry.", True
        except httpx.TimeoutException:
            message = (
                "Ollama timed out while generating a local response. Start it with `ollama serve`, "
                f"then run `ollama pull {settings.ollama_model}` and retry."
            )
            logger.warning(message)
            return message, True
        except httpx.RequestError as exc:  # pragma: no cover - environment-specific
            message = build_ollama_unavailable_message(f"request error: {exc}")
            logger.warning(message)
            return message, True
        except Exception as exc:  # pragma: no cover - environment-specific
            logger.exception("Failed during Ollama call: %s", exc)
            return build_ollama_unavailable_message(str(exc)), True

    if provider == "openai":
        api_key = settings.openai_api_key
        if not api_key:
            message = "OpenAI is selected, but OPENAI_API_KEY is not configured. Choose Ollama or configure the key locally."
            logger.warning("OpenAI provider selected without credentials")
            return message, True
        try:
            import openai

            client = openai.OpenAI(api_key=api_key)
            completion = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": system_prompt}, *messages],
                temperature=0.2,
            )
            content = completion.choices[0].message.content
            if isinstance(content, str) and content.strip():
                return content.strip(), False
            return "OpenAI returned an empty response. Retry the request.", True
        except Exception:  # pragma: no cover - environment-specific
            logger.warning("OpenAI request failed")
            return "OpenAI request failed. Check provider availability and local credentials, then retry.", True

    if provider == "anthropic":
        api_key = settings.anthropic_api_key
        if not api_key:
            message = "Anthropic is selected, but ANTHROPIC_API_KEY is not configured. Choose Ollama or configure the key locally."
            logger.warning("Anthropic provider selected without credentials")
            return message, True
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1200,
                system=system_prompt,
                messages=messages,
            )
            content = response.content[0].text if response.content else None
            if isinstance(content, str) and content.strip():
                return content.strip(), False
            return "Anthropic returned an empty response. Retry the request.", True
        except Exception:  # pragma: no cover - environment-specific
            logger.warning("Anthropic request failed")
            return "Anthropic request failed. Check provider availability and local credentials, then retry.", True

    if provider == "claude_agent_sdk":
        api_key = settings.claude_agent_api_key or settings.anthropic_api_key
        if not api_key:
            message = build_claude_agent_sdk_missing_credentials_message()
            logger.warning(message)
            return message, True
        if not _claude_agent_sdk_available():
            message = build_claude_agent_sdk_missing_package_message()
            logger.warning(message)
            return message, True
        try:
            return _run_claude_agent_sdk(messages, system_prompt), False
        except Exception:  # pragma: no cover - environment-specific
            logger.warning("Claude Agent SDK execution failed")
            return (
                "Claude Agent SDK execution failed. Install the official package and confirm your API credentials are valid: "
                "`pip install claude-agent-sdk` and set ANTHROPIC_API_KEY or CLAUDE_AGENT_API_KEY.",
                True,
            )

    return mock_response(messages, system_prompt), True


def mock_response(messages: List[Dict[str, str]], system_prompt: str) -> str:
    last_user = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            last_user = message.get("content", "")
            break
    if not last_user:
        return "I am operating in offline fallback mode and can answer using the transcript excerpts available in this app."
    return (
        "Based on the transcript excerpts available in this workspace, the core idea is that product and growth work should be "
        "rooted in customer insight and repeated learning loops. The best teams build small experiments, listen closely to user behavior, "
        f"and focus on compounding distribution signals rather than vanity metrics. User ask: {last_user[:180]}"
    )
