from typing import Dict, List, Any, Optional
from .eventstore import EventStore
from .circuit import CircuitBreaker
from .core import StepExecution, ExecutionStatus
from .step import StepType
from datetime import datetime
import logging
from .registry import StepRegistry, StepRegistryError,StepMetadata
from .service_locator import ServiceLocator
from .factory import StepFactory
from .plugin import PluginManager 
class ProcessEngine:
    def __init__(self, 
                 event_store=None,
                 service_locator: Optional[ServiceLocator] = None):
        self.event_store = event_store
        self.service_locator = service_locator or ServiceLocator()
        self.registry = StepRegistry()
        self.factory = StepFactory(self.registry, self.service_locator)
        self.plugin_manager = PluginManager(self.registry, self.service_locator)
        self.logger = logging.getLogger("enhanced_process_engine")
        
        # Setup default steps
        self._register_default_steps()
    
    def _register_default_steps(self):
        """Register default step types"""
        
        # Import and register default step implementations
        from steps import (
            ValidationStep, CommandStep, QueryStep, 
            EmailStep, DatabaseStep, HttpRequestStep
        )
        
        # Validation steps
        self.registry.register("validation", ValidationStep, StepMetadata(
            step_class=ValidationStep,
            description="Generic validation step",
            category="validation",
            supported_types=[StepType.VALIDATION],
            required_services=[],
            configuration_schema={
                "type": "object",
                "properties": {
                    "validation_func": {"type": "string", "description": "Validation function name"},
                    "validation_rules": {"type": "array", "description": "List of validation rules"}
                },
                "required": ["validation_func"]
            }
        ))
        
        # Command steps  
        self.registry.register("command", CommandStep, StepMetadata(
            step_class=CommandStep,
            description="Generic command step for CQRS",
            category="cqrs",
            supported_types=[StepType.COMMAND],
            required_services=[],
            configuration_schema={
                "type": "object",
                "properties": {
                    "command_func": {"type": "string", "description": "Command function name"}
                },
                "required": ["command_func"]
            }
        ))
        
        # Query steps
        self.registry.register("query", QueryStep, StepMetadata(
            step_class=QueryStep,
            description="Generic query step for CQRS",
            category="cqrs", 
            supported_types=[StepType.QUERY],
            required_services=[],
            configuration_schema={
                "type": "object",
                "properties": {
                    "query_func": {"type": "string", "description": "Query function name"}
                },
                "required": ["query_func"]
            }
        ))
        
        # Email steps
        self.registry.register("email", EmailStep, StepMetadata(
            step_class=EmailStep,
            description="Send email notifications",
            category="notification",
            supported_types=[StepType.SIDE_EFFECT],
            required_services=["email_service"],
            configuration_schema={
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Email template name"},
                    "recipient_context_key": {"type": "string", "description": "Context key for recipient"}
                },
                "required": ["template"]
            }
        ))
        
        # Database steps
        self.registry.register("database", DatabaseStep, StepMetadata(
            step_class=DatabaseStep,
            description="Execute database operations",
            category="database",
            supported_types=[StepType.COMMAND, StepType.QUERY],
            required_services=["database_service"],
            configuration_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL query or procedure name"},
                    "parameters": {"type": "object", "description": "Query parameters"},
                    "transaction_required": {"type": "boolean", "default": False}
                },
                "required": ["query"]
            }
        ))
        
        # HTTP request steps
        self.registry.register("http_request", HttpRequestStep, StepMetadata(
            step_class=HttpRequestStep,
            description="Make HTTP requests to external services",
            category="integration",
            supported_types=[StepType.COMMAND, StepType.QUERY],
            required_services=["http_client"],
            configuration_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Request URL"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
                    "headers": {"type": "object", "description": "Request headers"},
                    "timeout": {"type": "integer", "default": 30}
                },
                "required": ["url"]
            }
        ))
        
        # Register aliases for common operations
        self.registry._aliases.update({
            "validate": "validation",
            "cmd": "command", 
            "select": "query",
            "insert": "database",
            "update": "database",
            "delete": "database",
            "send_email": "email",
            "notify": "email",
            "api_call": "http_request",
            "webhook": "http_request"
        })
    
    async def execute_process(self, process_config: Dict, context) -> Any:
        """Execute process using factory-created steps"""
        
        process_name = process_config.get("name", "unnamed_process")
        steps_config = process_config.get("steps", [])
        
        self.logger.info(f"Starting process {process_name}")
        
        try:
            # Create steps using factory
            steps = self.factory.create_steps_from_config_list(steps_config)
            
            # Execute steps (implementation details from previous artifacts)
            # This would integrate with the execution logic from the main engine
            
            return context
            
        except Exception as e:
            self.logger.error(f"Process {process_name} failed: {e}")
            raise
    
    def load_plugin(self, plugin: StepPlugin) -> None:
        """Load a step plugin"""
        self.plugin_manager.load_plugin(plugin)
    
    def get_available_steps(self) -> Dict[str, Dict]:
        """Get information about all available steps"""
        
        available_steps = {}
        
        for step_name in self.registry.list_steps():
            metadata = self.registry.get_metadata(step_name)
            available_steps[step_name] = {
                "description": metadata.description,
                "category": metadata.category,
                "supported_types": [t.value for t in metadata.supported_types],
                "required_services": metadata.required_services,
                "configuration_schema": metadata.configuration_schema,
                "examples": metadata.examples
            }
        
        return available_steps
