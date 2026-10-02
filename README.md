# My AI Brain: A Second Brain for Work

My AI Brain is my capstone project for the CMU Agentic AI program.

The goal is to build an AI work assistant that helps professionals maintain context across projects, retrieve relevant project information, and answer questions grounded in their work knowledge.

The project is being developed incrementally as concepts from each course module are introduced. Each module extends the same application rather than creating a separate project.

---

## Current Architecture

As of Module 4 plus the completed source-integration increment, My AI Brain combines:

- a local Qwen3-8B LLM,
- a ReAct-style agent/controller,
- an Agent Harness defined in `AGENTS.md`,
- MCP-based tools,
- short-term conversational memory,
- semantic long-term memory,
- Google Docs / Google Drive,
- GitHub,
- Slack,
- BGE embeddings and top-k semantic retrieval.

```text
                         User
                           │
                           ▼
                  ┌─────────────────┐
                  │ Agent Controller│
                  │ + AGENTS.md     │
                  └────────┬────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Qwen3-8B   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ MCP Server  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        Google Docs      GitHub        Slack
        Google Drive    REST API      Web API
              │            │            │
              └────────────┼────────────┘
                           ▼
                    Semantic Memory
                           │
                     BGE Embeddings
                           │
                    Top-k Retrieval
                           │
                           ▼
                    Grounded Answer
```

For work-information questions, the agent searches semantic memory first.

When a project is explicitly identified, project metadata can be used to filter candidate chunks before semantic similarity ranking.

Common project-name variants are normalized to one project identity. For example:

```text
Project Atlas
project-atlas
Atlas
```

are normalized to:

```text
Atlas
```

If the requested project is not yet available in semantic memory, the controller can discover information from relevant external sources, index the retrieved information, and retry semantic retrieval.

For general project questions, Google Docs and Slack can both contribute evidence.

GitHub is treated differently because it represents source-code knowledge. The agent should search GitHub when the question is code-related and an appropriate repository mapping is known rather than searching GitHub simply because the user requests "all work sources."

The resulting project retrieval flow is:

```text
User Question
      │
      ▼
search_memory
      │
      ▼
Normalize Project Identity
      │
      ▼
Project Evidence Found?
      │
      ├── Yes
      │     │
      │     ▼
      │ Semantic Retrieval
      │     │
      │     ▼
      │ Grounded Answer
      │
      └── No
            │
            ▼
     Source Discovery
        ┌───┴───┐
        ▼       ▼
   Google Docs  Slack
        │       │
        └───┬───┘
            ▼
       Controller
        Indexing
            │
            ▼
     Chunk + Embed
            │
            ▼
     Semantic Memory
            │
            ▼
     search_memory
            │
            ▼
      Top-k Evidence
            │
            ▼
        Qwen3-8B
            │
            ▼
     Grounded Answer
```

The LLM does not directly access Google, GitHub, Slack, or the vector-memory implementation. These capabilities are exposed through MCP tools.

The application controller also handles deterministic workflow transitions such as indexing discovered sources and retrying retrieval. This keeps the LLM responsible for interpreting the request while predictable ingestion operations remain application-controlled.

---

## Module 1 - Local LLM Baseline

Module 1 established the initial local LLM application.

The first implementation used:

- Python 3.12
- Hugging Face Transformers
- PyTorch
- Qwen3-0.6B running locally
- A small synthetic project file as context

The initial flow was:

```text
User Question
   ↓
Agent
   ↓
Project Context
   ↓
Prompt
   ↓
Local LLM
   ↓
Response
```

### Module 1 Experiments

Qwen3-0.6B was tested with both standard generation and thinking mode.

For simple project questions, thinking mode produced additional reasoning but did not materially improve the answers, so standard generation was used as the baseline.

This version intentionally had no external tools, semantic retrieval, persistent memory, or multi-agent workflow.

---

