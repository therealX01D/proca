from typing import Callable
from ..step import Step
from ..core import Context, StepResult, StepType

class ValidationStep(Step):
    def __init__(self, step_id: str, validation_func: Callable[[Context], bool]):
        super().__init__(step_id, StepType.VALIDATION)
        self.validation_func = validation_func

    async def execute(self, context: Context) -> StepResult:
        try:
            is_valid = self.validation_func(context)
            return StepResult(success=is_valid, data={"is_valid": is_valid}, error=None if is_valid else f"Validation failed for {self.step_id}")
        except Exception as exc:
            return StepResult(success=False, error=str(exc))
