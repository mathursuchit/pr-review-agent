import asyncio
import os
import queue
import sys
import threading
from pathlib import Path

import streamlit as st

for _key in ["GROQ_API_KEY", "TAVILY_API_KEY", "LANGSMITH_API_KEY"]:
    if hasattr(st, "secrets") and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.blog_graph import build_blog_graph

st.set_page_config(page_title="Blog Writer Agent", layout="wide")

NODE_LABELS = {
    "plan_blog":       "Planning blog outline",
    "search":          "Searching the web",
    "read_pages":      "Reading pages",
    "score_relevance": "Scoring source relevance",
    "decide_next":     "Deciding whether to dig deeper",
    "write_blog":      "Writing the blog post",
    "blog_guardrails": "Validating citations",
}


def _check_secrets() -> bool:
    missing = [k for k in ("GROQ_API_KEY", "TAVILY_API_KEY") if not os.environ.get(k)]
    if missing:
        st.error(
            f"Missing required secrets: **{', '.join(missing)}**\n\n"
            "Add them in Streamlit Cloud → App settings → Secrets."
        )
        return False
    return True


@st.cache_resource
def get_graph():
    return build_blog_graph()


def stream_blog(topic: str, tone: str, audience: str, word_count: int, max_depth: int):
    graph = get_graph()
    q: queue.Queue = queue.Queue()

    initial: dict = {
        "topic": topic,
        "tone": tone,
        "target_audience": audience,
        "target_word_count": word_count,
        "question": topic,
        "search_queries": [],
        "search_results": [],
        "pages_read": [],
        "scored_sources": [],
        "depth": 0,
        "max_depth": max_depth,
        "token_budget": 50_000,
        "tokens_used": 0,
        "should_continue": True,
        "blog_outline": None,
        "blog_post": None,
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


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0


def main() -> None:
    if not _check_secrets():
        return

    st.title("Blog Writer Agent")
    st.caption(
        "Give it a topic — it plans an outline, researches the web, and writes a full cited blog post. "
        "Built with LangGraph: plan → search → score → write → validate."
    )

    # ── Sidebar settings ──────────────────────────────────────────
    with st.sidebar:
        st.header("Settings")

        tone = st.selectbox(
            "Tone",
            ["technical", "beginner-friendly", "conversational"],
            index=0,
        )
        audience = st.text_input("Target audience", value="software engineers")
        word_count = st.slider("Target word count", 500, 2000, 1000, step=100)
        max_depth = st.slider(
            "Search depth",
            1, 3, 2,
            help="How many search iterations before writing.",
        )

        st.divider()
        st.caption("Model routing: GPT-4o-mini for planning & scoring, GPT-4o for writing.")

    # ── Topic input ────────────────────────────────────────────────
    topic = st.text_area(
        "Blog topic",
        placeholder="How LangGraph enables production-grade AI agents",
        height=80,
        label_visibility="collapsed",
    )

    run = st.button("Write Blog", type="primary")

    if not run:
        st.markdown(
            """
            **How it works**

            1. **Plan** — GPT-4o-mini creates a title, intro hook, and section outline
            2. **Research** — Searches the web and scores each source for relevance
            3. **Write** — GPT-4o writes a full Markdown post following the outline
            4. **Validate** — Citation check drops any URL not in the actual source list
            """
        )
        return

    if not topic.strip():
        st.error("Enter a blog topic.")
        return

    st.divider()

    # ── Two-column layout: outline | progress ─────────────────────
    col_outline, col_progress = st.columns([1, 1])

    outline_area = col_outline.empty()
    progress_area = col_progress.empty()

    completed: list[str] = []
    final_state: dict | None = None

    with st.spinner(""):
        for event_type, node_name, state in stream_blog(
            topic.strip(), tone, audience, word_count, max_depth
        ):
            if event_type == "node":
                label = NODE_LABELS.get(node_name, node_name)
                if node_name == "search" and state.get("depth", 0) > 0:
                    label += f" (depth {state['depth']})"
                completed.append(label)
                progress_area.markdown("**Progress**\n\n" + "\n".join(f"- {n}" for n in completed))

                # Show outline as soon as plan_blog completes
                outline = state.get("blog_outline")
                if outline:
                    md = f"**{outline['title']}**\n\n_{outline['intro_hook']}_\n\n"
                    for s in outline.get("sections", []):
                        md += f"**{s['heading']}**\n"
                        for kp in s.get("key_points", []):
                            md += f"- {kp}\n"
                        md += "\n"
                    outline_area.markdown(md)

            elif event_type == "done":
                final_state = state

    progress_area.empty()

    if not final_state:
        st.error("Something went wrong.")
        return

    if final_state.get("error"):
        st.error(f"Error: {final_state['error']}")
        return

    blog_post = final_state.get("blog_post")
    if not blog_post:
        st.warning("Research completed but no blog post was generated.")
        return

    # ── Metrics ────────────────────────────────────────────────────
    sources_used = final_state.get("scored_sources", [])
    good = [s for s in sources_used if s.get("relevance_score", 0) >= 0.7]

    m1, m2, m3 = st.columns(3)
    m1.metric("Word count", _word_count(blog_post))
    m2.metric("Sources used", len(good))
    m3.metric("Depth reached", final_state.get("depth", 0))

    st.divider()

    # ── Blog post ──────────────────────────────────────────────────
    st.download_button(
        label="Download .md",
        data=blog_post,
        file_name=f"{topic[:40].replace(' ', '-').lower()}.md",
        mime="text/markdown",
    )

    st.markdown(blog_post)

    # ── Sources inspector ──────────────────────────────────────────
    if sources_used:
        st.divider()
        with st.expander(f"Sources evaluated ({len(sources_used)} total)", expanded=False):
            for s in sorted(sources_used, key=lambda x: x.get("relevance_score", 0), reverse=True):
                rel = s.get("relevance_score", 0)
                trust = s.get("trust_score", 0)
                st.markdown(
                    f"**{rel:.0%}** relevance  |  **{trust:.0%}** trust  |  [{s['url']}]({s['url']})"
                )


if __name__ == "__main__":
    main()