## Module 2 - Agent Architecture, Memory, and MCP Tools

Module 2 extended the baseline into a tool-using agent.

The implementation focused on three concepts from the module:

1. ReAct-style reasoning and action
2. Short-term conversational memory
3. Tool use through the Model Context Protocol (MCP)

### ReAct-Style Tool Loop

The agent can decide whether it already has enough information to answer or whether it needs to use a tool.

When a tool is needed, the model produces a structured request:

```text
TOOL: <tool name>
ARGS: <JSON arguments>
```

The controller executes the requested MCP tool and returns the tool observation to the model.

The model can then call another tool or produce the final answer.

Tool execution is bounded to prevent an unlimited tool-calling loop.

### Dynamic MCP Tool Discovery

The agent does not maintain a hardcoded list of tool schemas in its controller.

At runtime, it asks the MCP server for the available tools and provides their names, descriptions, and input schemas to the LLM.

Module 2 initially introduced:

- `read_project_notes`
- `search_google_docs`
- `read_google_doc`

Additional semantic-memory and external-source tools were added in later increments.

This separates the agent's reasoning loop from the implementation of individual tools.

### Google Integration

Module 2 introduced the first real external data source.

Google Drive is used to discover documents and Google Docs is used to retrieve their contents.

```text
Agent
  │
  ▼
 MCP
  │
  ├── search_google_docs → Google Drive API
  └── read_google_doc    → Google Docs API
```

OAuth is used for authentication.

The application requests read-only access to:

- Google Docs
- Google Drive

OAuth credentials and user tokens are stored locally and excluded from Git.

### Multi-Tool Reasoning

Module 2 demonstrated that the agent could chain tools when one tool's output was required by another.

For example:

```text
User asks about Atlas
        ↓
LLM selects search_google_docs
        ↓
Drive returns matching document ID
        ↓
LLM selects read_google_doc
        ↓
Docs returns document contents
        ↓
LLM answers using retrieved evidence
```

This demonstrated the separation between:

- reasoning: deciding what information is needed,
- acting: selecting a tool,
- observation: receiving external information,
- answering: synthesizing the retrieved information.

Module 3 later evolved this flow so discovered documents can be indexed into semantic memory instead of requiring the entire document to be passed directly to the LLM for every question.

### Short-Term Memory

The application maintains a bounded conversation history.

The most recent conversation messages are included in subsequent model calls, allowing follow-up questions such as:

```text
User:
What should I discuss with the architect?

Agent:
1. Messaging solution
2. Retry handling
3. Architecture direction

User:
What was the second point you mentioned?

Agent:
The second point was retry handling.
```

The follow-up can be answered from conversation history without calling an external source again.

This provides short-term conversational memory. Semantic memory provides a separate longer-term project knowledge layer.

### Local Model Experiment

The initial Qwen3-0.6B model could answer simple questions but was not reliable enough at following the structured MCP tool-calling protocol.

The model was changed to:

```text
Qwen/Qwen3-8B
```

The larger model was substantially more reliable at selecting tools, supplying arguments, and continuing multi-step tool workflows.

---

## Module 3 - RAG and Semantic Memory

Module 3 extended My AI Brain with Retrieval-Augmented Generation (RAG) and semantic long-term memory.

The goal was to establish a reliable:

```text
store → retrieve → answer
```

workflow before introducing more advanced retrieval strategies.

### RAG Pipeline

```text
Project Information
       ↓
    Chunking
       ↓
   Embeddings
       ↓
Semantic Memory

User Question
       ↓
 Query Embedding
       ↓
Metadata Filtering
       ↓
Semantic Search
       ↓
Top-K Relevant Chunks
       ↓
Retrieved Context
       ↓
   Qwen3-8B
       ↓
Grounded Answer
```

The LLM therefore acts primarily as a synthesizer over retrieved project knowledge rather than being treated as the source of project memory.

### Embeddings and Retrieval

The project uses:

