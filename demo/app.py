import asyncio
import os
import queue
import sys
import threading
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph import build_graph

st.set_page_config(page_title="PR Review Agent", layout="wide")

SEVERITY_COLORS = {
    "critical": "#ff4b4b",
    "high":     "#ff8c00",
    "medium":   "#ffd700",
    "low":      "#4b9fff",
    "info":     "#888888",
}

NODE_LABELS = {
    "fetch_diff":        "Fetching PR diff from GitHub",
    "pre_scan":          "Scanning for injection attempts and secrets",
    "analyze_security":  "Analyzing security vulnerabilities",
    "analyze_logic":     "Analyzing logic errors and edge cases",
    "analyze_tests":     "Checking test coverage",
    "synthesize":        "Synthesizing final report",
    "post_guardrails":   "Validating output",
    "reject":            "Review rejected (injection detected)",
}


@st.cache_resource
def get_graph():
    return build_graph()


def stream_review(pr_url: str):
    graph = get_graph()
    q: queue.Queue = queue.Queue()

    initial: dict = {
        "pr_url": pr_url,
        "raw_diff": "",
        "chunks": [],
        "injection_flagged": False,
        "secrets_found": [],
        "security_findings": [],
        "logic_findings": [],
        "test_findings": [],
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


def render_findings(findings: list[dict]) -> None:
    if not findings:
        st.success("No issues found.")
        return

    # Group by severity for display order
    order = ["critical", "high", "medium", "low", "info"]
    sorted_findings = sorted(findings, key=lambda f: order.index(f.get("severity", "info")))

    for f in sorted_findings:
        severity = f.get("severity", "info")
        color = SEVERITY_COLORS.get(severity, "#888888")
        label = f"[{severity.upper()}]  {f.get('category', '')}  —  {f.get('file_path', 'unknown')}"

        with st.expander(label, expanded=severity in ("critical", "high")):
            cols = st.columns([1, 2])
            with cols[0]:
                st.markdown(f"**Severity**")
                st.markdown(f"**Category**")
                st.markdown(f"**File**")
                if f.get("line_range"):
                    st.markdown(f"**Lines**")
            with cols[1]:
                st.markdown(f":{color.replace('#', '')}[{severity}]" if False else severity)
                st.markdown(f.get("category", ""))
                st.code(f.get("file_path", "unknown"), language=None)
                if f.get("line_range"):
                    st.markdown(f.get("line_range", ""))

            st.markdown(f"**Issue**")
            st.markdown(f.get("description", ""))
            st.markdown(f"**Suggestion**")
            st.info(f.get("suggestion", ""))


def main() -> None:
    st.title("PR Review Agent")
    st.caption(
        "Analyzes GitHub pull requests for security issues, logic errors, and missing tests. "
        "Built with LangGraph — each step is a separate node in the state machine."
    )

    st.divider()

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        pr_url = st.text_input(
            "GitHub PR URL",
            placeholder="https://github.com/owner/repo/pull/123",
            label_visibility="collapsed",
        )
    with col_btn:
        run = st.button("Review PR", type="primary", use_container_width=True)

    if not run:
        st.markdown(
            """
            **How it works**

            1. Fetches the PR diff from the GitHub API
            2. Scans for prompt injection attempts and secrets before sending anything to the LLM
            3. Runs three parallel analysis passes: security, logic, test coverage
            4. Synthesizes findings into a structured report using GPT-4o
            5. Validates the output — corrects hallucinated file paths, enforces schema

            **Cost:** ~$0.008 per review with default model routing
            """
        )
        return

    if not pr_url or not pr_url.startswith("https://github.com/"):
        st.error("Enter a valid GitHub PR URL (https://github.com/owner/repo/pull/N).")
        return

    st.divider()

    # --- Progress ---
    progress_area = st.empty()
    completed: list[str] = []
    final_state: dict | None = None

    with st.spinner(""):
        for event_type, node_name, state in stream_review(pr_url):
            if event_type == "node":
                label = NODE_LABELS.get(node_name, node_name)
                completed.append(f"**{label}**")
                progress_area.markdown("\n\n".join(f"- {n}" for n in completed))
            elif event_type == "done":
                final_state = state

    progress_area.empty()

    if not final_state:
        st.error("Review failed — no state returned.")
        return

    # --- Error states ---
    if final_state.get("injection_flagged"):
        st.error("Review aborted: prompt injection detected in the PR diff.")
        return

    if final_state.get("error"):
        st.error(f"Error: {final_state['error']}")
        return

    report = final_state.get("final_report")
    if not report:
        st.warning("Review completed but the report could not be generated.")
        return

    # --- Warnings ---
    if final_state.get("secrets_found"):
        st.warning(
            f"Secrets detected and redacted before analysis: "
            f"{', '.join(final_state['secrets_found'])}"
        )

    # --- Metrics ---
    risk = report.get("risk_score", 0.0)
    findings = report.get("findings", [])
    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    high_count = sum(1 for f in findings if f.get("severity") == "high")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Risk Score", f"{risk:.1f} / 10")
    m2.metric("Total Findings", len(findings))
    m3.metric("Critical", critical_count)
    m4.metric("High", high_count)
    m5.metric("Cached", "Yes" if report.get("cached") else "No")

    # --- Summary ---
    st.markdown(f"**{report.get('summary', '')}**")

    st.caption(
        f"Model: {report.get('model_used', 'unknown')}  |  "
        f"Tokens: {report.get('tokens_used', 0):,}  |  "
        f"Guardrail passed: {'yes' if final_state.get('guardrail_passed') else 'no'}"
    )

    st.divider()

    # --- Findings ---
    st.subheader("Findings")
    render_findings(findings)

    # --- Raw diff inspector ---
    with st.expander("View raw diff (post-redaction)", expanded=False):
        raw = final_state.get("raw_diff", "")
        st.code(raw[:5000] + (" ... (truncated)" if len(raw) > 5000 else ""), language="diff")

    # --- Feedback ---
    st.divider()
    st.subheader("Feedback")
    st.caption("Help improve the eval dataset by marking findings as correct or incorrect.")

    feedback_submitted = False
    for i, f in enumerate(findings):
        finding_id = f"{f.get('category')}:{f.get('file_path')}:{f.get('line_range', '')}"
        cols = st.columns([6, 1, 1])
        cols[0].markdown(f"`{finding_id}`  {f.get('description', '')[:80]}")
        if cols[1].button("Correct", key=f"correct_{i}"):
            _submit_feedback(pr_url, finding_id, correct=True)
            feedback_submitted = True
        if cols[2].button("Wrong", key=f"wrong_{i}"):
            _submit_feedback(pr_url, finding_id, correct=False)
            feedback_submitted = True

    if feedback_submitted:
        st.success("Feedback saved.")


def _submit_feedback(pr_url: str, finding_id: str, correct: bool) -> None:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from feedback.store import save_feedback
        save_feedback({"pr_url": pr_url, "finding_id": finding_id, "correct": correct, "comment": None})
    except Exception:
        pass  # feedback is best-effort


if __name__ == "__main__":
    main()
