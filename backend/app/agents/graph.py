import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from app.agents.planner_agent import planner_node
from app.agents.report_agent import report_node
from app.agents.scenario_parser_agent import scenario_parser_node
from app.agents.state import ExecutionState

logger = logging.getLogger(__name__)


def _should_continue_execution(state: ExecutionState) -> Literal["execute", "validate"]:
    planned_steps = state.get("planned_steps", [])
    current_index = state.get("current_step_index", 0)
    if current_index < len(planned_steps):
        return "execute"
    return "validate"


def build_execution_graph() -> StateGraph:
    graph = StateGraph(ExecutionState)

    graph.add_node("parse", scenario_parser_node)
    graph.add_node("plan", planner_node)
    graph.add_node("validate", lambda state: {"validation": None})
    graph.add_node("report", report_node)

    graph.set_entry_point("parse")
    graph.add_edge("parse", "plan")
    graph.add_edge("plan", END)
    graph.add_edge("validate", "report")
    graph.add_edge("report", END)

    return graph


def build_planning_graph():
    graph = build_execution_graph()
    return graph.compile()