```text
BAAI/bge-small-en-v1.5
```

through Sentence Transformers to generate normalized embeddings.

The query and stored chunks are embedded into the same vector space. Similarity is calculated using the dot product of normalized embeddings, corresponding to cosine similarity.

The initial retrieval configuration uses:

```text
top_k = 3
```

This intentionally keeps the retrieval strategy simple while the core RAG workflow is being established.

### Chunking

Documents are split into relatively small topical chunks before embedding.

The current implementation groups related short paragraphs into larger semantic units while avoiding excessively large chunks.

The approximate chunk size is:

```text
250 characters
```

This is a simple initial strategy and can be refined later if retrieval evaluation shows that different chunk boundaries perform better.

### Metadata-Aware Retrieval

Indexed chunks can carry metadata such as:

- project
- source
- source type
- document ID
- modification time
- repository
- file path
- Git SHA
- Slack channel ID
- Slack channel name

When the user explicitly identifies a project, the retriever can filter candidate chunks by project before semantic similarity ranking.

Project filtering was added after testing showed an important limitation of similarity-only retrieval: unrelated information can receive a similarity score close to or even above the correct project information.

The current design therefore does not rely on an arbitrary global similarity threshold.

### Controller-Managed Source Discovery

The application uses the LLM for decisions requiring interpretation while the controller handles deterministic workflow transitions.

If semantic memory has no information for a named project, the controller can discover relevant external sources, index them, and retry retrieval.

This behavior was introduced because the local LLM could recognize that more information was needed but did not always reliably emit every required structured tool call.

Moving predictable transitions into the controller improves reliability without removing the LLM's responsibility for understanding the user's request.

---

## Module 4 - Agent Harness and Tree-of-Thought Reasoning

Module 4 introduced the concept of an **Agent Harness**: the environment surrounding the language model that provides context, tools, workflow, and evaluation expectations needed for an agent to operate reliably.

The project already had many of these components implicitly through the MCP controller, semantic memory, Google Docs integration, and tool-calling workflow. In Module 4, these responsibilities were made explicit.

### Agent Harness

An `AGENTS.md` file was introduced as the configuration and instruction layer for My AI Brain.

The harness defines:

- **Context** — the purpose and expected behavior of My AI Brain.
- **Tools** — how MCP tools and connected sources should be used.
- **Memory** — how short-term conversation memory and long-term semantic memory are used.
- **Automation** — expected workflows such as memory → source discovery → indexing → retrieval.
- **Constraints** — project facts should come from retrieved evidence rather than model assumptions.
- **Evaluation** — expected behavior for grounded answers and insufficient evidence.

`src/agent.py` loads `AGENTS.md` at runtime and includes it in the system context supplied to the local LLM.

### Tree-of-Thought Decision

Tree-of-Thought reasoning was evaluated but deliberately not added to the core workflow.

The primary challenge for My AI Brain is retrieving and grounding answers in the correct work information rather than exploring many possible reasoning paths.

Tree-of-Thought may become useful later for multi-constraint planning or design trade-off analysis, but adding it to the current retrieval workflow would increase LLM calls, latency, and complexity without addressing the primary problem.

---

## GitHub Source Integration

After Module 4, GitHub was added as another real external work source.

The integration uses the GitHub REST API behind MCP tools and keeps repository access read-only.

The current test repository is:

```text
nchoksi/jokesAPI
```

GitHub authentication is supplied through the `GITHUB_TOKEN` environment variable and propagated to the MCP subprocess. The token is never stored in source control.

The GitHub flow is:

```text
Code-related question
        ↓
search_memory
        ↓
Memory miss
        ↓
search_github_files
        ↓
Controller indexes discovered files
        ↓
Chunk + BGE embedding
        ↓
Semantic Memory
        ↓
search_memory
        ↓
Qwen3-8B
        ↓
Grounded Answer
```

GitHub discovery searches file paths and names rather than source-code contents.

