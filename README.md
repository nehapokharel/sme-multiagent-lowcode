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


# KMU Multi-Agenten-Prototyp zur Anforderungsübersetzung

Ein lauffähiger Multi-Agenten-Prototyp (Python + LangGraph), der unstrukturierte
Freitext-Anforderungen aus einem KMU über drei kollaborierende Agenten mit einer
Feedback-/Refinement-Schleife in einen validierten Low-Code-Entwurf überführt.

Läuft vollständig lokal über **Ollama**.


## Architektur

```
        ┌──────────┐        ┌───────────┐        ┌──────────┐
input → │ Analyst  │ ─────→ │ Architekt │ ─────→ │ Reviewer │ ─→ Freigabe? → ENDE
        └──────────┘        └───────────┘        └──────────┘
             ▲                    ▲                    │
             │                    │                    │
             └────────────────────┴── Feedbackschleife───┘
                (Reviewer leitet zurück an Analyst ODER Architekt)
```

- **Agent 1 — Anforderungs- und Prozessanalyst**: Extrahiert Kernentitäten, Rollen,
  Prozessschritte und Schnittstellen aus dem Freitext in ein strukturiertes JSON-Schema.
- **Agent 2 — Low-Code-Architekt**: Überführt die strukturierte Definition in einen
  konkreten Entwurf (Datenmodell, UI-Masken, Workflows) als JSON.
- **Agent 3 — Review- & Validierungs-Agent**: Prüft den Entwurf kritisch auf
  Machbarkeit, fehlende Edge-Cases (Validierungsregeln, Rechteverwaltung) und
  KMU-Konformität (Einfachheit). Bei Unklarheiten oder Lücken wird Feedback direkt an
  den Analysten oder Architekten zurückgespielt (zyklische Kollaboration statt linearer Ablauf).

Die Orchestrierung basiert auf **LangGraph**: Der Graph ist explizit in `graph.py`
definiert, einschließlich der bedingten Kanten (Conditional Edges) für die
Refinement-Schleife.

### Vollständig lokal 

Jeder Agent nutzt eine zentrale Funktion `call_llm_json(...)` (`llm_client.py`),
die mit einem lokalen **Ollama**-Modell kommuniziert. Es gibt keine externen API-Abhängigkeiten:
Das gesamte System funktioniert nach der Installation von Ollama und dem Download des Modells
komplett offline — keine Registrierung, keine API-Kosten, keine Rate-Limits während der Live-Demo.

## Einrichtung

### 1. Repository klonen / entpacken und Abhängigkeiten installieren

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Ollama installieren und Modell laden

```bash
# Ollama installieren: [https://ollama.com/download](https://ollama.com/download)
ollama pull llama3.2:3b
ollama serve   # Startet nach der Installation meist automatisch im Hintergrund
```

Sicherstellen, dass die Instanz unter http://localhost:11434 erreichbar ist.

### 3. (Optional) Konfiguration anpassen

```bash
cp .env.example .env
```

Die Standardeinstellungen sind bereits für eine reguläre Ollama-Installation vorkonfiguriert.
Dieser Schritt ist nur erforderlich, falls ein anderes Modell oder ein abweichender Port genutzt werden soll.



## Ausführung


### Kommandozeile (Einzeldurchlauf mit Trace-Ausgabe)

```bash
python graph.py
```

Führt den Standard-Beispiel-Prompt aus und gibt die Zwischenstände aller Agenten im Terminal aus.

### Live-Demo Web-UI (Streamlit)

```bash
streamlit run app.py
```

Öffnet die Benutzeroberfläche im Browser::
- Eigene KMU-Anforderung eingeben/anpassen (oder "KMU-Beispiel laden" klicken),
- Maximale Anzahl an Review-Iterationen festlegen,
- **Multi-Agenten-Lauf** starten anklicken und den Agenten-Dialog sowie Zustandsübergänge,
- Finalen, freigegebenen Low-Code-Entwurf (oder Status nach Iterationsgrenze) einsehen.

## Projektstruktur

```
agent-system/
├── app.py            # Streamlit live-demo UI
├── graph.py          # LangGraph-Graphdefinition (Knoten + Feedback-Kanten)
├── agents.py         # Prompts und Node-Funktionen der 3 Agenten
├── state.py          # Shared State Schema (TypedDict)
├── llm_client.py     # Ollama-Client & JSON-Parsing/Reparatur
├── .env.example
```

