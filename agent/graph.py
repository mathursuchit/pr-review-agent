from langgraph.graph import StateGraph, END
from agent.state import ReviewState
from agent.nodes import fetch_diff, pre_scan, analyze, synthesize, guardrails


def _route_after_prescan(state: ReviewState) -> str:
    if state.get("error"):
        return "reject"
    if state.get("injection_flagged"):
        return "reject"
    return "analyze_security"


def _route_after_guardrails(state: ReviewState) -> str:
    if state.get("guardrail_passed"):
        return END
    if state.get("retry_count", 0) >= 1:
        # Fail open after one retry — return partial report flagged
        return END
    return "synthesize"


def build_graph() -> StateGraph:
    g = StateGraph(ReviewState)

    g.add_node("fetch_diff", fetch_diff.run)
    g.add_node("pre_scan", pre_scan.run)
    g.add_node("analyze_security", analyze.security)
    g.add_node("analyze_logic", analyze.logic)
    g.add_node("analyze_tests", analyze.tests)
    g.add_node("synthesize", synthesize.run)
    g.add_node("post_guardrails", guardrails.run)
    g.add_node("reject", pre_scan.reject)

    g.set_entry_point("fetch_diff")
    g.add_edge("fetch_diff", "pre_scan")
    g.add_conditional_edges("pre_scan", _route_after_prescan)
    g.add_edge("analyze_security", "analyze_logic")
    g.add_edge("analyze_logic", "analyze_tests")
    g.add_edge("analyze_tests", "synthesize")
    g.add_edge("synthesize", "post_guardrails")
    g.add_conditional_edges("post_guardrails", _route_after_guardrails)
    g.add_edge("reject", END)

    return g.compile()