Once candidate files are discovered, the controller automatically calls `index_github_file`, after which semantic retrieval searches the indexed contents.

An end-to-end test asked how the `jokesAPI` project fetches and parses jokes.

The agent discovered and indexed the relevant Java files and correctly retrieved that `RandomJokes` uses `HttpURLConnection` for HTTP GET requests, reads the response, and uses Jackson `ObjectMapper` to parse the JSON.

---

## Slack Source Integration

Slack was added as the third real external work source.

The integration is read-only and uses the Slack Web API behind MCP tools.

The current Slack tools are:

- `search_slack_channels`
- `read_slack_channel`
- `index_slack_channel`

Authentication is provided through:

```text
SLACK_BOT_TOKEN
```

The token is supplied through the environment and propagated to the MCP subprocess. It is never stored in source control.

The Slack application currently requires only read permissions for public channel discovery and history.

The ingestion flow is:

```text
Project question
      ↓
Slack channel discovery
      ↓
Matching channel
      ↓
Read channel history
      ↓
Controller indexing
      ↓
Chunk + BGE embedding
      ↓
Semantic Memory
      ↓
Semantic retrieval
```

The Slack acceptance test used a synthetic `#project-atlas` channel containing discussion about:

- Kafka viability,
- Kafka versus the existing messaging platform,
- retry limits,
- repeated event failures,
- dead-letter queue handling.

The agent successfully discovered the channel, indexed its contents, searched semantic memory, and produced an answer grounded in the Slack discussion.

---

## Cross-Source Retrieval

A major integration checkpoint was validating that My AI Brain could use information from more than one real external work source for the same project.

Project Atlas information was intentionally distributed across:

- a Google Doc containing architecture notes, and
- a Slack channel containing team discussion.

The test question was:

```text
What should I discuss with the architect about Project Atlas?
Use all relevant information available across my work sources.
```

Starting with fresh semantic memory, the observed workflow was:

```text
search_memory
      ↓
No Atlas memory
      ↓
Normalize "Project Atlas" → "Atlas"
      ↓
Discover project sources
      │
      ├── Google Docs
      │      ↓
      │  Project Atlas - Architecture Notes
      │      ↓
      │     Index
      │
      └── Slack
             ↓
        #project-atlas
             ↓
            Index
      │
      ▼
Semantic Memory
      ↓
search_memory
      ↓
Combined evidence
      ↓
Grounded Answer
```

The final answer combined overlapping and complementary information from the two sources, including:

- Kafka versus the existing messaging platform,
- retry handling,
- event-driven processing,
- the fact that the final architecture had not yet been selected.

This validates the current cross-source flow:

```text
Google Docs ─┐
             ├── MCP → Semantic Memory → Retrieval → Answer
Slack ───────┘
```

GitHub remains available independently for source-code questions but is not searched automatically for a general project question unless code context is relevant and an appropriate repository is known.

---

## MCP Tools

The MCP server currently exposes:

```text
read_project_notes

search_google_docs
read_google_doc
index_google_doc

search_memory

search_github_files
read_github_file
index_github_file

search_slack_channels
read_slack_channel
index_slack_channel
```

The agent discovers these tools dynamically at runtime.

---

## Project Structure

```text
my-ai-brain/
├── data/
│   └── project_atlas.txt
├── src/
│   ├── agent.py
│   ├── google_docs.py
│   ├── github_source.py
│   ├── slack_source.py
│   ├── llm.py
│   ├── mcp_client.py
│   ├── mcp_server.py
│   ├── rag.py
│   └── retrieval.py
├── AGENTS.md
├── .gitignore
├── README.md
└── requirements.txt
```

### `src/agent.py`

Main application and agent controller.

Responsibilities include:

