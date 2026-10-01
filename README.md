**# My AI Brain: A Second Brain for Work**



My AI Brain is my capstone project for the CMU Agentic AI program.



The goal is to build an AI work assistant that helps professionals maintain

context across projects, retrieve relevant project information, and answer

questions grounded in their work knowledge.



The project is being developed incrementally as concepts from each course

module are introduced. Each module extends the same application rather than

creating a separate project.



\---



**## Current Architecture**



As of Module 4 plus the current source-integration increment, My AI Brain combines a local LLM, MCP-based tools, short-term conversational memory, Google Docs and GitHub integrations, and semantic long-term memory through a Retrieval-Augmented Generation (RAG) pipeline.



\`\`\`text

&#x20;                        ┌──────────────────────┐

&#x20;                        │        User          │

&#x20;                        └──────────┬───────────┘

&#x20;                                   │

&#x20;                                   ▼

&#x20;                        ┌──────────────────────┐

&#x20;                        │       Agent          │

&#x20;                        │   ReAct-style loop   │

&#x20;                        └──────────┬───────────┘

&#x20;                                   │

&#x20;                                   ▼

&#x20;                        ┌──────────────────────┐

&#x20;                        │ Local LLM            │

&#x20;                        │ Qwen3-8B             │

&#x20;                        └──────────┬───────────┘

&#x20;                                   │

&#x20;                                   ▼

&#x20;                        ┌──────────────────────┐

&#x20;                        │      MCP Tools       │

&#x20;                        └──────────┬───────────┘

&#x20;                                   │

&#x20;                  ┌────────────────┼────────────────┐

&#x20;                  │                │                │

&#x20;                  ▼                ▼                ▼

&#x20;            Local Notes       Google APIs      Semantic Memory

&#x20;                               Drive + Docs      BGE Embeddings

\`\`\`



For work-information questions, the agent searches semantic memory first.



When the user identifies a project, project metadata can be used to filter

candidate chunks before semantic similarity ranking.



If the requested project has not yet been indexed, the application can

discover the corresponding Google Doc, index it into semantic memory, and

retry retrieval.



\`\`\`text

User Question

&#x20;    ↓

search_memory

&#x20;    ↓

Project Metadata Filter

&#x20;    ↓

Semantic Retrieval

&#x20;    │

&#x20;    ├── Relevant evidence found

&#x20;    │          ↓

&#x20;    │      Local LLM

&#x20;    │          ↓

&#x20;    │    Grounded Answer

&#x20;    │

&#x20;    └── Project not in memory

&#x20;               ↓

&#x20;        Google Docs Search

&#x20;               ↓

&#x20;        Document Discovery

&#x20;               ↓

&#x20;       Chunk + Embed + Index

&#x20;               ↓

&#x20;         Semantic Memory

&#x20;               ↓

&#x20;        search_memory again

&#x20;               ↓

&#x20;           Local LLM

&#x20;               ↓

&#x20;        Grounded Answer

\`\`\`



The LLM does not directly access Google APIs or the vector memory

implementation. These capabilities are exposed through MCP tools.



The application controller also handles deterministic workflow steps such as

automatically indexing a discovered Google Doc. This keeps the LLM focused on

deciding what information is needed while predictable ingestion operations

remain application-controlled.



\---



**## Module 1 - Local LLM Baseline**



Module 1 established the initial local LLM application.



The first implementation used:



\- Python 3.12

\- Hugging Face Transformers

\- PyTorch

\- Qwen3-0.6B running locally

\- A small synthetic project file as context



The initial flow was:



\`\`\`text

User Question

&#x20;   ↓

Agent

&#x20;   ↓

Project Context

&#x20;   ↓

Prompt

&#x20;   ↓

Local LLM

&#x20;   ↓

Response

\`\`\`



**### Module 1 Experiments**



Qwen3-0.6B was tested with both standard generation and thinking mode.



For simple project questions, thinking mode produced additional reasoning but

did not materially improve the answers, so standard generation was used as

the baseline.



This version intentionally had no external tools, semantic retrieval,

persistent memory, or multi-agent workflow.



\---



**## Module 2 - Agent Architecture, Memory, and MCP Tools**



Module 2 extended the baseline into a tool-using agent.



The implementation focused on three concepts from the module:



1\. ReAct-style reasoning and action

2\. Short-term conversational memory

3\. Tool use through the Model Context Protocol (MCP)



**### ReAct-Style Tool Loop**



The agent can decide whether it already has enough information to answer or

whether it needs to use a tool.



When a tool is needed, the model produces a structured request:



\`\`\`text

TOOL: \<tool name>

ARGS: \<JSON arguments>

\`\`\`



The controller executes the requested MCP tool and returns the tool observation

to the model.



The model can then:



\- call another tool, or

\- produce the final answer.



Tool execution is bounded to prevent an unlimited tool-calling loop.



**### Dynamic MCP Tool Discovery**



The agent does not maintain a hardcoded list of tool schemas in its controller.



At runtime, it asks the MCP server for the available tools and provides their

names, descriptions, and input schemas to the LLM.



Module 2 initially introduced:



\- \`read_project_notes\`

\- \`search_google_docs\`

\- \`read_google_doc\`



Additional semantic-memory tools were added in Module 3.



This separates the agent's reasoning loop from the implementation of individual

tools.



**### Google Integration**



Module 2 introduced the first real external data source.



Google Drive is used to discover documents and Google Docs is used to retrieve

their contents.



\`\`\`text

Agent

&#x20; ↓

MCP

&#x20; ├── search_google_docs → Google Drive API

&#x20; └── read_google_doc    → Google Docs API

\`\`\`



OAuth is used for authentication.



The application requests read-only access to:



\- Google Docs

\- Google Drive



OAuth credentials and user tokens are stored locally and excluded from Git.



**### Multi-Tool Reasoning**



Module 2 demonstrated that the agent could chain tools when one tool's output

was required by another.



For example:



\`\`\`text

User asks about Atlas

&#x20;       ↓

LLM selects search_google_docs

&#x20;       ↓

Drive returns matching document ID

&#x20;       ↓

LLM selects read_google_doc

&#x20;       ↓

Docs returns document contents

&#x20;       ↓

LLM answers using retrieved evidence

\`\`\`



This demonstrated the separation between:



\- reasoning: deciding what information is needed

\- acting: selecting a tool

\- observation: receiving external information

\- answering: synthesizing the retrieved information



Module 3 later evolved this flow so discovered documents can be indexed into

semantic memory instead of requiring the entire document to be passed directly

to the LLM for every question.



**### Short-Term Memory**



The application maintains a bounded conversation history.



The most recent conversation messages are included in subsequent model calls,

allowing follow-up questions such as:



\`\`\`text

User:

What should I discuss with the architect?



Agent:

1\. Messaging solution

2\. Retry handling

3\. Architecture direction



User:

What was the second point you mentioned?



Agent:

The second point was retry handling.

\`\`\`



The follow-up can be answered from conversation history without calling Google

again.



This provides short-term conversational memory. Module 3 adds a separate

semantic-memory layer for longer-lived project knowledge.



**### Local Model Experiment**



The initial Qwen3-0.6B model could answer simple questions but was not reliable

enough at following the structured MCP tool-calling protocol.



The model was changed to:



\`\`\`text

Qwen/Qwen3-8B

\`\`\`



The larger model was substantially more reliable at selecting tools, supplying

arguments, and continuing multi-step tool workflows.



\---



**## Module 3 - RAG and Semantic Memory**



Module 3 extends My AI Brain with Retrieval-Augmented Generation (RAG) and

semantic long-term memory.



The goal of this module is to establish a reliable:



\`\`\`text

store → retrieve → answer

\`\`\`



workflow before introducing more advanced retrieval strategies.



**### RAG Pipeline**



The core retrieval pipeline is:



\`\`\`text

Project Information

&#x20;       ↓

&#x20;    Chunking

&#x20;       ↓

&#x20;   Embeddings

&#x20;       ↓

&#x20;Semantic Memory





User Question

&#x20;       ↓

&#x20; Query Embedding

&#x20;       ↓

Metadata Filtering

&#x20;       ↓

&#x20;Semantic Search

&#x20;       ↓

Top-K Relevant Chunks

&#x20;       ↓

Retrieved Context

&#x20;       ↓

&#x20;   Qwen3-8B

&#x20;       ↓

&#x20;Grounded Answer

\`\`\`



The LLM therefore acts primarily as a synthesizer over retrieved project

knowledge rather than being treated as the source of project memory.



**### Embeddings and Retrieval**



The project uses:



\`\`\`text

BAAI/bge-small-en-v1.5

\`\`\`



through Sentence Transformers to generate normalized embeddings.



The query and stored chunks are embedded into the same vector space.

Similarity is calculated using the dot product of normalized embeddings,

which corresponds to cosine similarity.



The initial retrieval configuration uses:



\`\`\`text

top_k = 3

\`\`\`



This intentionally keeps the retrieval strategy simple while the core RAG

workflow is being established.



**### Chunking**



Documents are split into relatively small topical chunks before embedding.



During testing, paragraph-level chunking produced overly fragmented Google Docs

content. Increasing the chunk size too far produced a single large chunk.



The current implementation groups related short paragraphs into larger

semantic units while avoiding excessively large chunks.



The current approximate chunk size is:



\`\`\`text

250 characters

\`\`\`



This is a simple initial strategy and can be refined later if retrieval

evaluation shows that different chunk boundaries perform better.



**### Metadata-Aware Retrieval**



Each indexed chunk can carry metadata such as:



\- project

\- source

\- document ID

\- source type

\- modification time



Metadata is stored alongside the text and embedding.



When the user explicitly identifies a project, the retriever can filter

candidate chunks by project before semantic similarity ranking.



For example:



\`\`\`text

Question:

"What should I discuss with the architect about Atlas?"



&#x20;       ↓



project = "Atlas"



&#x20;       ↓



Filter semantic memory to Atlas



&#x20;       ↓



Rank Atlas chunks by semantic similarity

\`\`\`



This was added after testing showed an important limitation of similarity-only

retrieval: an unrelated document could receive a similarity score very close

to or even slightly above the correct project document.



Project filtering reduces this type of cross-project retrieval error.



**### Google Docs → Semantic Memory**



Google Docs can now be:



1\. discovered through the Google Drive API,

2\. read through the Google Docs API,

3\. split into topical chunks,

4\. embedded,

5\. indexed into semantic memory,

6\. retrieved using semantic similarity.



This connects the external knowledge source introduced in Module 2 to the RAG

pipeline introduced in Module 3.



**### Controller-Managed Source Discovery**



The application uses the LLM for decisions that require interpretation, while

the controller handles deterministic workflow transitions.



For example, if the agent searches semantic memory for a named project and no

information exists for that project:



\`\`\`text

search_memory(project="Atlas")

&#x20;       ↓

Memory Miss

&#x20;       ↓

Controller

&#x20;       ↓

search_google_docs("Atlas")

&#x20;       ↓

Google Drive

&#x20;       ↓

Matching document

&#x20;       ↓

index_google_doc

&#x20;       ↓

Semantic Memory

&#x20;       ↓

search_memory(project="Atlas")

\`\`\`



This behavior was introduced because the local LLM could correctly recognize

that it needed to search Google Docs after a memory miss but did not always

emit the required structured tool call.



Moving this predictable transition into the controller makes the workflow more

reliable without removing the LLM's responsibility for understanding the

user's request.



**### MCP Semantic Memory Tools**



Module 3 adds two MCP tools:



\- \`index_google_doc\` — loads a Google Doc, chunks it, embeds the chunks, and

&#x20; stores them in semantic memory.

\- \`search_memory\` — performs semantic top-k retrieval over indexed knowledge

&#x20; and optionally filters retrieval by project.



The MCP server now exposes:



\- \`read_project_notes\`

\- \`search_google_docs\`

\- \`read_google_doc\`

\- \`index_google_doc\`

\- \`search_memory\`



This allows My AI Brain to access external source systems and semantic memory

through the same MCP interface.



**### Module 3 End-to-End Example**



Given:



\`\`\`text

What should I discuss with the architect about Atlas?

\`\`\`



the agent can perform:



\`\`\`text

search_memory(

&#x20;   query="what should I discuss with the architect?",

&#x20;   project="Atlas"

)

&#x20;       ↓

Atlas not currently indexed

&#x20;       ↓

Controller searches Google Docs for "Atlas"

&#x20;       ↓

Project Atlas - Architecture Notes

&#x20;       ↓

Document is chunked and embedded

&#x20;       ↓

Chunks stored with project="Atlas"

&#x20;       ↓

search_memory(... project="Atlas")

&#x20;       ↓

Relevant Atlas chunks retrieved

&#x20;       ↓

Qwen3-8B

&#x20;       ↓

Grounded answer

\`\`\`



A second document was also tested in the same running session using a different

topic. Project metadata kept retrieval scoped to the appropriate information

instead of mixing unrelated chunks.



**### RAG Failure Analysis**



During development, retrieval scores were compared across relevant and

irrelevant documents.



The experiment showed that a single global cosine-similarity threshold would

not reliably separate correct from incorrect evidence. In one test, an

unrelated chunk received nearly the same score as the correct Atlas chunk.



For this reason, the current design does not rely on an arbitrary global

similarity cutoff.



Instead, when the user provides an explicit project identifier, metadata

filtering is applied before semantic ranking.



This keeps the retrieval strategy simple while addressing the specific failure

observed during testing.



\---



**## Project Structure**



\`\`\`text

my-ai-brain/

├── data/

│   └── project_atlas.txt

├── src/

│   ├── agent.py

│   ├── google_docs.py

│   ├── github_source.py

│   ├── llm.py

│   ├── mcp_client.py

│   ├── mcp_server.py

│   ├── rag.py

│   └── retrieval.py

├── .gitignore

├── README.md

└── requirements.txt

\`\`\`



**### \`src/agent.py\`**



Main application and agent controller.



Responsibilities include:



\- accepting user questions

\- maintaining short-term conversation history

\- discovering MCP tools

\- asking the LLM to choose between answering and tool use

\- executing requested tools

\- handling deterministic source-discovery transitions

\- feeding tool observations back to the model

\- bounding the tool-use loop



**### \`src/llm.py\`**



Local model interface.



The current implementation uses Qwen3-8B through Hugging Face Transformers and

PyTorch.



**### \`src/retrieval.py\`**



Semantic retrieval layer.



Responsibilities include:



\- loading the embedding model

\- chunking text

\- generating normalized embeddings

\- storing chunks and metadata

\- filtering by project metadata

\- calculating semantic similarity

\- returning top-k relevant chunks



**### \`src/rag.py\`**



RAG orchestration layer for indexing sources, retrieving relevant context, and

generating grounded answers.



**### \`src/mcp_server.py\`**



MCP server exposing external-source and semantic-memory tools to the agent.



**### \`src/google_docs.py\`**



Google integration layer.



Responsibilities include:



\- OAuth authentication

\- Google Drive document search

\- Google Docs retrieval

\- extraction of text from Google Docs responses



**### \`data/project_atlas.txt\`**



Synthetic project information used during development and for the local

\`read_project_notes\` MCP tool.



\---



**## Running the Project**



Create and activate a Python virtual environment.



Install dependencies:



\`\`\`bash

pip install -r requirements.txt

\`\`\`



Google integration requires a Google Cloud OAuth Desktop application with both

the Google Drive API and Google Docs API enabled.



Place the downloaded OAuth client configuration in the repository root as:



\`\`\`text

credential-googleusercontent.json

\`\`\`



The application creates:



\`\`\`text

token.json

\`\`\`



after OAuth authorization.



Both files are excluded from Git and must never be committed.



Run the agent from the repository root:



\`\`\`bash

python -m src.agent

\`\`\`



Example:



\`\`\`text

You: what should i discuss with architect about atlas?



[Tool] search_memory

[Controller] no memory for project 'Atlas', searching Google Docs

[Controller] indexing Google Doc: Project Atlas - Architecture Notes

[Tool] search_memory



My AI Brain: Based on the information retrieved...

\`\`\`



\---



**## Current Limitations**



The current implementation is intentionally limited in scope.



\- Semantic memory currently uses an in-memory vector store. Indexed embeddings

&#x20; are lost when the MCP server exits.

\- Google Drive discovery currently searches document titles rather than

&#x20; performing semantic search across Google Drive contents.

\- The current project/topic metadata is intentionally simple and is inferred

&#x20; from the identifying term used during document discovery.

\- Chunking uses a simple size-based topical grouping strategy.

\- Retrieval does not yet include reranking, query rewriting, hybrid search, or

&#x20; other advanced RAG techniques.

\- Retrieved information is not yet independently verified by a separate agent.

\- Conflicting or outdated information is not yet automatically resolved.

\- There is not yet a multi-agent workflow.

\- Google Docs and GitHub are currently connected as real external knowledge sources.

\- Slack integration has not yet been implemented.

\- Tool routing still depends partly on the local LLM correctly interpreting

&#x20; available MCP tools.



These limitations are intentional. Later course modules will be evaluated

individually and only the concepts that improve the core agent will be added.



\---



**## Development Approach**



The capstone is intentionally being built incrementally.



The objective is not to add every possible tool or agent pattern. Each module

adds only the concepts that improve the core goal of My AI Brain: reliably

remembering and retrieving work context while keeping the architecture small

enough to implement, understand, and evaluate.



The project currently demonstrates the progression from:



\`\`\`text

Module 1

Local LLM

&#x20;   ↓

Module 2

Agent + MCP + Tools + Short-Term Memory

&#x20;   ↓

Module 3

RAG + Embeddings + Semantic Memory + Metadata-Aware Retrieval

\`\`\`



Future modules will extend this architecture only where the additional

capability is justified by the problem being solved.





**## Module 4 — Agent Harness and Tree-of-Thought Reasoning**



Module 4 introduced the concept of an **\*\*Agent Harness\*\***: the environment surrounding the language model that provides the context, tools, workflow, and evaluation expectations needed for an agent to operate reliably.



The project already had many of these components implicitly through the MCP controller, semantic memory, Google Docs integration, and tool-calling workflow. In Module 4, these responsibilities were made more explicit.



**### Agent Harness**



An \`AGENTS.md\` file was introduced as the configuration and instruction layer for My AI Brain.



The harness defines:



\- **\*\*Context\*\*** — the purpose and behavior of My AI Brain.

\- **\*\*Tools\*\*** — how MCP tools and connected sources should be used.

\- **\*\*Memory\*\*** — how short-term conversation memory and long-term semantic memory are used.

\- **\*\*Automation\*\*** — expected workflows such as memory → source discovery → indexing → retrieval.

\- **\*\*Constraints\*\*** — project facts should come from retrieved evidence rather than model assumptions.

\- **\*\*Evaluation\*\*** — expected behavior for grounded answers and insufficient evidence.



\`src/agent.py\` loads \`AGENTS.md\` at runtime and includes it in the system context supplied to the local LLM.



\`\`\`text

User

&#x20; |

&#x20; v

Agent Controller

&#x20; |

&#x20; +---- AGENTS.md

&#x20; \|       |

&#x20; \|       +-- Context

&#x20; \|       +-- Tools

&#x20; \|       +-- Memory rules

&#x20; \|       +-- Workflow

&#x20; \|       +-- Constraints

&#x20; \|       +-- Evaluation expectations

&#x20; |

&#x20; +---- Local LLM

&#x20; |

&#x20; +---- MCP Tools

&#x20;          |

&#x20;          +-- Semantic Memory

&#x20;          +-- Google Docs

---

## GitHub Source Integration

After Module 4, GitHub was added as the second real external work source. The integration uses the GitHub REST API behind MCP tools and keeps repository access read-only.

The current configured repository is `nchoksi/jokesAPI`. GitHub authentication is supplied through the `GITHUB_TOKEN` environment variable and is propagated to the MCP subprocess; the token is never stored in source control.

The implemented flow is:

```text
User question about source code
        ↓
