import asyncio
from agent.nodes.guardrails import run


def _valid_report(question: str = "What is RAG?") -> dict:
    return {
        "question": question,
        "summary": "RAG combines retrieval with generation.",
        "key_findings": ["Retrieval improves factuality"],
        "sources": [],
        "confidence_score": 0.8,
        "depth_reached": 1,
        "tokens_used": 1200,
        "cached": False,
    }


def test_passes_valid_report():
    state = {
        "final_report": _valid_report(),
        "scored_sources": [],
        "retry_count": 0,
    }
    result = asyncio.run(run(state))
    assert result["guardrail_passed"] is True


def test_fails_missing_report():
    state = {"final_report": None, "scored_sources": [], "retry_count": 0}
    result = asyncio.run(run(state))
    assert result["guardrail_passed"] is False
    assert result["retry_count"] == 1


def test_drops_hallucinated_url():
    report = _valid_report()
    report["sources"] = [{
        "url": "https://hallucinated.example.com/fake",
        "title": "Fake source",
        "relevance_score": 0.9,
        "trust_score": 0.5,
        "excerpt": "Does not exist in scored_sources",
    }]
    state = {
        "final_report": report,
        # scored_sources does NOT contain the URL above
        "scored_sources": [{"url": "https://real.example.com", "content": "real"}],
        "retry_count": 0,
    }
    result = asyncio.run(run(state))
    assert result["guardrail_passed"] is True
    assert result["final_report"]["sources"] == []
