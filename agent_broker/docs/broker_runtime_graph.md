# Broker Runtime Graph

This diagram shows the active LangGraph pipeline assembled in
`opamp_broker/graph/graph.py`, plus the runtime planner/formatter selection
used by `plan_action` and `execute_or_summarize`.

```mermaid
flowchart TD
    Start([Inbound Slack message or slash command]) --> Normalize["normalize_input"]
    Normalize --> Classify["classify_intent"]
    Classify --> Plan["plan_action"]
    Plan --> Execute["execute_or_summarize"]
    Execute --> End([response_text returned to Slack adapter])

    subgraph PlannerSelection["Planner selection inside plan_action"]
        PlanGate{"ai_enabled && ai_planner available?"}
        PlanGate -- Yes --> AISvc["AISvcPlanner"]
        PlanGate -- No --> RuleFirst["RuleFirstPlanner"]
    end

    subgraph FormatterSelection["Formatter selection inside execute_or_summarize"]
        FormatGate{"ai_enabled && ai_planner available?"}
        FormatGate -- Yes --> AIFormat["ai_planner.format_tool_response_for_slack"]
        FormatGate -- No --> DefaultFormat["default response formatting path"]
    end

    AISvc -. selected planner .-> Plan
    RuleFirst -. selected planner .-> Plan
    AIFormat -. selected formatter .-> Execute
    DefaultFormat -. selected formatter .-> Execute
```

## Source

- Mermaid source: [broker_runtime_graph.mmd](./broker_runtime_graph.mmd)
