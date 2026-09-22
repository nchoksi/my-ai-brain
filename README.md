# My AI Brain: A Second Brain for Work

My AI Brain is my capstone project for the CMU Agentic AI program.

The goal is to build an AI work assistant that helps professionals maintain
context across projects, retrieve relevant project information, and answer
questions grounded in their work knowledge.

The project is being developed incrementally as concepts from each course
module are introduced. Each module extends the same application rather than
creating a separate project.

---

## Current Architecture

As of Module 2, My AI Brain runs a local LLM that can reason about a user's
request, discover available tools through MCP, call those tools when external
information is needed, and maintain short-term conversational context.

```text
                         ┌──────────────────────┐
                         │        User          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Agent          │
                         │   (ReAct-style loop) │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Local LLM            │
                         │ Qwen3-8B             │
                         └──────────┬───────────┘
                                    │
                         Need external context?
                           │                │
                          Yes               No
                           │                │
                           ▼                ▼
                    ┌─────────────┐      Answer
                    │ MCP Tools   │
                    └──────┬──────┘
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
        Local Project   Google Drive   Google Docs
           Notes           Search         Reader
```

The LLM does not directly access Google APIs. It selects an MCP tool, the
application executes that tool, and the resulting observation is returned to
the LLM so it can continue reasoning.

This allows a single request to involve multiple tool calls.

For example:

```text
"Find the Google Doc for Atlas and tell me what I should
 discuss with the architect."

        ↓
search_google_docs("Atlas")
        ↓
Google Drive returns document metadata + document ID
        ↓
read_google_doc(document_id)
        ↓
Google Docs returns document contents
        ↓
Qwen3-8B generates an answer grounded in the retrieved document
```

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

For simple project questions, thinking mode produced additional reasoning but
did not materially improve the answers, so standard generation was used as the
baseline.

This version intentionally had no external tools, semantic retrieval,
persistent memory, or multi-agent workflow.

---

## Module 2 - Agent Architecture, Memory, and MCP Tools

Module 2 extends the baseline into a tool-using agent.

The implementation focuses on three concepts from the module:

1. ReAct-style reasoning and action
2. Short-term conversational memory
3. Tool use through the Model Context Protocol (MCP)

### ReAct-Style Tool Loop

The agent can decide whether it already has enough information to answer or
whether it needs to use a tool.

When a tool is needed, the model produces a structured request:

```text
TOOL: <tool name>
ARGS: <JSON arguments>
```

The controller executes the requested MCP tool and returns the tool observation
to the model.

The model can then:

- call another tool, or
- produce the final answer.

Tool execution is bounded to prevent an unlimited tool-calling loop.

### Dynamic MCP Tool Discovery

The agent does not maintain a hardcoded list of tool schemas in its controller.

At runtime, it asks the MCP server for the available tools and provides their
names, descriptions, and input schemas to the LLM.

Current MCP tools include:

- `read_project_notes`
- `search_google_docs`
- `read_google_doc`

This separates the agent's reasoning loop from the implementation of individual
tools.

### Google Integration

Module 2 introduces the first real external data source.

Google Drive is used to discover documents and Google Docs is used to retrieve
their contents.

```text
Agent
  ↓
MCP
  ├── search_google_docs → Google Drive API
  └── read_google_doc    → Google Docs API
```

OAuth is used for authentication.

The application requests read-only access:

- Google Docs read-only
- Google Drive read-only

OAuth credentials and user tokens are stored locally and are excluded from Git.

### Multi-Tool Reasoning

The agent can chain tools when one tool's output is required by another.

For example, the user does not need to know a Google document ID:

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

This demonstrates the separation between:

- reasoning: deciding what information is needed
- acting: selecting a tool
- observation: receiving external information
- answering: synthesizing the retrieved information

### Short-Term Memory

The application maintains a bounded conversation history.

The most recent conversation messages are included in subsequent model calls,
allowing follow-up questions such as:

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

The follow-up can be answered from conversation history without calling Google
again.

This is intentionally short-term memory only. Persistent long-term memory and
semantic retrieval are not implemented yet.

---

## Project Structure

```text
my-ai-brain/
├── data/
│   └── project_atlas.txt
├── src/
│   ├── agent.py
│   ├── google_docs.py
│   ├── llm.py
│   ├── mcp_client.py
│   └── mcp_server.py
├── .gitignore
├── README.md
└── requirements.txt
```

### `src/agent.py`

Main application and agent controller.

Responsibilities include:

- accepting user questions
- maintaining short-term conversation history
- discovering MCP tools
- asking the LLM to choose between answering and tool use
- executing requested tools
- feeding tool observations back to the model
- bounding the tool-use loop

### `src/llm.py`

Local model interface.

The current implementation uses Qwen3-8B through Hugging Face Transformers and
PyTorch.

### `src/mcp_server.py`

MCP server exposing the tools available to the agent.

### `src/google_docs.py`

Google integration layer.

Responsibilities include:

- OAuth authentication
- Google Drive document search
- Google Docs retrieval
- extraction of text from Google Docs responses

### `data/project_atlas.txt`

Synthetic project information used during development and for the local
`read_project_notes` MCP tool.

---

## Running the Project

Create and activate a Python virtual environment and install the dependencies:

```bash
pip install -r requirements.txt
```

Google integration requires a Google Cloud OAuth Desktop application with both
the Google Drive API and Google Docs API enabled.

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

Run the agent:

```bash
python src/agent.py
```

Example:

```text
You: Find the Google Doc for Atlas and tell me what I should discuss
with the architect.

[Tool] search_google_docs
[Tool] read_google_doc

My AI Brain: ...
```

---

## Current Limitations

The Module 2 implementation is intentionally limited in scope.

- Google Drive search currently searches document names rather than document
  contents semantically.
- Long-term memory is not yet implemented.
- There is no vector database or RAG pipeline.
- Retrieved information is not independently verified.
- There is no multi-agent workflow.
- Conflicting or outdated information is not yet detected automatically.
- Google is currently the primary real external integration.
- Tool routing depends on the local LLM correctly interpreting the available
  MCP tool descriptions.

These limitations will be addressed selectively as later course modules
introduce retrieval, multi-agent workflows, verification, and guardrails.

---

## Development Approach

The capstone is intentionally being built incrementally.

The objective is not to add every possible tool or agent pattern. Each module
adds only the concepts that improve the core goal of My AI Brain: reliably
remembering and retrieving work context while keeping the architecture small
enough to implement, understand, and evaluate.