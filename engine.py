from typing import Dict, List
from .eventstore import EventStore
from .circuit import CircuitBreaker
from .core import StepExecution, ExecutionStatus
from .step import Step
from datetime import datetime
import logging

class ProcessEngine:
    def __init__(self, event_store: EventStore = None):
        self.event_store = event_store or EventStore()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = logging.getLogger("process_engine")

    async def execute_process(self, process_definition: Dict, context):
        process_name = process_definition.get("name", "unnamed_process")
        steps_config = process_definition.get("steps", [])
        self.logger.info(f"Starting process {process_name} with ID {context.process_id}")

        steps = self._build_steps_from_config(steps_config)
        execution_order = self._resolve_dependencies(steps)

        executed_steps: List[Step] = []
        try:
            for step in execution_order:
                record = await self._execute_step_with_patterns(step, context)
                if record.status == ExecutionStatus.SUCCESS:
                    executed_steps.append(step)
                    context.data[f"{step.step_id}_result"] = record.output_data
                else:
                    self.logger.error(f"Step {step.step_id} failed: {record.error_message}")
                    await self._compensate_executed_steps(executed_steps, context)
                    raise Exception(f"Process failed at step {step.step_id}: {record.error_message}")
            self.logger.info(f"Process {process_name} completed successfully")
            return context
        except Exception:
            raise

    async def _execute_step_with_patterns(self, step: Step, context):
        circuit_breaker = self._get_circuit_breaker(step.step_id)
        if not circuit_breaker.can_execute():
            execution_record = StepExecution(step_id=step.step_id, process_id=context.process_id, started_at=datetime.now(), completed_at=datetime.now(), status=ExecutionStatus.FAILED, error_message="Circuit breaker is OPEN")
            await self.event_store.store_execution(execution_record)
            return execution_record

        execution_record = StepExecution(step_id=step.step_id, process_id=context.process_id, started_at=datetime.now(), input_data=context.data.copy())
        try:
            if not await step.validate(context):
                raise Exception(f"Step validation failed for {step.step_id}")
            execution_record.status = ExecutionStatus.RUNNING
            result = await step.execute(context)
            if result.success:
                execution_record.status = ExecutionStatus.SUCCESS
                execution_record.output_data = result.data
                circuit_breaker.record_success()
            else:
                execution_record.status = ExecutionStatus.FAILED
                execution_record.error_message = result.error
                circuit_breaker.record_failure()
        except Exception as e:
            execution_record.status = ExecutionStatus.FAILED
            execution_record.error_message = str(e)
            circuit_breaker.record_failure()
        finally:
            execution_record.completed_at = datetime.now()
            execution_record.metadata = {
                "execution_time_ms": (execution_record.completed_at - execution_record.started_at).total_seconds() * 1000,
                "step_type": step.step_type.value
            }
            await self.event_store.store_execution(execution_record)
            context.execution_trace.append({
                "step_id": step.step_id,
                "status": execution_record.status.value,
                "timestamp": execution_record.completed_at.isoformat()
            })
        return execution_record

    async def _compensate_executed_steps(self, executed_steps: List[Step], context):
        self.logger.info("Starting compensation for executed steps")
        for step in reversed(executed_steps):
            try:
                res = await step.compensate(context)
                if res.success:
                    self.logger.info(f"Successfully compensated step {step.step_id}")
                else:
                    self.logger.error(f"Failed to compensate step {step.step_id}: {res.error}")
            except Exception as exc:
                self.logger.error(f"Exception during compensation of step {step.step_id}: {exc}")

    def _get_circuit_breaker(self, step_id: str) -> CircuitBreaker:
        if step_id not in self.circuit_breakers:
            self.circuit_breakers[step_id] = CircuitBreaker()
        return self.circuit_breakers[step_id]

    def _build_steps_from_config(self, steps_config):
        # Minimal factory: expand to plugin registry later
        from .steps.validation import ValidationStep
        from .steps.command import CommandStep
        from .steps.query import QueryStep

        steps = []
        for cfg in steps_config:
            step_type = cfg["type"]
            step_id = cfg["name"]
            if step_type == "validation":
                steps.append(ValidationStep(step_id, lambda ctx: True))
            elif step_type == "command":
                steps.append(CommandStep(step_id, lambda ctx: {"created": True}, cfg.get("dependencies", [])))
            elif step_type == "query":
                steps.append(QueryStep(step_id, lambda ctx: {"data": "queried"}))
            else:
                steps.append(CommandStep(step_id, lambda ctx: {"executed": True}))
        return steps

    def _resolve_dependencies(self, steps):
        step_map = {s.step_id: s for s in steps}
        resolved = []
        unresolved = set(steps)
        while unresolved:
            progress = False
            for step in list(unresolved):
                deps = step.get_dependencies()
                if all(dep in [r.step_id for r in resolved] for dep in deps):
                    resolved.append(step)
                    unresolved.remove(step)
                    progress = True
                    break
            if not progress:
                raise Exception("Circular dependency detected or unresolvable dependencies")
        return resolved