- accepting user questions,
- maintaining short-term conversation history,
- loading the Agent Harness,
- dynamically discovering MCP tools,
- asking the LLM to choose between answering and tool use,
- executing requested tools,
- normalizing project identities,
- handling deterministic source-discovery transitions,
- automatically indexing discovered sources,
- feeding observations back to the model,
- bounding the tool-use loop.

### `src/llm.py`

Local model interface using Qwen3-8B through Hugging Face Transformers and PyTorch.

### `src/retrieval.py`

Semantic retrieval layer responsible for:

- loading the BGE embedding model,
- chunking text,
- generating normalized embeddings,
- storing chunks and metadata,
- filtering by project,
- calculating semantic similarity,
- returning top-k chunks.

### `src/rag.py`

RAG orchestration layer for indexing sources, retrieving relevant context, and generating grounded answers.

### `src/mcp_server.py`

MCP server exposing external-source and semantic-memory tools.

### `src/google_docs.py`

Read-only Google integration responsible for:

- OAuth authentication,
- Google Drive document discovery,
- Google Docs retrieval,
- extracting text from Google Docs responses.

### `src/github_source.py`

Read-only GitHub REST API integration responsible for:

- repository file discovery,
- retrieving source files,
- returning repository metadata needed for indexing.

### `src/slack_source.py`

Read-only Slack Web API integration responsible for:

- channel discovery,
- reading channel history,
- filtering non-content/system messages,
- returning messages for semantic indexing.

### `AGENTS.md`

Agent Harness describing source-selection rules, memory behavior, deterministic workflows, grounding expectations, and constraints.

---

## Running the Project

Create and activate a Python virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

### Google

Google integration requires a Google Cloud OAuth Desktop application with the Google Drive API and Google Docs API enabled.

Place the downloaded OAuth client configuration in the repository root as:

```text
credential-googleusercontent.json
```

The application creates:

```text
token.json
```

after OAuth authorization.

Both files are excluded from Git and must never be committed.

### GitHub

Provide the GitHub token through the environment.

For example, when using GitHub CLI:

```bash
export GITHUB_TOKEN="$(gh auth token --hostname github.com --user nchoksi)"
```

### Slack

Provide the Slack bot token through the environment:

```bash
export SLACK_BOT_TOKEN="<your bot token>"
```

Do not commit the token.

### Start the Agent

From the repository root:

```bash
python -m src.agent
```

Example cross-source query:

```text
You:
What should I discuss with the architect about Project Atlas?
Use all relevant information available across my work sources.

[Tool] search_memory

[Controller] no memory for project 'Atlas'; discovering project sources

[Controller] indexing Google Doc:
Project Atlas - Architecture Notes

[Controller] indexing Slack channel:
#project-atlas

[Tool] search_memory

My AI Brain:
Based on the retrieved information...
```

---

## Current External Sources

My AI Brain currently demonstrates three real external work-source integrations:

| Source | Discovery | Content Retrieval | Semantic Indexing |
|---|---|---|---|
| Google Docs / Drive | Document title | Google Docs API | Yes |
| GitHub | Repository file path/name | GitHub REST API | Yes |
| Slack | Channel name | Slack Web API | Yes |

Local project notes are also available as a development/test source.

Semantic memory is a derived long-term memory layer populated from these sources rather than an independent external source.

---

## Current Limitations

The current implementation is intentionally limited in scope.

- Semantic memory currently uses an in-memory vector store. Indexed embeddings are lost when the MCP server exits.
- Google Drive discovery currently searches document titles rather than performing semantic search across all Drive contents.
- GitHub discovery searches repository file paths/names rather than source-code contents.
- Slack discovery searches channel names before indexing channel history.
- Chunking uses a relatively simple size-based topical grouping strategy.
- Retrieval currently uses top-k semantic similarity without reranking, query rewriting, hybrid retrieval, or other advanced RAG techniques.
- `top_k = 3` can omit useful facts when relevant information is distributed across many chunks.
- Project identity normalization currently handles simple naming variants rather than maintaining a general project/entity registry.
- Conflict/freshness handling is conservative: the verifier uses metadata when available and escalates unresolved material conflicts rather than guessing.
- Prompt instructions alone do not guarantee that the local LLM will invoke retrieval for every work-information question. Some controller-managed workflows improve reliability, but stronger grounding enforcement remains future work.
- The current external integrations are read-only.
- GitHub is not automatically searched for arbitrary project questions unless a relevant repository is known.

