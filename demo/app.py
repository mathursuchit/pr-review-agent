import asyncio
import os
import queue
import sys
import threading
from pathlib import Path

import streamlit as st

# Inject Streamlit Cloud secrets into env vars before any agent imports
for _key in ["GROQ_API_KEY", "TAVILY_API_KEY", "LANGSMITH_API_KEY"]:
    if hasattr(st, "secrets") and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph import build_graph


def _check_secrets() -> bool:
    missing = [k for k in ("GROQ_API_KEY", "TAVILY_API_KEY") if not os.environ.get(k)]
    if missing:
        st.error(
            f"Missing required secrets: **{', '.join(missing)}**\n\n"
            "Add them in the Streamlit Cloud dashboard → App settings → Secrets:\n"
            "```toml\n"
            "GROQ_API_KEY = \"gsk_...\"\n"
            "TAVILY_API_KEY = \"tvly-...\"\n"
            "LANGSMITH_API_KEY = \"ls__...\"  # optional\n"
            "```"
        )
        return False
    return True

st.set_page_config(page_title="Research Agent", layout="wide")

NODE_LABELS = {
    "search":          "Searching the web",
    "read_pages":      "Reading pages",
    "score_relevance": "Scoring source relevance",
    "decide_next":     "Deciding whether to dig deeper",
    "synthesize":      "Synthesizing report",
    "post_guardrails": "Validating citations",
}


@st.cache_resource
def get_graph():
    return build_graph()


def stream_research(question: str, max_depth: int):
    graph = get_graph()
    q: queue.Queue = queue.Queue()

    initial: dict = {
        "question": question,
        "search_queries": [],
        "search_results": [],
        "pages_read": [],
        "scored_sources": [],
        "depth": 0,
        "max_depth": max_depth,
        "token_budget": 50_000,
        "tokens_used": 0,
        "should_continue": True,
        "final_report": None,
        "guardrail_passed": False,
        "retry_count": 0,
        "error": None,
    }

    async def _run():
        state = dict(initial)
        async for chunk in graph.astream(initial, stream_mode="updates"):
            node = list(chunk.keys())[0]
            state.update(chunk[node])
            q.put(("node", node, dict(state)))
        q.put(("done", None, dict(state)))

    def _thread():
        asyncio.run(_run())

    t = threading.Thread(target=_thread, daemon=True)
    t.start()

    while True:
        item = q.get()
        yield item
        if item[0] == "done":
            break


def trust_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def main() -> None:
    if not _check_secrets():
        return

    st.title("Research Agent")
    st.caption(
        "Searches the web, reads pages, scores source relevance, and synthesizes a cited report. "
        "Built with LangGraph — iterates until it has enough high-quality sources or hits the depth limit."
    )

    st.divider()

    question = st.text_area(
        "Research question",
        placeholder="What are the production challenges of deploying LLM-based agents at scale?",
        height=80,
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        max_depth = st.slider("Max search depth", min_value=1, max_value=3, value=2,
                              help="How many search iterations the agent can run before synthesizing.")
    with col2:
        run = st.button("Research", type="primary", use_container_width=True)

    if not run:
        st.markdown(
            """
            **How it works**

            1. Searches the web using Tavily
            2. Fetches and cleans the top pages
            3. Scores each source for relevance (0-1) using GPT-4o-mini
            4. Decides whether to search again with a refined query or synthesize
            5. Synthesizes a report with key findings and cited sources using GPT-4o
            6. Validates citations — drops any URL not in the actual source list
            """
        )
        return

    if not question.strip():
        st.error("Enter a research question.")
        return

    st.divider()

    progress_area = st.empty()
    completed: list[str] = []
    final_state: dict | None = None

    with st.spinner(""):
        for event_type, node_name, state in stream_research(question.strip(), max_depth):
            if event_type == "node":
                label = NODE_LABELS.get(node_name, node_name)
                completed.append(label)

                # Show depth context on search iterations
                if node_name == "search" and state.get("depth", 0) > 0:
                    completed[-1] += f" (depth {state['depth']})"

                progress_area.markdown("\n\n".join(f"- {n}" for n in completed))
            elif event_type == "done":
                final_state = state

    progress_area.empty()

    if not final_state:
        st.error("Research failed.")
        return

    if final_state.get("error"):
        st.error(f"Error: {final_state['error']}")
        return

    report = final_state.get("final_report")
    if not report:
        st.warning("Research completed but no report was generated.")
        return

    # --- Metrics ---
    confidence = report.get("confidence_score", 0.0)
    sources = report.get("sources", [])
    depth = report.get("depth_reached", final_state.get("depth", 0))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Confidence", f"{confidence:.0%}")
    m2.metric("Sources cited", len(sources))
    m3.metric("Depth reached", depth)
    m4.metric("Cached", "Yes" if report.get("cached") else "No")

    st.divider()

    # --- Summary ---
    st.subheader("Summary")
    st.markdown(report.get("summary", ""))

    # --- Key findings ---
    findings = report.get("key_findings", [])
    if findings:
        st.subheader("Key findings")
        for f in findings:
            st.markdown(f"- {f}")

    st.divider()

    # --- Sources ---
    st.subheader("Sources")
    for s in sorted(sources, key=lambda x: x.get("relevance_score", 0), reverse=True):
        rel = s.get("relevance_score", 0)
        trust = s.get("trust_score", 0)
        with st.expander(f"{s.get('title', s['url'])}  —  relevance {rel:.0%}", expanded=rel >= 0.7):
            st.markdown(f"[{s['url']}]({s['url']})")
            cols = st.columns(2)
            cols[0].caption(f"Relevance: {rel:.0%}")
            cols[1].caption(f"Source trust: {trust_label(trust)} ({trust:.0%})")
            if s.get("excerpt"):
                st.markdown(s["excerpt"])

    # --- Sources inspector ---
    scored = final_state.get("scored_sources", [])
    with st.expander(f"All evaluated sources ({len(scored)} total)", expanded=False):
        for s in sorted(scored, key=lambda x: x.get("relevance_score", 0), reverse=True):
            rel = s.get("relevance_score", 0)
            trust = s.get("trust_score", 0)
            st.markdown(
                f"**{rel:.0%}** relevance  |  **{trust:.0%}** trust  |  [{s['url']}]({s['url']})"
            )

    # --- Feedback ---
    st.divider()
    st.subheader("Feedback")
    st.caption("Mark sources as useful or not to improve the eval dataset.")

    for i, s in enumerate(sources):
        finding_id = f"source:{s['url']}"
        cols = st.columns([6, 1, 1])
        cols[0].markdown(f"[{s.get('title', s['url'])}]({s['url']})")
        if cols[1].button("Useful", key=f"useful_{i}"):
            _submit_feedback(question, finding_id, correct=True)
            st.toast("Feedback saved.")
        if cols[2].button("Not useful", key=f"not_{i}"):
            _submit_feedback(question, finding_id, correct=False)
            st.toast("Feedback saved.")


def _submit_feedback(question: str, finding_id: str, correct: bool) -> None:
    try:
        from feedback.store import save_feedback
        save_feedback({"pr_url": question, "finding_id": finding_id, "correct": correct, "comment": None})
    except Exception:
        pass


if __name__ == "__main__":
    main()
