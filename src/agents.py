"""
The three specialized agents, implemented as LangGraph node functions.

Each node:
  1. builds a prompt (incorporating prior state + any review feedback aimed at it)
  2. calls the LLM expecting JSON back
  3. returns a partial state update, including a log entry for the UI/demo
"""

import json

from state import AgentState
from validators import run_structural_checks


# Agent 1: Requirements & Process Analyst 

ANALYST_SYSTEM_PROMPT = """Du bist ein Anforderungs- und Prozessanalyst für KMU-Digitalisierungsprojekte. \
Deine Aufgabe: unstrukturierte Freitext-Beschreibungen eines Geschäftsprozesses in eine saubere, \
strukturierte Prozessdefinition überführen.

Antworte NUR mit einem JSON-Objekt nach diesem Schema:
{
  "kernentitaeten": ["zentrale Geschäftsobjekte/Datenkonzepte, die explizit genannt oder direkt impliziert werden"],
  "rollen": ["menschliche Akteure, Abteilungen oder externe Rollen"],
  "prozessschritte": [
    {
      "schritt": 1,
      "akteur": "wer führt die Aktion aus",
      "aktion": "welche Aktion wird ausgeführt",
      "trigger_oder_bedingung": "operativer Trigger, Bedingung, Regel oder Fallback (oder null, falls keiner)"
    }
  ],
  "schnittstellen": ["Hardware- oder Software-Schnittstellen, z. B. Kamera/Scanner, E-Mail/Push-Benachrichtigung, Report-Export, externe API"],
  "offene_fragen": ["kritische fachliche Unklarheiten, die aus dem Text nicht ableitbar sind, falls vorhanden"]
}

REGEL ZUR SCHRITT-GRANULARITÄT — wichtig:
- Jeder Eintrag in "prozessschritte" darf genau EINE atomare Aktion beschreiben, nicht mehrere,
  die mit Komma oder "und" verbunden sind. Das ist wichtig für die nachfolgenden Schritte: jede
  atomare Aktion braucht ihr eigenes Datenfeld und UI-Element, was unmöglich korrekt abzubilden
  ist, wenn mehrere Aktionen im "aktion"-Text eines einzelnen Schritts zusammengefasst werden.

  BEISPIEL — folge genau diesem Muster:

  Eingabetext: "Der Werker soll das Teil fotografieren, die Teilenummer scannen
  und eine Fehlerkategorie wählen."

  FALSCH (nicht so machen — fasst 3 Aktionen zusammen mit einem falschen Trigger):
  [
    {"schritt": 1, "akteur": "Werker", "aktion": "fotografieren", "trigger_oder_bedingung": "Fehlerkategorie wählen"},
    {"schritt": 2, "akteur": "Werker", "aktion": "Teilenummer scannen", "trigger_oder_bedingung": "Fehlerkategorie wählen"}
  ]

  RICHTIG (3 atomare Schritte, jeweils mit korrektem trigger_oder_bedingung —
  "Fehlerkategorie wählen" ist hier selbst eine AKTION, niemals der Trigger für einen anderen Schritt):
  [
    {"schritt": 1, "akteur": "Werker", "aktion": "fotografieren", "trigger_oder_bedingung": "Teil ist fehlerhaft"},
    {"schritt": 2, "akteur": "Werker", "aktion": "Teilenummer scannen", "trigger_oder_bedingung": null},
    {"schritt": 3, "akteur": "Werker", "aktion": "Fehlerkategorie wählen", "trigger_oder_bedingung": null}
  ]

  Wende dieselbe Ein-Aktion-pro-Schritt-Aufteilung auf jede Aktionsfolge im Eingabetext an,
  unabhängig von der Formulierung.

ALLGEMEINE RICHTLINIEN:
- Extrahiere alle bedingten Verzweigungen, Eskalationspfade und zeitbasierten Regeln aus dem Eingabetext.
- Fokussiere dich strikt auf die fachliche Prozesslogik (wer, was, wann, warum).
- Erfinde keine technischen Implementierungsdetails (z. B. Datenbankschemas, JSON-Schemas, Netzwerkprotokolle).
- Gib niemals Platzhalter in spitzen Klammern in deinen finalen Werten aus."""


