from typing import TypedDict


class ResearchState(TypedDict):
    question: str
    search_queries: list[str]      # queries issued so far (refined each depth)
    search_results: list[dict]     # raw results from search API
    pages_read: list[dict]         # fetched + cleaned page content
    scored_sources: list[dict]     # relevance + trust scored sources
    depth: int
    max_depth: int
    token_budget: int
    tokens_used: int
    should_continue: bool
    final_report: dict | None
    guardrail_passed: bool
    retry_count: int
    error: str | None
