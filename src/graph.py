"""
Graph-based orchestration (LangGraph) of the 3-agent SME requirement pipeline.
"""

from langgraph.graph import StateGraph, END

from state import AgentState
from agents import analyst_node, architect_node, reviewer_node


def route_after_review(state: AgentState) -> str:
    """
    Evaluates conditional branches following review:
      - Transitions to END if approved, stalled, or max iterations reached.
      - Routes back to 'analyst' or 'architect' for revisions otherwise.
    """
    review = state["review"]
    if review.get("genehmigt"):
        return "end"
    if state.get("architect_stalled"):
        return "end"
    if state["iteration"] >= state["max_iterations"]:
        return "end"
    ziel = review.get("ziel")
    if ziel in ("analyst", "architect"):
        return ziel
    return "architect"


def build_graph():
    """Assembles and compiles the StateGraph workflow."""
    graph = StateGraph(AgentState)

    # Register workflow nodes
    graph.add_node("analyst", analyst_node)
    graph.add_node("architect", architect_node)
    graph.add_node("reviewer", reviewer_node)

    # Define linear pipeline progression
    graph.set_entry_point("analyst")
    graph.add_edge("analyst", "architect")
    graph.add_edge("architect", "reviewer")

    # Dynamic loop-back based on review outcome
    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "analyst": "analyst",
            "architect": "architect",
            "end": END,
        },
    )

    return graph.compile()


def run_pipeline(raw_requirement: str, max_iterations: int = 3):
    """Convenience synchronous entry-point for testing or CLI invocation."""
    app = build_graph()
    initial_state: AgentState = {
        "raw_requirement": raw_requirement,
        "process_definition": None,
        "design": None,
        "review": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "status": "running",
        "log": [],
        "architect_stalled": False,
    }
    return app.invoke(initial_state)


if __name__ == "__main__":
    EXAMPLE_INPUT = (
        "Wenn in der Montage ein Teil fehlerhaft ist, soll der Werker das fotografieren, "
        "die Teilenummer scannen und eine Fehlerkategorie wählen können. Der Schichtleiter "
        "muss sofort benachrichtigt werden, falls es der dritte Fehler an einem Tag an dieser "
        "Station ist. Am Monatsende braucht die Qualitätssicherung einen PDF-Report."
    )
    final_state = run_pipeline(EXAMPLE_INPUT)

    print("\n=== FINAL STATUS:", final_state["status"], "===\n")
    print("Process definition:", final_state["process_definition"])
    print("\nDesign:", final_state["design"])
    print("\nReview:", final_state["review"])
    print(f"\nTotal LLM calls: {len(final_state['log'])}")
    for entry in final_state["log"]:
        print(f"  [{entry['iteration']}] {entry['agent']:10s} via {entry['backend']}")
