from typing import Callable, Any
from ..step import Step
from ..core import Context, StepResult, StepType
import asyncio

class QueryStep(Step):
    def __init__(self, step_id: str, query_func: Callable[[Context], Any]):
        super().__init__(step_id, StepType.QUERY)
        self.query_func = query_func

    async def execute(self, context: Context) -> StepResult:
        try:
            if asyncio.iscoroutinefunction(self.query_func):
                result = await self.query_func(context)
            else:
                result = self.query_func(context)
            return StepResult(success=True, data=result)
        except Exception as e:
            return StepResult(success=False, error=str(e))
