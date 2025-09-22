import asyncio
from typing import Callable, List, Any
from ..step import Step
from ..core import Context, StepResult, StepType

class CommandStep(Step):
    def __init__(self, step_id: str, command_func: Callable[[Context], Any], dependencies: List[str] = None, retry_count: int = 0):
        super().__init__(step_id, StepType.COMMAND, retry_count=retry_count)
        self.command_func = command_func
        self.dependencies = dependencies or []

    async def execute(self, context: Context) -> StepResult:
        try:
            result = await self._execute_with_retry(context)
            return StepResult(success=True, data=result)
        except Exception as e:
            return StepResult(success=False, error=str(e))

    async def _execute_with_retry(self, context: Context):
        for attempt in range(self.retry_count + 1):
            try:
                if asyncio.iscoroutinefunction(self.command_func):
                    return await self.command_func(context)
                else:
                    return self.command_func(context)
            except Exception:
                if attempt == self.retry_count:
                    raise
                await asyncio.sleep(2 ** attempt)

    def get_dependencies(self):
        return self.dependencies
