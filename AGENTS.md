# My AI Brain Agent Harness

## Context

My AI Brain is a work assistant designed to help users remember,
retrieve, and reason over information across projects.

Project knowledge should come from connected sources and semantic
memory rather than assumptions made by the language model.

Long-term project knowledge is stored in semantic memory after
documents are chunked and embedded. Short-term conversational
context is maintained by the application.

## Tools and Memory

The agent has access to tools through MCP.

Current capabilities include:
- reading local project notes
- searching Google Docs
- reading Google Docs
- indexing Google Docs into semantic memory
- searching semantic memory

For questions about stored work information, search semantic memory
before answering.

When the user explicitly identifies a project, use that project as
metadata when searching semantic memory.

If semantic memory does not contain the requested project, the
application controller may discover matching Google Docs and index
them automatically.

Google Docs discovery searches document titles. Use a concise
identifying term such as the project or topic name rather than the
entire user question.

After new information is indexed, search semantic memory again
before answering.

Do not invent document IDs, project information, source metadata,
tool results, or work facts.

If retrieved evidence is insufficient, clearly state that there is
not enough information.

## Automation

The application controller handles deterministic workflow steps.

Current controller-managed automation:

1. Detect a semantic-memory miss for a named project.
2. Search Google Docs for that project.
3. Index discovered documents into semantic memory.
4. Return control to the agent.
5. Search semantic memory again before answering.

The LLM decides what information it needs, while predictable
workflow operations remain application-controlled when possible.

## Evaluation

A successful grounded-answer task should satisfy these criteria:

- appropriate project information was retrieved
- retrieved evidence belongs to the requested project when specified
- the final answer is supported by retrieved evidence
- unrelated project information is not mixed into the answer
- missing project facts are not invented
- insufficient evidence produces uncertainty rather than fabrication

The system should be evaluated using real end-to-end tasks.

## Constraints

Keep the architecture intentionally small.

Do not introduce additional reasoning techniques or agents unless
they solve a demonstrated problem.

Tree-of-Thought reasoning is not part of the current core workflow.
The primary problem is reliable retrieval and grounded answering,
not exploration of multiple reasoning paths.

Tree-of-Thought may be considered later for tasks that genuinely
require exploring competing solution paths, strategic planning,
backtracking, or comparing architecture alternatives under several
constraints.