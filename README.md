# PR Review Agent

I built this to explore what it actually takes to put an LLM-based system into production, not just get it working in a notebook. The agent reviews GitHub pull requests for security issues, logic errors, and missing tests. The interesting part is everything around the LLM call: how you handle untrusted input, control cost, catch hallucinations, and measure quality over time.

## Architecture

```
GitHub PR URL
     |
     v
[fetch_diff] --> [pre_scan] --> route
                    |               |
              injection?        analyze_security
              secrets?          analyze_logic
                                analyze_tests
                                     |
                                [synthesize]  (GPT-4o, strong model only here)
                                     |
                               [post_guardrails]
                                     |
                               schema valid?
                               paths hallucinated?
                                     |
                                final report
```

Built with LangGraph. Each node is a discrete async function with its own error handling. The graph fails open after one guardrail retry rather than crashing.

## Production features

**Reliability**
- Model routing: GPT-4o-mini for per-category analysis, GPT-4o for synthesis only. Keeps cost around $0.008/review.
- Graceful degradation: if a node fails, the graph continues with what it has and flags the gap in the report.
- One guardrail retry before fail-open.

**Security**
- Pre-LLM injection guard: regex patterns catch common prompt injection attempts in PR diffs before they reach the model.
- Secrets redaction: scans for AWS keys, GitHub tokens, OpenAI keys, JWTs, and private keys, replaces them with `[REDACTED]` before sending to the LLM.
- Post-generation hallucination check: any file path cited in a finding that does not appear in the actual diff is corrected to `unknown`.
- API key auth on all endpoints, rate limiting (10 req/min per IP via slowapi).

**Observability**
- LangSmith tracing: every run is traced end-to-end, every tool call logged.
- Structured logging via structlog with request-level trace IDs.
- Prometheus metrics endpoint at `/metrics` (request count, latency p50/p95, in-flight requests).

**Evaluation**
- Golden test cases in `eval/cases/`. Each case has a PR URL and expected finding categories.
- Eval runner scores precision and recall per case, fails CI if either drops below threshold.
- Feedback loop: `POST /api/v1/feedback` lets reviewers mark findings correct or incorrect. Stored in SQLite, intended to grow the eval dataset over time.

**Caching**
- Redis semantic cache via LangChain. Semantically similar diffs skip the LLM entirely. Cache miss degrades gracefully if Redis is unavailable.

## Eval results

All cases are currently skipped (placeholders). Add real PR URLs with known issues to `eval/cases/` to activate.

| Category | Precision | Recall |
|----------|-----------|--------|
| pending  | --        | --     |

## Cost estimate

~$0.008 per review with default model routing (GPT-4o-mini for analysis, GPT-4o for synthesis). Adjust in `agent/nodes/analyze.py` and `agent/nodes/synthesize.py`.

## Run locally

```bash
cp .env.example .env
# fill in OPENAI_API_KEY, GITHUB_TOKEN, API_KEY

docker compose up
```

The API is at `http://localhost:8000`. Prometheus at `http://localhost:9090`.

```bash
# Review a PR
curl -X POST http://localhost:8000/api/v1/review \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pr_url": "https://github.com/owner/repo/pull/123"}' \
  --no-buffer

# Submit feedback
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"pr_url": "...", "finding_id": "security:src/auth.py:42", "correct": false, "comment": "false positive"}'
```

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/unit -q
python eval/run_evals.py --fail-below 0.80
```

## Stack

LangGraph, LangChain, OpenAI, FastAPI, Redis, Prometheus, structlog, Pydantic v2, Docker
