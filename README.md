# My AI Brain: A Second Brain for Work

My AI Brain is my capstone project for the CMU Agentic AI program.

The goal is to build an AI work assistant that can help professionals maintain
context across projects, retrieve relevant project information, and answer
questions grounded in their work knowledge.

The project will evolve incrementally as concepts from each course module are
introduced.

---

## Module 1 - Local LLM Baseline

The first version establishes a simple LLM-powered application using concepts
from Module 1.

### Current Architecture

User Question
    ↓
Agent
    ↓
Project Context
    ↓
Prompt
    ↓
Local LLM (Qwen3-0.6B)
    ↓
Response

The project currently uses:

- Python 3.12
- Hugging Face Transformers
- PyTorch
- Qwen3-0.6B running locally
- A small synthetic project file as context

### How It Works

`src/agent.py`

- Loads the sample project information
- Accepts questions from the user
- Constructs the prompt
- Sends the request to the LLM

`src/llm.py`

- Loads the Qwen tokenizer
- Loads the pretrained Qwen3-0.6B model
- Converts prompts into tokens
- Runs local model inference
- Decodes generated tokens back into text

`data/project_atlas.txt`

- Synthetic project information used to test the agent

### Example Questions

- What architecture did we decide to use?
- Who is investigating Kafka?
- Has Kafka been finalized?
- What retry strategy did we select?
- What should I discuss with the architect?
- What are the unresolved technical decisions?

### Module 1 Experiments

Qwen3-0.6B was tested with both standard generation and its thinking mode.

For the current simple project questions, thinking mode produced additional
reasoning but did not materially improve the final answers. Standard generation
is therefore used as the baseline.

### Current Limitations

This is intentionally a minimal implementation.

- The entire project file is inserted into the prompt.
- There is no semantic retrieval or RAG.
- There is no persistent long-term memory.
- There are no external tools.
- There is no multi-agent workflow.
- There is no independent answer verification.

These capabilities will be evaluated and added as later course modules
introduce the relevant concepts.