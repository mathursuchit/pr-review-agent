import structlog
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agent.models import Finding
from agent.state import ReviewState

logger = structlog.get_logger()

# Cheap model for per-category analysis, strong model reserved for synthesis
llm_fast = ChatOpenAI(model="gpt-4o-mini", temperature=0)

SECURITY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a security-focused code reviewer. Analyze the PR diff for vulnerabilities: "
        "injection flaws, hardcoded credentials, insecure dependencies, auth bypasses, SSRF, etc. "
        "Return an empty list if no issues found. Do not hallucinate file paths.",
    ),
    ("human", "<diff>\n{diff}\n</diff>"),
])

LOGIC_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a code reviewer focused on correctness. Identify logic errors, off-by-one bugs, "
        "unhandled edge cases, race conditions, and incorrect assumptions. "
        "Return an empty list if no issues found.",
    ),
    ("human", "<diff>\n{diff}\n</diff>"),
])

TEST_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a code reviewer focused on test quality. Identify missing tests, untested branches, "
        "and cases where the diff adds behavior but no corresponding tests. "
        "Return an empty list if coverage is adequate.",
    ),
    ("human", "<diff>\n{diff}\n</diff>"),
])


async def _run_analysis(prompt: ChatPromptTemplate, diff: str, category: str) -> list[dict]:
    structured_llm = llm_fast.with_structured_output(list[Finding])
    chain = prompt | structured_llm
    try:
        findings = await chain.ainvoke({"diff": diff})
        return [f.model_dump() for f in findings]
    except Exception as e:
        logger.error("analysis_failed", category=category, error=str(e))
        return []


async def security(state: ReviewState) -> dict:
    if state.get("error") or not state.get("raw_diff"):
        return {"security_findings": []}
    findings = await _run_analysis(SECURITY_PROMPT, state["raw_diff"], "security")
    return {"security_findings": findings}


async def logic(state: ReviewState) -> dict:
    if state.get("error") or not state.get("raw_diff"):
        return {"logic_findings": []}
    findings = await _run_analysis(LOGIC_PROMPT, state["raw_diff"], "logic")
    return {"logic_findings": findings}


async def tests(state: ReviewState) -> dict:
    if state.get("error") or not state.get("raw_diff"):
        return {"test_findings": []}
    findings = await _run_analysis(TEST_PROMPT, state["raw_diff"], "test-coverage")
    return {"test_findings": findings}