These limitations are intentional. Later course modules will be evaluated individually, and only concepts that improve the core agent will be added.

---

## Development Approach

The capstone is intentionally being built incrementally.

The objective is not to add every possible tool or agent pattern. Each module adds only concepts that improve the core goal of My AI Brain: reliably remembering and retrieving work context while keeping the architecture small enough to implement, understand, and evaluate.

The project currently demonstrates the progression:

```text
Module 1
Local LLM
    ↓
Module 2
Agent + MCP + Tools + Short-Term Memory
    ↓
Module 3
RAG + Embeddings + Semantic Memory + Metadata-Aware Retrieval
    ↓
Module 4
Agent Harness + Explicit Workflow/Tool Rules
    ↓
Source Integration Checkpoint
Google Docs + GitHub + Slack + Cross-Source Retrieval
```

Tree-of-Thought reasoning was evaluated during Module 4 but intentionally excluded from the core workflow.

The next course module will be evaluated against the same principle: add architecture only where it solves a demonstrated problem in My AI Brain.

---

## Module 5 — Multi-Agent Verification with LangGraph

Module 5 extends My AI Brain with a small multi-agent workflow focused on improving the reliability of generated answers.

The architecture intentionally uses two agent roles:

1. **Retrieval + Answer Agent** — reuses the existing retrieval workflow to search semantic memory and connected sources, collect relevant evidence, and generate a grounded draft answer.
2. **Verifier Agent** — independently checks whether the draft answer is supported by the retrieved evidence.

LangGraph coordinates the workflow using shared state and conditional routing.

```text
User Question
      ↓
Retrieval + Answer Agent
      ↓
Retrieved Evidence + Draft Answer
      ↓
Verifier Agent
   /       \
 PASS      RETRY
  ↓          ↓
 END    Verifier Feedback
             ↓
       Retrieval + Answer Agent
             ↓
          Verifier

---

## Module 6 — Guardrails, Safe Fallbacks, and Evaluation

Module 6 adds reliability controls around the existing two-agent workflow without adding another agent.

The Verifier now returns one of four decisions:

- `PASS` — the draft is supported by retrieved evidence.
- `RETRY` — the evidence is usable but the draft needs one bounded revision.
- `REFUSE` — there is not enough reliable evidence for a definitive answer.
- `ESCALATE` — important evidence remains materially conflicting or ambiguous and requires human judgment.

The verifier considers source metadata such as `modified_time`, `status`, `source`, and `project` when available. Newer information is not automatically treated as correct; a conflict is resolved only when the evidence clearly establishes supersession. Otherwise the workflow escalates rather than guessing.

A deterministic no-evidence guardrail prevents work-information answers from passing verification when no retrieved evidence was captured. After the single allowed retry, another verification failure ends in a safe refusal rather than returning an unsupported draft.

Runtime output records evidence count, verifier decision, retry count, final outcome, and end-to-end latency. `src/evaluation.py` provides a lightweight structure for recording the Assignment 6 metrics: answer correctness, groundedness, retrieval quality, verifier effectiveness, fallback success, and latency.

The external integrations remain read-only, preserving the tool-access limitation from the safety plan.

```text
Retrieve + Generate
       ↓
     Verify
       ↓
     Decide
  ┌────┼───────┬──────────┐
 PASS RETRY   REFUSE    ESCALATE
  ↓     ↓       ↓           ↓
Answer Revise  Safe       Human
       once   fallback     review
```
