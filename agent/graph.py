from langgraph.graph import StateGraph, END
from agent.state import ResearchState
from agent.nodes import search, read_pages, score_relevance, decide_next, synthesize, guardrails


def _route_after_search(state: ResearchState) -> str:
    if state.get("error"):
        return END
    return "read_pages"


def _route_after_decide(state: ResearchState) -> str:
    if state.get("should_continue"):
        return "search"
    return "synthesize"


def _route_after_guardrails(state: ResearchState) -> str:
    if state.get("guardrail_passed"):
        return END
    if state.get("retry_count", 0) >= 1:
        return END  # fail open — return partial report
    return "synthesize"


def build_graph() -> StateGraph:
    g = StateGraph(ResearchState)

    g.add_node("search",           search.run)
    g.add_node("read_pages",       read_pages.run)
    g.add_node("score_relevance",  score_relevance.run)
    g.add_node("decide_next",      decide_next.run)
    g.add_node("synthesize",       synthesize.run)
    g.add_node("post_guardrails",  guardrails.run)

    g.set_entry_point("search")
    g.add_conditional_edges("search", _route_after_search)
    g.add_edge("read_pages",      "score_relevance")
    g.add_edge("score_relevance", "decide_next")
    g.add_conditional_edges("decide_next", _route_after_decide)
    g.add_edge("synthesize",      "post_guardrails")
    g.add_conditional_edges("post_guardrails", _route_after_guardrails)

    return g.compile()
