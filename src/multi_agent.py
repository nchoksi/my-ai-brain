import time
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
    verification_decision: Literal["PASS", "RETRY", "REFUSE", "ESCALATE", ""]
    verification_reason: str
    retry_count: int
    final_answer: str
    started_at: float


def build_multi_agent_graph(
    session: ClientSession,
    llm: LocalLLM,
):
    """
    Build the Module 6 guarded two-agent workflow.

    Retrieval/Answer -> Verifier -> Decide

    PASS      -> answer
    RETRY     -> one bounded revision -> verify again
    REFUSE    -> safe fallback
    ESCALATE  -> human-review response
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

        print(f"[Guardrail] captured evidence items: {len(result['evidence'])}")

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

        print(f"[Verifier] {result['decision']}: {result['reason']}")

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

        return {"retry_count": next_retry}

    def finalize_pass(state: WorkflowState):
        elapsed = time.perf_counter() - state["started_at"]
        print(
            f"[Outcome] PASS | retries={state['retry_count']} | "
            f"latency={elapsed:.2f}s"
        )
        return {"final_answer": state["draft_answer"]}

    def finalize_refusal(state: WorkflowState):
        elapsed = time.perf_counter() - state["started_at"]
        print(
            f"[Outcome] REFUSE | retries={state['retry_count']} | "
            f"latency={elapsed:.2f}s"
        )
        return {
            "final_answer": (
                "I don't have enough reliable evidence to give a definitive "
                "answer. " + state["verification_reason"]
            )
        }

    def finalize_escalation(state: WorkflowState):
        elapsed = time.perf_counter() - state["started_at"]
        print(
            f"[Outcome] ESCALATE | retries={state['retry_count']} | "
            f"latency={elapsed:.2f}s"
        )
        return {
            "final_answer": (
                "The available evidence is conflicting or ambiguous enough "
                "that this decision should be reviewed by a person. "
                + state["verification_reason"]
            )
        }

    def route_after_verification(state: WorkflowState):
        decision = state["verification_decision"]

        if decision == "PASS":
            return "finalize_pass"

        if decision == "ESCALATE":
            return "finalize_escalation"

        if decision == "REFUSE":
            return "finalize_refusal"

        if decision == "RETRY" and state["retry_count"] < MAX_RETRIES:
            return "prepare_retry"

        # A second verifier failure is not allowed to leak an unsupported draft.
        return "finalize_refusal"

    graph = StateGraph(WorkflowState)

    graph.add_node("retrieval_answer", retrieval_answer_agent)
    graph.add_node("verifier", verifier_agent)
    graph.add_node("prepare_retry", prepare_retry)
    graph.add_node("finalize_pass", finalize_pass)
    graph.add_node("finalize_refusal", finalize_refusal)
    graph.add_node("finalize_escalation", finalize_escalation)

    graph.add_edge(START, "retrieval_answer")
    graph.add_edge("retrieval_answer", "verifier")

    graph.add_conditional_edges(
        "verifier",
        route_after_verification,
        {
            "finalize_pass": "finalize_pass",
            "prepare_retry": "prepare_retry",
            "finalize_refusal": "finalize_refusal",
            "finalize_escalation": "finalize_escalation",
        },
    )

    graph.add_edge("prepare_retry", "retrieval_answer")
    graph.add_edge("finalize_pass", END)
    graph.add_edge("finalize_refusal", END)
    graph.add_edge("finalize_escalation", END)

    return graph.compile()


async def run_multi_agent(
    session: ClientSession,
    llm: LocalLLM,
    user_question: str,
    conversation_history: list,
) -> str:
    """Run one user turn through the guarded Module 6 workflow."""

    graph = build_multi_agent_graph(session=session, llm=llm)

    initial_state: WorkflowState = {
        "question": user_question,
        "conversation_history": conversation_history,
        "evidence": [],
        "draft_answer": "",
        "verification_decision": "",
        "verification_reason": "",
        "retry_count": 0,
        "final_answer": "",
        "started_at": time.perf_counter(),
    }

    result = await graph.ainvoke(initial_state)
    return result["final_answer"]
