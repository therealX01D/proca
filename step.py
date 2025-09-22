from abc import ABC, abstractmethod
from typing import List
import logging
from .core import Context, StepResult, StepType

class Step(ABC):
    def __init__(self, step_id: str, step_type: StepType, retry_count: int = 0):
        self.step_id = step_id
        self.step_type = step_type
        self.retry_count = retry_count
        self.logger = logging.getLogger(f"step.{step_id}")

    @abstractmethod
    async def execute(self, context: Context) -> StepResult:
        raise NotImplementedError

    async def validate(self, context: Context) -> bool:
        return True

    async def compensate(self, context: Context) -> StepResult:
        return StepResult(success=True)

    def get_dependencies(self) -> List[str]:
        return []

    def get_required_context_keys(self) -> List[str]:
        return []