search_memory
        ↓
Memory miss
        ↓
search_github_files
        ↓
Controller indexes discovered GitHub files
        ↓
Chunk + BGE embedding + semantic memory
        ↓
search_memory
        ↓
Qwen3-8B
        ↓
Grounded answer
```

GitHub discovery searches file paths and names rather than source-code contents. Once candidate files are discovered, the controller automatically calls `index_github_file`; semantic retrieval then searches the indexed contents. This mirrors the controller-managed ingestion pattern already used for Google Docs.

An end-to-end test asked how the `jokesAPI` project fetches and parses jokes. The agent searched semantic memory, discovered relevant GitHub files, automatically indexed the Java source and tests, searched semantic memory again, and produced an answer grounded in `RandomJokes.java`.

The test also exposed a remaining grounding limitation: prompt instructions alone do not guarantee that Qwen will invoke retrieval for every work-related question. For example, a later Atlas question was answered generically without a tool call. This is retained as an explicit reliability issue to address through later guardrail/evaluation work rather than being hidden by source-specific routing hacks.

### GitHub Authentication

Before starting the agent, provide a GitHub token in the environment. For example, when using GitHub CLI with the configured account:

```bash
export GITHUB_TOKEN="$(gh auth token --hostname github.com --user nchoksi)"
python -m src.agent
```

Do not commit GitHub tokens or other credentials.

### Current External Sources

- Google Docs / Google Drive — document discovery and document content.
- GitHub — repository file discovery and source-code content.
- Local project notes — development/test source.
- Semantic memory — derived long-term memory populated from connected sources.

Slack is planned as the next external source before the Module 5 implementation work begins.
