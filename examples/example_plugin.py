from typing import Dict, Type, Any
from proca.step import Step
from proca.plugin import StepPlugin 
from .example_step import CustomValidationStep,ExternalApiStep
from .example_service import CustomService,ExternalApiClient
class ExamplePlugin(StepPlugin):
    """Example plugin implementation"""
    
    def get_plugin_name(self) -> str:
        return "example_plugin"
    
    def get_step_classes(self) -> Dict[str, Type[Step]]:
        # This would return actual step classes
        return {
            "custom_validation": CustomValidationStep,
            "external_api": ExternalApiStep
        }
    
    def get_services(self) -> Dict[str, Any]:
        return {
            "custom_service": CustomService(),
            "api_client": ExternalApiClient()
        }