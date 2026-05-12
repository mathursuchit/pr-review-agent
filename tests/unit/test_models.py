import pytest
from pydantic import ValidationError
from agent.models import Source, ResearchReport


def test_valid_source():
    s = Source(
        url="https://arxiv.org/abs/2305.14627",
        title="Survey of LLM Agents",
        relevance_score=0.9,
        trust_score=0.9,
        excerpt="This paper surveys...",
    )
    assert s.relevance_score == 0.9


def test_source_score_bounds():
    with pytest.raises(ValidationError):
        Source(
            url="https://example.com",
            title="test",
            relevance_score=1.5,
            trust_score=0.5,
            excerpt="",
        )


def test_valid_report():
    report = ResearchReport(
        question="What is RAG?",
        summary="RAG combines retrieval with generation.",
        key_findings=["Retrieval improves factuality", "Chunking strategy matters"],
        sources=[],
        confidence_score=0.8,
        depth_reached=1,
        tokens_used=1200,
        cached=False,
    )
    assert report.confidence_score == 0.8


def test_confidence_out_of_range():
    with pytest.raises(ValidationError):
        ResearchReport(
            question="test",
            summary="test",
            key_findings=[],
            sources=[],
            confidence_score=1.5,
            depth_reached=1,
            tokens_used=100,
            cached=False,
        )
