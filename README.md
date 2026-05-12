# Research Agent

Built to explore what it actually takes to put an LLM-based agent into production, not just get it working in a notebook. Takes a research question, searches the web iteratively, scores source relevance, and synthesizes a cited report. The interesting part is everything around the LLM calls: controlling search depth, enforcing token budgets, scoring source trust, catching citation hallucinations, and measuring quality over time.

## Architecture

```
question
   |
[search] ──── Tavily web search (refined query each depth)
   |
[read_pages] ── fetch + clean top pages in parallel
   |
[score_relevance] ── GPT-4o-mini scores each source 0-1
   |
[decide_next] ── enough good sources? synthesize : search again
   |    ^
   |    └── loop (max_depth / token_budget hard stops)
   |
[synthesize] ── GPT-4o writes cited report
   |
[post_guardrails] ── schema check + drop hallucinated URLs
   |
final report
```

## Production features

**Cost control**
- Model routing: GPT-4o-mini for relevance scoring, GPT-4o for synthesis only
- Token budget enforced at the graph level — agent can't spiral past 50K tokens
- Depth limit (1-3) enforced before any LLM call, not after

**Security**
- Injection guard: question scanned for prompt injection patterns before search
- Citation hallucination check: any URL in the final report not present in scored sources is dropped
- Rate limiting: 10 req/min per IP (slowapi)
- API key auth on all endpoints

**Observability**
- LangSmith tracing: every run traced end-to-end, every node logged
- Structured logging via structlog with request-level context
- Prometheus metrics at `/metrics` (latency p50/p95, request count, in-flight)

**Source quality**
- Trust scoring: known high-quality domains (arxiv, GitHub, .edu, .gov) scored higher; low-quality patterns (Pinterest, ad trackers) scored lower
- Relevance scoring separate from trust — a trustworthy page can still be off-topic

**Evaluation**
- Golden cases in `eval/cases/research.json` — enable once `TAVILY_API_KEY` is set in CI
- Eval runner scores whether the agent found sources and generated a report; fails CI below threshold
- Feedback loop: `POST /api/v1/feedback` to mark sources as useful or not — stored in SQLite

**Caching**
- Redis semantic cache: semantically similar questions skip the LLM entirely, served from cache

## Eval results

Eval cases are currently skipped pending CI secrets. Add `TAVILY_API_KEY` to GitHub Actions secrets to activate.

| Case | Status |
|------|--------|
| LLM production challenges | pending |
| RAG evaluation methods | pending |

## Cost estimate

~$0.02-0.05 per research query depending on depth and page count.

## Run locally

```bash
cp .env.example .env
# fill in OPENAI_API_KEY, TAVILY_API_KEY, API_KEY

docker compose up
```

| Service | URL |
|---------|-----|
| Streamlit demo | http://localhost:8501 |
| API | http://localhost:8000 |
| Prometheus | http://localhost:9090 |

```bash
# Research a question
curl -X POST http://localhost:8000/api/v1/research \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the production challenges of deploying LLM agents?", "max_depth": 2}' \
  --no-buffer
```

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/unit -q
python eval/run_evals.py --fail-below 0.80
```

## Stack

LangGraph, LangChain, OpenAI, Tavily, FastAPI, Redis, Prometheus, structlog, Pydantic v2, Docker