def analyst_node(state: AgentState) -> dict:
    """
    Agent 1: Extracts roles, atomic process steps, data entities, and trigger rules.
    Includes reviewer feedback if a loop-back revision was targeted at the analyst.
    """
    feedback_note = ""
    review = state.get("review")
    if review and review.get("ziel") == "analyst":
        feedback_note = (
            f"\n\nDer Review-Agent hat dies zur Überarbeitung zurückgeschickt:\n{review['feedback']}\n"
            "Bitte überarbeite die Prozessdefinition entsprechend diesem Feedback."
        )

    user_prompt = f"KMU-Anforderung (Freitext):\n{state['raw_requirement']}{feedback_note}"

    from llm_client import call_llm_json
    data, backend = call_llm_json(ANALYST_SYSTEM_PROMPT, user_prompt)

    log_entry = {
        "agent": "Analyst",
        "backend": backend,
        "iteration": state["iteration"],
        "output": data,
    }
    return {"process_definition": data, "log": state["log"] + [log_entry]}


# Agent 2: Low-Code-Architekt

ARCHITECT_SYSTEM_PROMPT = """Du bist ein Low-Code-Architekt für ein KMU-Digitalisierungsprojekt. \
Du überführst eine strukturierte Prozessdefinition in einen Low-Code-Entwurf (Datenmodell, UI-Masken, Workflows).

Antworte NUR mit einem JSON-Objekt nach diesem Schema:
{
  "datenmodell": [
    {
      "entitaet": "EntitätsName",
      "felder": [
        {"name": "feldname", "typ": "string|number|date|boolean|enum|file", "pflichtfeld": true}
      ]
    }
  ],
  "ui_masken": [
    {"name": "MaskenName", "rolle": "RollenName", "felder_oder_aktionen": ["Feld oder Button"]}
  ],
  "workflows": [
    {
      "name": "WorkflowName",
      "trigger": "Auslösebedingung",
      "schritte": ["Schritt 1", "Schritt 2"],
      "benachrichtigungen": ["Empfänger, Kanal, Bedingung"]
    }
  ]
}

KRITISCHE REGELN:
1. Jede Nutzer-Aktion im Prozess MUSS ein entsprechendes Feld im datenmodell haben:
   - Foto machen -> Feldtyp "file" (z. B. name: "Foto", typ: "file")
   - Barcode/Nummer scannen -> Feldtyp "string" (z. B. name: "Teilenummer", typ: "string")
   - Kategorie auswählen -> Feldtyp "enum" (z. B. name: "Fehlerkategorie", typ: "enum")
2. Sofortige operative Ereignisse (Fehler/Alarme) und periodische Aufgaben (monatlicher PDF-Report)
   müssen getrennte Workflows sein.
3. Falls Überarbeitungs-Feedback gegeben wird:
   - Lies die Liste "Fehlende Elemente" sorgfältig — sie sagt dir genau und ausschließlich,
     was tatsächlich fehlt. Füge NUR diese Elemente hinzu.
   - Entferne, benenne nicht um oder verändere keine bereits vorhandenen Felder/Workflows,
     die nicht in der Liste der fehlenden Elemente genannt werden — übernimm sie unverändert.
   - Falls nichts aus der Liste zutrifft (z. B. weil es sich herausstellt, bereits vorhanden
     zu sein), gib deinen vorherigen Entwurf exakt unverändert zurück."""


def architect_node(state: AgentState) -> dict:
    """
    Agent 2: Converts the process specification into concrete Low-Code data models, 
    UI views, and workflow triggers. Detects convergence stalls during iterative repairs.
    """
    feedback_note = ""
    review = state.get("review")
    if review and review.get("ziel") == "architect":
        missing_items = review.get("fehlende_details") or [review.get("feedback", "")]
        missing_list = "\n".join(f"- {item}" for item in missing_items if item)
        feedback_note = (
            f"\n\nFehlende Elemente (verifiziert — dies sind die EINZIGEN hinzuzufügenden Dinge):\n{missing_list}\n"
            f"\nDein vorheriger Entwurf:\n{json.dumps(state.get('design'), ensure_ascii=False)}\n"
            "Aktualisiere deinen vorherigen Entwurf, um genau diese fehlenden Elemente hinzuzufügen. "
            "Lasse alles andere unverändert."
        )

    user_prompt = (
        f"Prozessdefinition:\n{json.dumps(state['process_definition'], ensure_ascii=False)}"
        f"{feedback_note}"
    )

    from llm_client import call_llm_json
    data, backend = call_llm_json(ARCHITECT_SYSTEM_PROMPT, user_prompt)

    # Detect if the model converged into a loop by outputting an unchanged design payload
    made_no_change = False
    if review and review.get("ziel") == "architect":
        prev_design = state.get("design")
        if prev_design is not None and json.dumps(data, sort_keys=True) == json.dumps(prev_design, sort_keys=True):
            made_no_change = True

    log_entry = {
        "agent": "Architect",
        "backend": backend,
        "iteration": state["iteration"],
        "output": data,
    }
    return {
        "design": data,
        "log": state["log"] + [log_entry],
        "architect_stalled": made_no_change,
    }



