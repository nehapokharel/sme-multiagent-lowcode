"""
Streamlit UI for the live demo.
"""

import streamlit as st

from graph import build_graph
from state import AgentState
from llm_client import OLLAMA_MODEL

st.set_page_config(page_title="LowCodeKMU Multi-Agent Orchestrator", layout="wide")

EXAMPLE_INPUT = (
    "Wenn in der Montage ein Teil fehlerhaft ist, soll der Werker das fotografieren, "
    "die Teilenummer scannen und eine Fehlerkategorie wählen können. Der Schichtleiter "
    "muss sofort benachrichtigt werden, falls es der dritte Fehler an einem Tag an dieser "
    "Station ist. Am Monatsende braucht die Qualitätssicherung einen PDF-Report."
)

AGENT_LABELS = {
    "analyst": "1. Requirements & Process Analyst",
    "architect": "2. Low-Code Architect",
    "reviewer": "3. Review & Validation Agent",
}

AGENT_INFO = [
    ("1", "Requirements & Process Analyst", "Extrahiert Rollen, Prozessschritte, Daten & Trigger"),
    ("2", "Low-Code Architect", "Erzeugt Datenschema, UI-Layout & Automatisierungen"),
    ("3", "Review & KMU Validator", "Prüft Edge Cases, Machbarkeit & Einfachheit"),
]


# Custom CSS Badges for UI State Representation
CUSTOM_CSS = """
<style>
    .badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 999px;
        font-family: monospace;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid;
    }
    .badge-running { color: #7ee2c8; border-color: #2f6f5e; background: rgba(46,160,132,0.08); }
    .badge-approved { color: #7ee2a0; border-color: #2f6f45; background: rgba(46,160,90,0.10); }
    .badge-warning { color: #f0c674; border-color: #7a5f24; background: rgba(240,198,116,0.08); }
    .badge-fallback { color: #f0c674; border-color: #7a5f24; background: rgba(240,198,116,0.10); }
    .badge-hosted { color: #7ee2a0; border-color: #2f6f45; background: rgba(46,160,90,0.08); }
    .section-label {
        font-family: monospace;
        letter-spacing: 0.08em;
        color: #8b949e;
        font-size: 0.78rem;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


# Header & Sidebar Configuration
st.title("LowCodeKMU Multi-Agent Orchestrator")
st.caption(
    "LangGraph orchestration · 3 specialized agents · feedback loop · "
    "runs entirely locally via Ollama (llama3.2:3b)"
)

with st.sidebar:
    st.header("Settings")
    max_iterations = st.slider("Max review iterations", min_value=1, max_value=5, value=3)

# Pipeline Architecture Cards
st.markdown('<div class="section-label">AGENT PIPELINE</div>', unsafe_allow_html=True)

for num, name, desc in AGENT_INFO:
    with st.container(border=True):
        cols = st.columns([1, 11])
        with cols[0]:
            st.markdown(f"### {num}")
        with cols[1]:
            st.markdown(f"**{name}**")
            st.caption(desc)

st.markdown(
    "*Conditional loop-back → Agent 1 or 2 if the reviewer requests a revision*"
)
st.markdown("")

# User Requirement Input Form
st.markdown('<div class="section-label">REQUIREMENT INPUT</div>', unsafe_allow_html=True)

if "raw_input" not in st.session_state:
    st.session_state.raw_input = ""

if st.button("📋 Load SME Example"):
    st.session_state.raw_input = EXAMPLE_INPUT

raw_input = st.text_area(
    "SME requirement (free text):",
    key="raw_input",
    placeholder="Beschreiben Sie hier einen unstrukturierten Geschäftsprozess...",
    height=120,
    label_visibility="collapsed",
)

run_clicked = st.button("▶ Start Multi-Agent Run", type="primary", disabled=not raw_input.strip())


# Dynamic Streaming Execution Loop
if run_clicked:
    app = build_graph()
    initial_state: AgentState = {
        "raw_requirement": raw_input,
        "process_definition": None,
        "design": None,
        "review": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "status": "running",
        "log": [],
        "architect_stalled": False,
    }

    status_placeholder = st.empty()
    st.markdown('<div class="section-label">ORCHESTRATOR LOG</div>', unsafe_allow_html=True)
    trace_container = st.container()
    shown_log_entries = 0

    # Stream partial state updates step-by-step to populate the UI live
    # We merge each partial update into `full_state` ourselves so nothing gets lost by the end.
    full_state = dict(initial_state)

    for step_output in app.stream(initial_state):
        for node_name, node_state in step_output.items():
            full_state.update(node_state)
            new_entries = full_state["log"][shown_log_entries:]
            shown_log_entries = len(full_state["log"])

            current_iter = full_state["iteration"] + 1
            status_placeholder.markdown(
                badge(f"Iteration {current_iter} / {max_iterations}", "running")
                + "&nbsp;&nbsp;"
                + badge("Running", "running"),
                unsafe_allow_html=True,
            )

            for entry in new_entries:
                with trace_container.container(border=True):
                    st.markdown(
                        f"**Step {entry['iteration']} — {AGENT_LABELS.get(node_name, node_name)}**"
                        f"&nbsp;&nbsp;{badge(entry['backend'], 'hosted')}",
                        unsafe_allow_html=True,
                    )
                    st.json(entry["output"])

    # Final Outcome & Output Display
    status = full_state["status"]
    final_iter = full_state["iteration"]
    if status == "approved":
        status_placeholder.markdown(
            badge(f"Iteration {final_iter} / {max_iterations}", "approved")
            + "&nbsp;&nbsp;"
            + badge("Approved", "approved"),
            unsafe_allow_html=True,
        )
    elif status == "max_iterations_reached":
        status_placeholder.markdown(
            badge(f"Iteration {final_iter} / {max_iterations}", "warning")
            + "&nbsp;&nbsp;"
            + badge("Max iterations reached", "warning"),
            unsafe_allow_html=True,
        )
    elif status == "stalled_no_progress":
        status_placeholder.markdown(
            badge(f"Iteration {final_iter} / {max_iterations}", "warning")
            + "&nbsp;&nbsp;"
            + badge("Stalled — no progress", "warning"),
            unsafe_allow_html=True,
        )

    st.markdown("---")
    if status == "approved":
        st.success("Design approved by the review agent.")
    elif status == "max_iterations_reached":
        st.warning(
            f"Max iterations ({max_iterations}) reached without approval. "
            "Showing the last design produced."
        )
    elif status == "stalled_no_progress":
        st.warning(
            "The Architect's revision was identical to its previous attempt — "
            "stopped early instead of repeating the same design. Showing the last "
            "design produced."
        )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Final process definition")
        st.json(full_state["process_definition"])
    with col2:
        st.subheader("Final design")
        st.json(full_state["design"])

    st.subheader("Final review")
    st.json(full_state["review"])

    n_calls = len(full_state["log"])
    st.caption(f"Total LLM calls: {n_calls} · model: {OLLAMA_MODEL}")
