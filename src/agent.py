from pathlib import Path

from llm import LocalLLM


PROJECT_FILE = Path("data/project_atlas.txt")

SYSTEM_PROMPT = """
You are My AI Brain, a work assistant.

Answer questions using only the project information provided to you.

If the project information does not contain enough evidence to answer
the question, clearly say that the information is not available.

Do not invent project decisions, people, dates, or technical details.
""".strip()


def load_project_context() -> str:
    return PROJECT_FILE.read_text()

def main():
    project_context = load_project_context()

    llm = LocalLLM()

    print("\nMy AI Brain - Module 1")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()

        if not question:
            continue

        if question.lower() == "exit":
            break

        user_prompt = f"""
PROJECT INFORMATION:
{project_context}
USER QUESTION:
{question}
""".strip()

        answer = llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        print(f"\nMy AI Brain: {answer}\n")

if __name__ == "__main__":
    main()