# Agent 3: Review- & Validierungs-Agent

REVIEWER_SYSTEM_PROMPT = """Du bist ein Qualitätssicherungs- und Validierungs-Agent für ein KMU-Low-Code-System. \
Du beurteilst, ob der vorgeschlagene Low-Code-Entwurf die Prozessdefinition angemessen unterstützt.

Du erhältst das Ergebnis von zwei STRUKTURELLEN PRÜFUNGEN, die bereits per Code (nicht von dir)
berechnet wurden — behandle diese als verifizierte Fakten, leite sie nicht neu ab und stelle sie
nicht infrage.

Antworte NUR mit einem JSON-Objekt nach diesem Schema:
{
  "probleme": ["<jedes ZUSÄTZLICHE qualitative Problem, das du über die strukturellen Prüfungen hinaus findest, falls vorhanden>"],
  "zusaetzliches_feedback": "<optionale zusätzliche Anleitung für den Architekten über die strukturellen Prüfungen hinaus, oder leerer String>"
}

Deine Aufgabe hier ist AUSSCHLIESSLICH, qualitative Einschätzungen zusätzlich zu den strukturellen
Prüfungen zu liefern — z. B. KMU-gerechte Einfachheit, fehlende Rollen-/Rechteverwaltung oder
unklare Geschäftslogik. Wiederhole NICHT die Ergebnisse der strukturellen Prüfungen; diese werden
separat behandelt. Falls du nichts über die strukturellen Prüfungen hinaus hinzuzufügen hast,
gib {"probleme": [], "zusaetzliches_feedback": ""} zurück."""


def reviewer_node(state: AgentState) -> dict:
    """
    Agent 3: Combines deterministic structural validation with qualitative LLM evaluation.
    Evaluates termination flags and assigns revision directives for targeted agent re-entry.
    """
    process_definition = state["process_definition"]
    design = state["design"]

    # Deterministic structural checks
    structural = run_structural_checks(process_definition, design)
    pruefungen = structural["pruefungen"]
    fehlende_details = structural["fehlende_details"]
    structural_passed = all(pruefungen.values())

    # Qualitative LLM assessment
    user_prompt = (
        f"Prozessdefinition:\n{json.dumps(process_definition, ensure_ascii=False)}\n\n"
        f"Vorgeschlagener Entwurf:\n{json.dumps(design, ensure_ascii=False)}\n\n"
        f"Ergebnisse der strukturellen Prüfungen (bereits verifiziert, nicht neu ableiten):\n"
        f"{json.dumps(pruefungen, ensure_ascii=False)}\n"
        f"Von den strukturellen Prüfungen gefundene fehlende Elemente:\n"
        f"{json.dumps(fehlende_details, ensure_ascii=False)}"
    )

    from llm_client import call_llm_json
    llm_data, backend = call_llm_json(REVIEWER_SYSTEM_PROMPT, user_prompt)

    extra_probleme = llm_data.get("probleme") or []
    extra_feedback = llm_data.get("zusaetzliches_feedback") or ""
    genehmigt = structural_passed
    ziel = None if genehmigt else "architect"
    probleme = list(fehlende_details) + list(extra_probleme)
    feedback = "" if genehmigt else (
        "Füge die folgenden fehlenden Elemente hinzu:\n"
        + "\n".join(f"- {item}" for item in fehlende_details)
        + (f"\n\nZusätzliche Hinweise: {extra_feedback}" if extra_feedback else "")
    )

    data = {
        "pruefungen": pruefungen,
        "genehmigt": genehmigt,
        "probleme": probleme,
        "ziel": ziel,
        "feedback": feedback,
        "fehlende_details": fehlende_details,
    }

    log_entry = {
        "agent": "Reviewer",
        "backend": backend,
        "iteration": state["iteration"],
        "output": data,
    }

    # Determine pipeline execution status
    new_iteration = state["iteration"] + 1
    if state.get("architect_stalled"):
        status = "stalled_no_progress"
    elif genehmigt:
        status = "approved"
    elif new_iteration >= state["max_iterations"]:
        status = "max_iterations_reached"
    else:
        status = "revising"

    return {
        "review": data,
        "iteration": new_iteration,
        "status": status,
        "log": state["log"] + [log_entry],
    }
