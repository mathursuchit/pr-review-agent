import structlog
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agent.models import ReviewReport
from agent.state import ReviewState

logger = structlog.get_logger()

# Strong model for final synthesis only — cost-controlled via model routing
llm_strong = ChatOpenAI(model="gpt-4o", temperature=0)

SYNTH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a senior code reviewer. Synthesize the provided findings into a concise review report. "
        "Set risk_score 0-10 based on severity distribution. "
        "Only include findings that are in the provided list — do not invent new ones.",
    ),
    ("human", "PR: {pr_url}\n\nFindings:\n{findings}"),
])


async def run(state: ReviewState) -> dict:
    if state.get("error"):
        return {"final_report": None}

    all_findings = (
        state.get("security_findings", [])
        + state.get("logic_findings", [])
        + state.get("test_findings", [])
    )

    structured_llm = llm_strong.with_structured_output(ReviewReport)
    chain = SYNTH_PROMPT | structured_llm

    try:
        report = await chain.ainvoke({
            "pr_url": state["pr_url"],
            "findings": str(all_findings),
        })
        return {
            "final_report": report.model_dump(),
            "retry_count": state.get("retry_count", 0),
        }
    except Exception as e:
        logger.error("synthesis_failed", error=str(e))
        return {"final_report": None, "retry_count": state.get("retry_count", 0)}
