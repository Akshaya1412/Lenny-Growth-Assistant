import json
import os
from uuid import uuid4
from unittest.mock import MagicMock, patch

import httpx
import pytest

os.environ.setdefault("USE_SQLITE_FALLBACK", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_lenny_growth.db")

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm import generate_llm_response

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database_status"] == "up"


def test_static_chat_ui_serves_session_provider_and_artifact_controls():
    page = client.get("/static/index.html")
    script = client.get("/static/app.js")

    assert page.status_code == 200
    assert script.status_code == 200
    assert 'id="sessionSearch"' in page.text
    assert 'id="providerSelect"' in page.text
    assert 'id="openArtifactBtn"' in page.text
    assert "provider," in script.text
    assert "/api/v1/sessions/" in script.text


def test_create_session_and_send_message():
    session_response = client.post("/api/v1/sessions", json={"user_name": "demo-user"})
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    chat_response = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "What matters most for product-market fit?", "provider": "mock"},
    )
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert payload["reply"]
    assert payload["citations"]


def test_session_list_preview_rename_and_delete():
    session_response = client.post("/api/v1/sessions", json={"user_name": "sidebar-test"})
    session_id = session_response.json()["id"]
    prompt = "How should we approach a new growth loop?"

    message_response = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": prompt, "provider": "mock"},
    )
    assert message_response.status_code == 200

    listed = client.get("/api/v1/sessions").json()
    listed_session = next(item for item in listed if item["id"] == session_id)
    assert listed_session["preview"] == prompt
    assert listed_session["title"] == prompt

    rename_response = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"title": "Growth loop research"},
    )
    assert rename_response.status_code == 200
    assert client.get(f"/api/v1/sessions/{session_id}").json()["title"] == "Growth loop research"

    delete_response = client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
    assert client.get(f"/api/v1/sessions/{session_id}").status_code == 404


def test_provider_availability_is_reported():
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    availability = response.json()["provider_availability"]
    assert "ollama" in availability
    assert "openai" in availability
    assert "anthropic" in availability
    assert "claude_agent_sdk" in availability


def test_follow_up_messages_and_chat_sessions_are_independent():
    first_session = client.post("/api/v1/sessions", json={"user_name": "independent-test-one"}).json()
    second_session = client.post("/api/v1/sessions", json={"user_name": "independent-test-two"}).json()

    for message in ("First question", "Follow-up question"):
        response = client.post(
            f"/api/v1/sessions/{first_session['id']}/messages",
            json={"message": message, "provider": "mock"},
        )
        assert response.status_code == 200

    response = client.post(
        f"/api/v1/sessions/{second_session['id']}/messages",
        json={"message": "Separate conversation", "provider": "mock"},
    )
    assert response.status_code == 200

    first_history = client.get(f"/api/v1/sessions/{first_session['id']}").json()["messages"]
    second_history = client.get(f"/api/v1/sessions/{second_session['id']}").json()["messages"]

    assert [message["role"] for message in first_history] == ["user", "assistant", "user", "assistant"]
    assert first_history[2]["content"] == "Follow-up question"
    assert len(second_history) == 2
    assert second_history[0]["content"] == "Separate conversation"


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Set TEST_POSTGRES_URL to run PostgreSQL integration coverage")
def test_postgres_persists_session_message_timestamps_and_metadata():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Base, ChatMessage, ChatSession

    engine = create_engine(os.environ["TEST_POSTGRES_URL"], pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    database_session = sessionmaker(bind=engine)()
    session_id = None

    try:
        chat_session = ChatSession(user_name=f"postgres-test-{uuid4()}", title="PostgreSQL persistence test")
        chat_message = ChatMessage(
            session=chat_session,
            role="assistant",
            content="Persisted response",
            citations=json.dumps(["source.txt"]),
            artifact={"type": "html", "content": "<p>Saved metadata</p>"},
        )
        database_session.add(chat_session)
        database_session.add(chat_message)
        database_session.commit()
        session_id = chat_session.id
        database_session.expunge_all()

        saved_session = database_session.query(ChatSession).filter_by(id=session_id).one()
        saved_message = saved_session.messages[0]

        assert saved_session.created_at is not None
        assert saved_session.updated_at is not None
        assert saved_message.created_at is not None
        assert json.loads(saved_message.citations) == ["source.txt"]
        assert saved_message.artifact == {"type": "html", "content": "<p>Saved metadata</p>"}
    finally:
        if session_id:
            database_session.query(ChatSession).filter_by(id=session_id).delete()
            database_session.commit()
        database_session.close()
        engine.dispose()


def test_generate_artifact_endpoint():
    artifact_response = client.post(
        "/api/v1/artifacts",
        json={"topic": "Growth strategy", "artifact_type": "html", "source_text": "Ground the plan in product signals and compounding learning loops."},
    )
    assert artifact_response.status_code == 200
    payload = artifact_response.json()
    assert payload["type"] == "html"
    assert "Growth strategy" in payload["content"] or "Ground the plan" in payload["content"]


def test_generate_llm_response_ollama_success_uses_local_model():
    with patch("app.services.llm.httpx.get") as mock_get, patch("app.services.llm.httpx.post") as mock_post:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.2:latest"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"message": {"content": "live answer"}}
        mock_post.return_value.raise_for_status.return_value = None

        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="ollama",
        )

    assert result == "live answer"
    assert fallback_used is False
    mock_post.assert_called_once()


