from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import ClientSession

from src.agent import run_agent
from src.llm import LocalLLM
from src.verifier import verify_answer


MAX_RETRIES = 1


class WorkflowState(TypedDict):
    question: str
    conversation_history: list
    evidence: list[dict]
    draft_answer: str
    verification_decision: Literal["PASS", "RETRY", ""]
    verification_reason: str
    retry_count: int
    final_answer: str


def build_multi_agent_graph(
    session: ClientSession,
    llm: LocalLLM,
):
    """
    Build the Module 5 two-agent workflow.

    Retrieval/Answer Agent -> Verifier Agent -> PASS/RETRY

    If verification fails, the verifier's feedback is sent back to the
    Retrieval/Answer Agent for one bounded revision attempt.
    """

    async def retrieval_answer_agent(state: WorkflowState):
        print("[Agent] Retrieval/Answer")

        revision_feedback = ""
        if state["retry_count"] > 0:
            revision_feedback = state["verification_reason"]

        result = await run_agent(
            session=session,
            llm=llm,
            user_question=state["question"],
            conversation_history=state["conversation_history"],
            revision_feedback=revision_feedback,
            return_details=True,
        )

        return {
            "draft_answer": result["answer"],
            "evidence": result["evidence"],
        }

    def verifier_agent(state: WorkflowState):
        print("[Agent] Verifier")

        result = verify_answer(
            llm=llm,
            question=state["question"],
            evidence=state["evidence"],
            draft_answer=state["draft_answer"],
        )

        print(
            f"[Verifier] {result['decision']}: "
            f"{result['reason']}"
        )

        return {
            "verification_decision": result["decision"],
            "verification_reason": result["reason"],
        }

    def prepare_retry(state: WorkflowState):
        next_retry = state["retry_count"] + 1

        print(
            f"[Workflow] verifier requested revision; "
            f"retry {next_retry}/{MAX_RETRIES}"
        )

        return {
            "retry_count": next_retry,
        }

    def finalize_agent(state: WorkflowState):
        return {
            "final_answer": state["draft_answer"],
        }

    def route_after_verification(state: WorkflowState):
        if state["verification_decision"] == "PASS":
            return "finalize"

        if state["retry_count"] < MAX_RETRIES:
            return "prepare_retry"

        return "finalize"

    graph = StateGraph(WorkflowState)

    graph.add_node(
        "retrieval_answer",
        retrieval_answer_agent,
    )
    graph.add_node(
        "verifier",
        verifier_agent,
    )
    graph.add_node(
        "prepare_retry",
        prepare_retry,
    )
    graph.add_node(
        "finalize",
        finalize_agent,
    )

    graph.add_edge(
        START,
        "retrieval_answer",
    )
    graph.add_edge(
        "retrieval_answer",
        "verifier",
    )

    graph.add_conditional_edges(
        "verifier",
        route_after_verification,
        {
            "finalize": "finalize",
            "prepare_retry": "prepare_retry",
        },
    )

    graph.add_edge(
        "prepare_retry",
        "retrieval_answer",
    )
    graph.add_edge(
        "finalize",
        END,
    )

    return graph.compile()


async def run_multi_agent(
    session: ClientSession,
    llm: LocalLLM,
    user_question: str,
    conversation_history: list,
) -> str:
    """
    Run one user turn through the Module 5 multi-agent workflow.
    """

    graph = build_multi_agent_graph(
        session=session,
        llm=llm,
    )

    initial_state: WorkflowState = {
        "question": user_question,
        "conversation_history": conversation_history,
        "evidence": [],
        "draft_answer": "",
        "verification_decision": "",
        "verification_reason": "",
        "retry_count": 0,
        "final_answer": "",
    }

    result = await graph.ainvoke(initial_state)

    return result["final_answer"]
