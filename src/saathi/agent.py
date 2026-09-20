"""Strands agent: turns free-form (multilingual) text into a profile, calls the
deterministic engine as a tool, and explains the result in the user's language.

The model provider is chosen by environment variables, so the same code runs
on a laptop with Ollama, on free API tiers (Gemini / Groq via LiteLLM), or on
Amazon Bedrock when deployed on AWS.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Optional

from strands import Agent, tool

from .engine import Profile, find_schemes, get_scheme

SYSTEM_PROMPT = """You are Sarkari Saathi, a friendly assistant that helps people in India \
discover central-government schemes they may be eligible for.

Rules:
1. Reply in the same language the user writes in (Hindi, English, Hinglish, etc.). Use simple words.
2. NEVER decide eligibility yourself. Extract facts the user stated and call `find_eligible_schemes`. \
Only pass fields the user actually told you; leave the rest empty. Never guess.
3. Base every claim about a scheme (benefit, documents, link) only on tool output. If unsure, say so.
4. If the tool returns `ask_user_next`, ask for at most two of those items, in a friendly way.
5. For each eligible scheme give: name, benefit in one line, documents needed, and the official link.
6. Never ask for Aadhaar, PAN, phone or bank numbers. Remind users to confirm details on the official portal.
7. Keep answers short and easy to read on a phone."""


@tool
def find_eligible_schemes(
    age: Optional[int] = None,
    gender: Optional[str] = None,
    occupation: Optional[str] = None,
    annual_family_income: Optional[int] = None,
    social_category: Optional[str] = None,
    owns_land: Optional[bool] = None,
    owns_pucca_house: Optional[bool] = None,
    is_bpl: Optional[bool] = None,
    has_bank_account: Optional[bool] = None,
    has_girl_child_under_10: Optional[bool] = None,
    is_student: Optional[bool] = None,
    wants_business: Optional[bool] = None,
) -> dict[str, Any]:
    """Check which government schemes a person is eligible for. Pass ONLY facts the user stated.

    Args:
        age: Age in years.
        gender: One of male, female, other.
        occupation: One of farmer, student, self_employed, salaried, unemployed, homemaker, retired.
        annual_family_income: Annual family income in rupees (convert lakh to rupees, 1 lakh = 100000).
        social_category: One of general, obc, sc, st.
        owns_land: True if the person owns agricultural land.
        owns_pucca_house: True if the family owns a pucca (permanent) house.
        is_bpl: True if the household is below poverty line / holds a poor-household ration card.
        has_bank_account: True if the person has a bank account.
        has_girl_child_under_10: True if the family has a girl child below 10 years.
        is_student: True if currently studying.
        wants_business: True if the person wants to start or expand a business.
    """
    profile = Profile.from_dict({k: v for k, v in locals().items()})
    result = find_schemes(profile)
    result["profile_used"] = {k: v for k, v in asdict(profile).items() if v is not None}
    return result


@tool
def get_scheme_details(scheme_id: str) -> dict[str, Any]:
    """Get full details (benefit, documents, official link) for one scheme by its id, e.g. 'pm-kisan'.

    Args:
        scheme_id: The scheme id returned by find_eligible_schemes.
    """
    return get_scheme(scheme_id) or {"error": f"Unknown scheme id: {scheme_id}"}


def build_model() -> Any:
    """Create the model from env vars (auto-loaded from .env). See .env.example."""
    provider = os.getenv("MODEL_PROVIDER", "gemini").lower()
    model_id = os.getenv("MODEL_ID")
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0.2"))

    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=model_id or "qwen3:8b",
            temperature=temperature,
        )
    if provider in ("gemini", "groq", "litellm"):
        from strands.models.litellm import LiteLLMModel

        default = {"gemini": "gemini/gemini-3.6-flash", "groq": "groq/llama-3.3-70b-versatile"}.get(provider)
        chosen = model_id or default
        if not chosen:
            raise ValueError("Set MODEL_ID for MODEL_PROVIDER=litellm (e.g. openrouter/<model>:free)")
        # LiteLLM reads GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY from the environment.
        # Gemini 3+ deprecates sampling params, so we only set temperature for other providers.
        params = {} if provider == "gemini" else {"temperature": temperature}
        return LiteLLMModel(model_id=chosen, params=params)
    if provider == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(
            model_id=model_id or "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=temperature,
        )
    raise ValueError(f"Unknown MODEL_PROVIDER: {provider}")


def build_agent(model: Any = None) -> Agent:
    return Agent(
        model=model or build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[find_eligible_schemes, get_scheme_details],
        callback_handler=None,  # no console streaming; we return text
    )
