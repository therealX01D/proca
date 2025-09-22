from typing import List
from .core import StepExecution, Context, ExecutionStatus
from datetime import datetime

class EventStore:
    def __init__(self):
        self.events: List[StepExecution] = []

    async def store_execution(self, execution: StepExecution):
        self.events.append(execution)

    async def get_process_history(self, process_id: str) -> List[StepExecution]:
        return [e for e in self.events if e.process_id == process_id]

    async def replay_process(self, process_id: str) -> Context:
        events = await self.get_process_history(process_id)
        context = Context(process_id=process_id)
        for event in sorted(events, key=lambda x: x.started_at):
            if event.status == ExecutionStatus.SUCCESS:
                context.data[f"{event.step_id}_result"] = event.output_data
        return context