def test_generate_llm_response_ollama_unavailable_returns_actionable_error():
    with patch("app.services.llm.httpx.get", side_effect=httpx.ConnectError("connection refused")):
        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="ollama",
        )

    assert fallback_used is True
    assert "ollama serve" in result.lower()
    assert "ollama pull llama3.2" in result.lower()
    assert "cloud" not in result.lower()


def test_generate_llm_response_ollama_missing_model_reports_install_step():
    with patch("app.services.llm.httpx.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}

        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="ollama",
        )

    assert fallback_used is True
    assert "ollama pull llama3.2" in result.lower()


def test_generate_llm_response_ollama_timeout_is_actionable():
    with patch("app.services.llm.httpx.get") as mock_get, patch(
        "app.services.llm.httpx.post", side_effect=httpx.ReadTimeout("timed out")
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.2:latest"}]}

        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="ollama",
        )

    assert fallback_used is True
    assert "timed out" in result.lower()


def test_generate_llm_response_ollama_http_error_is_actionable():
    with patch("app.services.llm.httpx.get") as mock_get, patch("app.services.llm.httpx.post") as mock_post:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_post.return_value.status_code = 500

        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="ollama",
        )

    assert fallback_used is True
    assert "http 500" in result.lower()


def test_generate_llm_response_ollama_empty_content_is_actionable():
    with patch("app.services.llm.httpx.get") as mock_get, patch("app.services.llm.httpx.post") as mock_post:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"message": {"content": "  "}}

        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="ollama",
        )

    assert fallback_used is True
    assert "without content" in result.lower()


def test_message_route_passes_selected_provider_to_agent():
    session_response = client.post("/api/v1/sessions", json={"user_name": "provider-test"})
    session_id = session_response.json()["id"]
    answer = {
        "answer": "Local answer",
        "citations": ["source.txt"],
        "provider": "ollama",
        "fallback_used": False,
        "provider_error": False,
    }

    with patch("app.api.routes.answer_question", return_value=answer) as mock_answer:
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"message": "What matters most?", "provider": "ollama"},
        )

    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"
    assert mock_answer.call_args.kwargs["provider"] == "ollama"


def test_ollama_provider_error_is_returned_as_service_unavailable():
    session_response = client.post("/api/v1/sessions", json={"user_name": "ollama-error-test"})
    session_id = session_response.json()["id"]
    answer = {
        "answer": "Ollama timed out. Retry the local request.",
        "citations": ["source.txt"],
        "provider": "ollama",
        "fallback_used": True,
        "provider_error": True,
    }

    with patch("app.api.routes.answer_question", return_value=answer):
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"message": "What matters most?", "provider": "ollama"},
        )

    assert response.status_code == 503
    assert "timed out" in response.json()["detail"].lower()


def test_agent_question_uses_claude_agent_sdk_route_when_configured():
    from app.services.agent import answer_question

    with patch("app.services.agent.retrieve_documents") as mock_docs, patch("app.services.agent.run_claude_agent") as mock_agent:
        mock_docs.return_value = [MagicMock(source="source-01.txt")]
        mock_agent.return_value = "Agent answer with Source: source-01.txt"

        result = answer_question("What matters most?", provider="claude_agent_sdk")

    assert result["provider"] == "claude_agent_sdk"
    assert result["answer"] == "Agent answer with Source: source-01.txt"
    assert result["citations"] == ["source-01.txt"]
    mock_agent.assert_called_once()


def test_generate_llm_response_agent_sdk_missing_credentials_returns_actionable_error():
    with patch("app.services.llm.settings.claude_agent_api_key", None), patch("app.services.llm.settings.anthropic_api_key", None):
        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider="claude_agent_sdk",
        )

    assert fallback_used is True
    assert "ANTHROPIC_API_KEY" in result.upper()
    assert "claude-agent-sdk" in result.lower()


@pytest.mark.parametrize(
    ("provider", "setting_name", "credential_name"),
    [
        ("openai", "openai_api_key", "OPENAI_API_KEY"),
        ("anthropic", "anthropic_api_key", "ANTHROPIC_API_KEY"),
    ],
)
def test_cloud_provider_missing_credentials_never_returns_mock(provider, setting_name, credential_name):
    with patch(f"app.services.llm.settings.{setting_name}", None):
        result, fallback_used = generate_llm_response(
            [{"role": "user", "content": "What matters most?"}],
            "You are a helpful assistant.",
            provider=provider,
        )

    assert fallback_used is True
    assert credential_name in result
    assert "based on the transcript excerpts" not in result.lower()
