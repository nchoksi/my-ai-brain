import json
import re

from src.llm import LocalLLM


VERIFIER_SYSTEM_PROMPT = """
You are the Verifier Agent for My AI Brain.

Your job is to independently check whether a draft answer is supported by the
retrieved evidence supplied to you and choose the safest next action.

Rules:
- Treat the retrieved evidence as the only source of truth for work facts.
- Do not add facts from your own knowledge.
- Consider source metadata such as modified_time, source, project, and status
  when it is present.
- If two pieces of evidence conflict and one clearly supersedes the other based
  on explicit status or reliable freshness metadata, prefer the superseding
  evidence and explain why.
- Do not assume that a newer timestamp automatically changes an older decision;
  only resolve a conflict when the evidence makes the supersession clear.
- PASS when the material claims in the draft are supported by the evidence.
- RETRY when the evidence is usable but the draft invents facts, overstates the
  evidence, contradicts it, or claims certainty that it does not support.
- REFUSE when there is not enough evidence to provide a reliable work answer,
  including after a bounded retry cannot repair the answer.
- ESCALATE when evidence for an important decision remains materially
  conflicting or ambiguous and choosing one version requires human judgment.
- Do not reject a draft merely because wording differs from the evidence.

Return JSON only in this exact shape:
{
  "decision": "PASS" or "RETRY" or "REFUSE" or "ESCALATE",
  "reason": "short explanation"
}
""".strip()


def _extract_json(text: str) -> dict:
    """Parse the verifier's small structured response defensively."""

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {
                "decision": "REFUSE",
                "reason": "Verifier did not return a valid structured decision.",
            }

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {
                "decision": "REFUSE",
                "reason": "Verifier returned malformed JSON.",
            }


def verify_answer(
    llm: LocalLLM,
    question: str,
    evidence: list[dict],
    draft_answer: str,
) -> dict:
    """Verify grounding and select PASS, RETRY, REFUSE, or ESCALATE."""

    # Deterministic guardrail: a work answer with no captured evidence should
    # never be accepted merely because the model sounds confident.
    if not evidence:
        return {
            "decision": "REFUSE",
            "reason": "No retrieved evidence was captured for this work-information answer.",
        }

    evidence_text = json.dumps(evidence, indent=2, ensure_ascii=False)

    user_prompt = f"""
Original question:
{question}

Retrieved evidence:
{evidence_text}

Draft answer:
{draft_answer}

Check whether the draft is grounded in the retrieved evidence. Also check for
materially conflicting or ambiguous evidence, using freshness/status metadata
only when it clearly establishes which information supersedes another.
""".strip()

    raw = llm.generate(
        system_prompt=VERIFIER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    result = _extract_json(raw)
    decision = str(result.get("decision", "REFUSE")).upper()

    if decision not in {"PASS", "RETRY", "REFUSE", "ESCALATE"}:
        decision = "REFUSE"

    return {
        "decision": decision,
        "reason": str(result.get("reason", "No reason provided.")),
    }
