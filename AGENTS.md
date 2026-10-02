# My AI Brain Agent Harness

## Context

My AI Brain is a work assistant designed to help users remember,
retrieve, and reason over information across projects.

Project knowledge should come from connected sources and semantic
memory rather than assumptions made by the language model.

Long-term project knowledge is stored in semantic memory after
documents or source files are chunked and embedded. Short-term
conversational context is maintained by the application.


## Tools and Memory

The agent has access to tools through MCP.

Current capabilities include:
- reading local project notes
- searching Google Docs
- reading Google Docs
- indexing Google Docs into semantic memory
- searching GitHub repositories for relevant files
- reading GitHub files
- indexing GitHub files into semantic memory
- searching Slack channels
- reading Slack channel history
- indexing Slack channels into semantic memory
- searching semantic memory

For questions about stored work information, search semantic memory
before answering.

When the user explicitly identifies a project, use that project as
metadata when searching semantic memory.

Normalize common forms of the same project to one stable project identity.
For example, `Project Atlas`, `project-atlas`, and `Atlas` all refer to
the project `Atlas`. Use the normalized identity consistently when
indexing and searching semantic memory.

If semantic memory does not contain enough information, select the
connected source based on the type of information needed.

For general project-knowledge questions, relevant evidence may span
multiple connected sources. When the project is known and semantic
memory does not yet contain its information, consider both Google Docs
and Slack because formal project documentation and team discussions may
contain complementary evidence.

Do not search GitHub merely because the user asks for information across
all work sources. Use GitHub when source-code or implementation evidence
is relevant and a repository mapping for that project is known.

Use Google Docs for information likely to exist in documents, such as:
- project notes
- meeting notes
- architecture documents
- decisions
- written documentation

Use GitHub for information likely to exist in source code, such as:
- implementation details
- classes or methods
- tests
- repository structure
- how an application behaves

Use Slack for information likely to exist in team conversations, such as:
- project discussions
- follow-up items
- conversational updates
- decisions discussed in channels

Slack discovery searches channel names. Use a concise project or channel
identifier likely to occur in the channel name. Channels discovered through
search_slack_channels are automatically indexed into semantic memory by the
application controller.

Google Docs discovery searches document titles. Use a concise
identifying term such as the project or topic name rather than the
entire user question.

GitHub discovery searches file paths and file names, not the contents
of source-code files.

When using search_github_files, use a concise file, class, or topic
identifier that is likely to occur in a file path.

For example, for a question about how jokes are fetched, search for
"Joke" or "RandomJokes" rather than phrases such as "fetch parse".

Use the repository mapping listed below rather than inventing a
repository name.

Files discovered through search_github_files are automatically
indexed into semantic memory by the application controller.

After new information is indexed from any source, search semantic
memory again before answering.

Do not invent document IDs, repository paths, project information,
source metadata, tool results, or work facts.

If retrieved evidence is insufficient, clearly state that there is
not enough information.


## Available Work Sources

Google Docs:
- Connected through the configured Google account.

GitHub repositories:
- jokesAPI: `nchoksi/jokesAPI`

Slack:
- Connected through the configured Slack workspace.
- Project Atlas test channel: `project-atlas`


## Automation

The application controller handles deterministic workflow steps.

Current controller-managed automation:

1. The agent searches semantic memory for relevant stored information.
2. Known project names are normalized to a stable project identity before
   semantic-memory filtering or indexing.
3. If a general project question misses semantic memory, the controller
   discovers relevant project knowledge from Google Docs and Slack so
   complementary documentation and discussion can be indexed together.
4. Google Docs search results are automatically indexed into semantic
   memory.
5. Slack channel search results are automatically indexed into semantic
   memory.
6. GitHub file search results are automatically indexed when source-code
   information is relevant and a repository mapping is known.
7. The agent searches semantic memory again after indexing.
8. The final answer is generated from retrieved evidence.

The LLM decides which source and search term are appropriate, while
predictable indexing operations remain application-controlled.


## Evaluation

A successful grounded-answer task should satisfy these criteria:

- appropriate project information was retrieved
- the correct connected source was selected for the requested information
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

## Multi-Agent Verification

My AI Brain uses two agent roles:

1. **Retrieval + Answer Agent**
   - Retrieves relevant evidence from semantic memory and connected sources.
   - Generates a draft answer grounded in the retrieved evidence.

2. **Verifier Agent**
   - Receives the original question, retrieved evidence, and draft answer.
   - Checks whether factual claims in the draft are supported by the evidence.
   - Returns `PASS` or `RETRY` with a reason.

If verification returns `RETRY`, the verifier feedback is sent back to the Retrieval + Answer Agent for revision.

The verification loop is bounded to one retry.

Do not introduce additional agents unless they solve a demonstrated problem that cannot be handled cleanly by the existing two-agent architecture.