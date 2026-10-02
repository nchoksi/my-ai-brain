"""Module 6 evaluation summary for My AI Brain.

This lightweight evaluation records acceptance-test results for the
reliability metrics defined in Assignment 6.

The cases below come from manually executed end-to-end tests against
the real My AI Brain workflow and connected sources.
"""

from dataclasses import asdict, dataclass
from statistics import mean


@dataclass
class EvaluationResult:
    name: str
    answer_correct: bool
    grounded: bool
    retrieval_sufficient: bool
    verifier_correct: bool
    fallback_correct: bool
    latency_seconds: float


def summarize(results: list[EvaluationResult]) -> dict:
    """Aggregate Module 6 evaluation metrics."""

    if not results:
        return {"cases": 0}

    count = len(results)

    def rate(field: str) -> float:
        return round(
            sum(bool(getattr(result, field)) for result in results) / count,
            3,
        )

    return {
        "cases": count,
        "answer_correctness": rate("answer_correct"),
        "groundedness": rate("grounded"),
        "retrieval_quality": rate("retrieval_sufficient"),
        "verifier_effectiveness": rate("verifier_correct"),
        "fallback_success": rate("fallback_correct"),
        "average_latency_seconds": round(
            mean(result.latency_seconds for result in results),
            3,
        ),
        "results": [asdict(result) for result in results],
    }


def print_report(results: list[EvaluationResult]) -> None:
    """Print a human-readable evaluation report."""

    summary = summarize(results)

    print("My AI Brain - Module 6 Evaluation")
    print("=" * 38)
    print(f"Cases:                  {summary['cases']}")
    print(f"Answer correctness:     {summary['answer_correctness']:.1%}")
    print(f"Groundedness:           {summary['groundedness']:.1%}")
    print(f"Retrieval quality:      {summary['retrieval_quality']:.1%}")
    print(f"Verifier effectiveness: {summary['verifier_effectiveness']:.1%}")
    print(f"Fallback success:       {summary['fallback_success']:.1%}")
    print(
        "Average latency:        "
        f"{summary['average_latency_seconds']:.2f}s"
    )

    print("\nCases")

    for result in results:
        print(f"\n- {result.name}")
        print(f"  grounded: {result.grounded}")
        print(f"  verifier correct: {result.verifier_correct}")
        print(f"  fallback correct: {result.fallback_correct}")
        print(f"  latency: {result.latency_seconds:.2f}s")


def main() -> None:
    # Results observed during real end-to-end Module 6 acceptance testing.
    results = [
        EvaluationResult(
            name="Project Atlas grounded architecture answer",
            answer_correct=True,
            grounded=True,
            retrieval_sufficient=True,
            verifier_correct=True,
            fallback_correct=True,
            latency_seconds=30.02,
        ),
        EvaluationResult(
            name="Project Phoenix insufficient-evidence refusal",
            answer_correct=True,
            grounded=True,
            retrieval_sufficient=False,
            verifier_correct=True,
            fallback_correct=True,
            latency_seconds=6.39,
        ),
    ]

    print_report(results)


if __name__ == "__main__":
    main()