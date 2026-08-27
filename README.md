# SME Multi-Agent Requirement Translation Prototype

A runnable multi-agent prototype (Python + LangGraph) that translates an
unstructured free-text requirement from an SME into a validated low-code design,
via three collaborating agents with a feedback/refinement loop.

Runs entirely locally via **Ollama**.


## Architecture

```
        ┌──────────┐        ┌───────────┐        ┌──────────┐
input → │ Analyst  │ ─────→ │ Architect │ ─────→ │ Reviewer │ ─→ approved? → END
        └──────────┘        └───────────┘        └──────────┘
             ▲                    ▲                    │
             │                    │                    │
             └────────────────────┴── feedback loop ───┘
                (reviewer routes back to analyst OR architect)
```

- **Agent 1 — Requirements & Process Analyst**: extracts entities, roles, process
  steps, and interfaces from the free-text input into structured JSON.
- **Agent 2 — Low-Code Architect**: turns that structure into a concrete design
  (data model, UI screens, workflows) as JSON.
- **Agent 3 — Review & Validation Agent**: critically checks the design for
  feasibility, missing edge cases (validation, roles/permissions), and
  SME-appropriate simplicity. If it finds issues, it routes feedback back to
  either the Analyst or the Architect (not just a linear pass-through).

Orchestration is built with **LangGraph**: the graph above is defined explicitly
in `graph.py`, including the conditional edge that implements the collaboration
loop.

### Fully local — no API keys, no cost

Every agent calls a single `call_llm_json(...)` function (`llm_client.py`),
which talks to a local **Ollama** model. There is no hosted API dependency
at all, so the whole system runs offline once Ollama and the model are
installed — no signup, no billing, no rate limits to worry about before
a live demo.

## Setup

### 1. Clone / unzip and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install and set up Ollama

```bash
# Install Ollama: https://ollama.com/download
ollama pull llama3.2:3b
ollama serve   # usually starts automatically after install
```

Verify it's reachable at `http://localhost:11434`.

### 3. (Optional) configure

```bash
cp .env.example .env
```

The defaults already match a standard Ollama install, so this step is only
needed if you want to use a different model or port.

## Running

### Command line (single run, prints the trace)

```bash
python graph.py
```

Runs the built-in example input and prints each agent's output.

### Live demo UI (Streamlit)

```bash
streamlit run app.py
```

Opens a browser UI where you can:
- paste/edit the SME requirement text (or click "Load SME Example"),
- set the max number of review iterations,
- click **Start Multi-Agent Run** and watch each agent's step appear live,
  including the feedback loop firing if the reviewer sends work back,
- see the final approved (or "max iterations reached") design.

## Project structure

```
agent-system/
├── app.py            # Streamlit live-demo UI
├── graph.py           # LangGraph graph definition (nodes + feedback-loop edge)
├── agents.py          # The 3 agent prompts + node functions
├── state.py            # Shared state schema (TypedDict)
├── llm_client.py       # Ollama client + JSON parsing/repair
├── .env.example
```


