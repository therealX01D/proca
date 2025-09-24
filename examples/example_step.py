from proca.step import Step,StepType,StepResult
from proca.core import Context
class CustomValidationStep(Step):
    """Example custom validation step"""
    
    async def execute(self, context: Context) -> StepResult:
        # Custom validation logic
        return StepResult(success=True, data={"validated": True})

class ExternalApiStep(Step):
    """Example external API step"""
    
    def __init__(self, step_id: str, step_type: StepType, api_client):
        super().__init__(step_id, step_type)
        self.api_client = api_client
    
    async def execute(self, context: Context) -> StepResult:
        # External API call logic
        return StepResult(success=True, data={"api_response": "success"})
