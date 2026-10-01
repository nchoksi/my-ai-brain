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
- searching semantic memory

For questions about stored work information, search semantic memory
before answering.

When the user explicitly identifies a project, use that project as
metadata when searching semantic memory.

If semantic memory does not contain enough information, select the
connected source based on the type of information needed.

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


## Automation

The application controller handles deterministic workflow steps.

Current controller-managed automation:

1. The agent searches semantic memory for relevant stored information.
2. If semantic memory does not contain enough information, the agent
   selects an appropriate connected source.
3. Google Docs search results are automatically indexed into semantic
   memory.
4. GitHub file search results are automatically indexed into semantic
   memory.
5. The agent searches semantic memory again after indexing.
6. The final answer is generated from retrieved evidence.

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