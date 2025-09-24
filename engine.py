from typing import Dict, List, Any, Optional
from .eventstore import EventStore
from .circuit import CircuitBreaker
from .core import StepExecution, ExecutionStatus
from .step import Step,StepType
from datetime import datetime
import logging
from .registry import StepRegistry, StepRegistryError,StepMetadata
from .service_locator import ServiceLocator
from .factory import StepFactory
from .plugin import PluginManager ,StepPlugin
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
        async def _execute_step_with_patterns(self, step: Step, context):
            circuit_breaker = self._get_circuit_breaker(step.step_id)
            if not circuit_breaker.can_execute():
                execution_record = StepExecution(step_id=step.step_id, process_id=context.process_id,
                                                started_at=datetime.now(), completed_at=datetime.now(),
                                                status=ExecutionStatus.FAILED, error_message="Circuit breaker is OPEN")
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
    def _resolve_dependencies(self, steps: List[Step]) -> List[Step]:
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

    async def execute_process(self, process_config: Dict, context) -> Any:
        """Execute process using factory-created steps"""
        
        process_name = process_config.get("name", "unnamed_process")
        steps_config = process_config.get("steps", [])
        
        self.logger.info(f"Starting process {process_name}")
        
        try:
            # Create steps using factory
            # Execute steps (implementation details from previous artifacts)
            # This would integrate with the execution logic from the main engine
            steps = self.factory.create_steps_from_config_list(steps_config)
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
            except Exception:
                raise


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
