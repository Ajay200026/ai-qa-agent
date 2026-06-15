from abc import ABC, abstractmethod

from app.schemas.agent import ExecutionPlan, PlannedStep
from app.schemas.parsed_scenario import ParsedScenario


class WorkflowStrategy(ABC):
    @abstractmethod
    def bind_inputs(self, inputs: dict[str, str]) -> "WorkflowStrategy":
        ...

    @abstractmethod
    def merge(
        self,
        business_actions: list[dict],
        expected_results: list[str],
    ) -> tuple[list[PlannedStep], ExecutionPlan]:
        ...


class DatabaseWorkflowStrategy(WorkflowStrategy):
    """Fully DB-driven workflow — new templates need only a database row."""

    def __init__(self, template_key: str, template_name: str, steps: list, input_schema: dict):
        self.template_key = template_key
        self.template_name = template_name
        self._template_steps = steps
        self.input_schema = input_schema
        self._inputs: dict[str, str] = {}

    def bind_inputs(self, inputs: dict[str, str]) -> "DatabaseWorkflowStrategy":
        merged = {}
        for key, spec in self.input_schema.items():
            merged[key] = inputs.get(key) or spec.get("default", "")
        merged.update(inputs)
        self._inputs = merged
        return self

    def _substitute_params(self, params: dict) -> dict:
        result = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                placeholder = v[1:-1]
                result[k] = self._inputs.get(placeholder, v)
            else:
                result[k] = v
        return result

    def _should_include_step(self, step_def: dict) -> bool:
        if step_def.get("require_input"):
            val = self._inputs.get(step_def["require_input"], "")
            if not val or val in ("__any__", "__first__"):
                return False
        if step_def.get("skip_if_input"):
            val = self._inputs.get(step_def["skip_if_input"], "")
            if val and val not in ("__any__", "__first__", ""):
                return False
        return True

    def merge(
        self,
        business_actions: list[dict],
        expected_results: list[str],
    ) -> tuple[list[PlannedStep], ExecutionPlan]:
        from app.workflows.merger import PlanMerger

        merger = PlanMerger(self)
        return merger.merge(business_actions, expected_results)
