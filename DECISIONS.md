# Design Decisions

Short records of the choices behind Sarkari Saathi: what we chose, why, and what we gave up.

## 1. Problem: scheme discovery, not another chatbot
**Decision:** Build an eligibility-and-guidance tool for government schemes.
**Why:** The theme asked for a real problem "you see in your family, your community, or the country". Unclaimed benefits are a concrete gap: the schemes exist, but discovery and eligibility interpretation are hard. The output is verifiable (a scheme is either a match or not), which suits a demo.
**Trade-off:** Narrow domain; value depends on data freshness (see #7).

## 2. The LLM never decides eligibility
**Decision:** Eligibility is computed by a deterministic Python engine over `schemes.json`. The LLM extracts facts, calls a tool, and explains the result.
**Why:** People may act on this output (documents, travel, applications). LLMs can invent criteria or amounts; rules code cannot. It is unit-tested, auditable (each result carries reasons), and cheap to update (edit JSON, not prompts).
**Alternatives rejected:** (a) RAG over scheme PDFs: more coverage, but hallucination risk and no clear pass/fail. (b) Rules pasted into the prompt: unreproducible.
**Trade-off:** Coverage is limited to schemes we encode by hand.

## 3. Three-valued logic: eligible / possibly eligible / not eligible
**Decision:** Each condition is true, false or *unknown*. Any false means not eligible; no false but some unknown means "possibly eligible", listing the missing fields.
**Why:** Users rarely give complete information up front. Treating unknown as "no" hides schemes they qualify for; treating it as "yes" misleads. Surfacing the gap lets the agent ask the one or two questions that matter.

## 4. Rules as data (JSON with `all` / `any` groups)
**Decision:** A tiny declarative rule format instead of per-scheme Python functions.
**Why:** Adding a scheme is a data change, reviewable by non-developers, and the same file powers the API, UI and agent.
**Trade-off:** No arbitrary logic (e.g., state-specific income slabs). Extend the operator set when needed.

## 5. Open-source agent framework, free model by default, model as configuration
**Decision:** Use the open-source Strands Agents SDK (Build It track). The model is chosen by `MODEL_PROVIDER` / `MODEL_ID` env variables. Default: **Gemini 3.6 Flash** on Google's free tier via LiteLLM. Ollama (local), Groq, OpenRouter and Bedrock are supported by config only.
**Why:** The track needs no paid cloud. Gemini 3.6 Flash was tested end to end with tool calling and Hinglish input. During development the first default (`gemini-2.5-flash`) was retired for new API keys and returned `NotFoundError`, so model names are configuration, not code, and the README documents how to fix it.
**Trade-off:** Free tiers have rate limits, and models change. Mitigation: the form and API need no model; Ollama runs fully offline.

## 6. Graceful degradation and visible errors
**Decision:** The agent is imported lazily. If no model is reachable, `/api/chat` returns a clear `503` while the form and `/api/eligibility` keep working. The full exception is logged in the server terminal.
**Why:** Demos fail when a model or network is down, and generic error text made the model-retirement bug hard to diagnose. The core value must never depend on an LLM being available, and failures must be debuggable.

## 7. Data honesty and scope
**Decision:** 13 well-known central schemes, simplified criteria, a `last_reviewed` date, official links, and a visible disclaimer in the API and UI.
**Why:** Wrong benefit info harms users more than missing info. We chose fewer, conservative entries over broad, unverified coverage.
**Known limits:** Amounts and thresholds change; many schemes have state variants; some criteria (e.g., PM-JAY's SECC-based selection) are approximated. **Each entry must be re-verified against its official portal before any production use.**

## 8. Privacy by design
**Decision:** No accounts, no database, no logging of profiles. Chat sessions live in process memory (LRU-capped at 200). The agent is told never to request Aadhaar, PAN, phone or bank numbers. API keys live in a git-ignored `.env`.
**Why:** Users share income, category and family details. The safest data is data we never keep.
**Trade-off:** No history across restarts; multi-instance hosting would need an external session store.

## 9. Optional serverless entrypoint (not required)
**Decision:** Keep a small Lambda handler and SAM template for the deterministic endpoints, but do not make the project depend on AWS.
**Why:** The rules engine is stateless, so it ports to Lambda cheaply if someone wants it. The Build It track is the primary target.
**Status:** The handler is unit-tested locally; the template has not been deployed.

## 10. Single-file UI, no build step
**Decision:** Vanilla HTML/JS served by FastAPI, mobile-first, dark-mode aware, with escaped output.
**Why:** Most target users are on phones; zero toolchain keeps setup short and the repo easy to review.

## What we'd do next
State-level schemes; official-source data refresh with change alerts; voice input for low-literacy users; a WhatsApp channel; evals for multilingual extraction accuracy across models.
