from fastapi.testclient import TestClient

from saathi.agent import build_agent, find_eligible_schemes
from saathi.api import app

client = TestClient(app)


def test_health_and_index():
    assert client.get("/api/health").json() == {"status": "ok"}
    assert "Sarkari Saathi" in client.get("/").text


def test_eligibility_endpoint():
    r = client.post("/api/eligibility", json={"age": 25, "occupation": "unemployed"})
    assert r.status_code == 200
    assert "pmkvy" in {m["id"] for m in r.json()["eligible"]}


def test_eligibility_validation():
    assert client.post("/api/eligibility", json={"age": -5}).status_code == 422


def test_chat_degrades_gracefully(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "nonsense")
    r = client.post("/api/chat", json={"session_id": "x", "message": "hi"})
    assert r.status_code == 503


def test_tool_is_callable_and_agent_builds():
    out = find_eligible_schemes(age=72)
    assert out["profile_used"] == {"age": 72}
    assert "pm-jay" in {m["id"] for m in out["eligible"]}
    from strands.models.ollama import OllamaModel
    agent = build_agent(model=OllamaModel(host="http://localhost:11434", model_id="qwen3:8b"))
    assert {"find_eligible_schemes", "get_scheme_details"} <= set(agent.tool_names)


def test_gemini_is_default_provider_and_model(monkeypatch):
    from saathi.agent import build_model

    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("MODEL_ID", raising=False)
    model = build_model()
    assert model.get_config()["model_id"] == "gemini/gemini-3.6-flash"
