import structlog
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agent.models import ResearchReport
from agent.state import ResearchState

logger = structlog.get_logger()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a research synthesizer. Write a comprehensive report answering the question. "
        "Only cite URLs that appear in the provided sources — do not invent URLs or facts. "
        "Set confidence_score based on source quality and coverage (0.0 = very uncertain, 1.0 = highly confident).",
    ),
    ("human", "Question: {question}\n\nSources:\n{sources}"),
])


async def run(state: ResearchState) -> dict:
    if state.get("error"):
        return {"final_report": None}

    scored = state.get("scored_sources", [])
    good_sources = [s for s in scored if s.get("relevance_score", 0) >= 0.4]

    if not good_sources:
        return {"final_report": None, "error": "No relevant sources found."}

    sources_text = "\n\n".join(
        f"[{i + 1}] {s.get('title', '')}\nURL: {s['url']}\n{s['content'][:800]}"
        for i, s in enumerate(good_sources)
    )

    structured_llm = llm.with_structured_output(ResearchReport)

    try:
        report = await (PROMPT | structured_llm).ainvoke({
            "question": state["question"],
            "sources": sources_text,
        })
        return {"final_report": report.model_dump(), "retry_count": state.get("retry_count", 0)}
    except Exception as e:
        logger.error("synthesis_failed", error=str(e))
        return {"final_report": None, "retry_count": state.get("retry_count", 0)}
