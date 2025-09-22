from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Callable
from enum import Enum
import asyncio
import json
import yaml
import logging
from datetime import datetime
import uuid
from contextlib import contextmanager

# =====================================================
# CORE ABSTRACTIONS & INTERFACES
# =====================================================

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    COMPENSATED = "compensated"
class CircuitStatus(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN" 
    HALF_OPEN = "HALF_OPEN"
class StepType(Enum):
    COMMAND = "command"
    QUERY = "query"
    VALIDATION = "validation"
    SIDE_EFFECT = "side_effect"

@dataclass
class Context:
    """Shared context for step execution"""
    process_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_trace: List[Dict] = field(default_factory=list)

@dataclass
class StepResult:
    """Result of step execution"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StepExecution:
    """Record of step execution for audit/logging"""
    step_id: str
    process_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Any = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# =====================================================
# STEP INTERFACE & BASE IMPLEMENTATIONS
# =====================================================

class Step(ABC):
    """Base step interface implementing all patterns"""
    
    def __init__(self, step_id: str, step_type: StepType, retry_count: int = 0):
        self.step_id = step_id
        self.step_type = step_type
        self.retry_count = retry_count
        self.logger = logging.getLogger(f"step.{step_id}")
    
    @abstractmethod
    async def execute(self, context: Context) -> StepResult:
        """Execute the step logic"""
        pass
    
    async def validate(self, context: Context) -> bool:
        """Validate if step can be executed"""
        return True
    
    async def compensate(self, context: Context) -> StepResult:
        """Compensation logic for saga pattern"""
        return StepResult(success=True)
    
    def get_dependencies(self) -> List[str]:
        """Return list of step IDs this step depends on"""
        return []
    
    def get_required_context_keys(self) -> List[str]:
        """Return list of context keys required for execution"""
        return []

# =====================================================
# CONCRETE STEP IMPLEMENTATIONS (EXAMPLES)
# =====================================================

class ValidationStep(Step):
    """Example validation step"""
    
    def __init__(self, step_id: str, validation_func: Callable[[Context], bool]):
        super().__init__(step_id, StepType.VALIDATION)
        self.validation_func = validation_func
    
    async def execute(self, context: Context) -> StepResult:
        try:
            is_valid = self.validation_func(context)
            return StepResult(
                success=is_valid,
                data={"is_valid": is_valid},
                error=None if is_valid else f"Validation failed for {self.step_id}"
            )
        except Exception as e:
            return StepResult(success=False, error=str(e))

class CommandStep(Step):
    """Example command step for CQRS"""
    
    def __init__(self, step_id: str, command_func: Callable[[Context], Any], dependencies: List[str] = None):
        super().__init__(step_id, StepType.COMMAND)
        self.command_func = command_func
        self.dependencies = dependencies or []
    
    async def execute(self, context: Context) -> StepResult:
        try:
            result = await self._execute_with_retry(context)
            return StepResult(success=True, data=result)
        except Exception as e:
            return StepResult(success=False, error=str(e))
    
    async def _execute_with_retry(self, context: Context) -> Any:
        """Implement retry logic"""
        for attempt in range(self.retry_count + 1):
            try:
                if asyncio.iscoroutinefunction(self.command_func):
                    return await self.command_func(context)
                else:
                    return self.command_func(context)
            except Exception as e:
                if attempt == self.retry_count:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    def get_dependencies(self) -> List[str]:
        return self.dependencies

class QueryStep(Step):
    """Example query step for CQRS"""
    
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

# =====================================================
# EVENT SOURCING & LOGGING
# =====================================================

class EventStore:
    """Simple event store for audit logging"""
    
    def __init__(self):
        self.events: List[StepExecution] = []
    
    async def store_execution(self, execution: StepExecution):
        """Store step execution event"""
        self.events.append(execution)
    
    async def get_process_history(self, process_id: str) -> List[StepExecution]:
        """Get all events for a process"""
        return [e for e in self.events if e.process_id == process_id]
    
    async def replay_process(self, process_id: str) -> Context:
        """Replay process from events"""
        events = await self.get_process_history(process_id)
        context = Context(process_id=process_id)
        
        for event in sorted(events, key=lambda x: x.started_at):
            if event.status == ExecutionStatus.SUCCESS:
                # Replay successful steps to rebuild context
                context.data[f"{event.step_id}_result"] = event.output_data
        
        return context

# =====================================================
# CIRCUIT BREAKER PATTERN
# =====================================================

class CircuitBreaker:
    """Circuit breaker for step failure handling"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if datetime.now().timestamp() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now().timestamp()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

# =====================================================
# PROCESS ENGINE - THE ORCHESTRATOR
# =====================================================

class ProcessEngine:
    """Main orchestrator implementing all patterns"""
    
    def __init__(self, event_store: EventStore = None):
        self.event_store = event_store or EventStore()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = logging.getLogger("process_engine")
    
    async def execute_process(self, process_definition: Dict, context: Context) -> Context:
        """Execute a complete process with all patterns applied"""
        
        process_name = process_definition.get("name", "unnamed_process")
        steps_config = process_definition.get("steps", [])
        
        self.logger.info(f"Starting process {process_name} with ID {context.process_id}")
        
        # Build step instances from configuration
        steps = self._build_steps_from_config(steps_config)
        
        # Resolve execution order based on dependencies
        execution_order = self._resolve_dependencies(steps)
        
        executed_steps = []
        
        try:
            # Execute steps in order
            for step in execution_order:
                execution_record = await self._execute_step_with_patterns(step, context)
                
                if execution_record.status == ExecutionStatus.SUCCESS:
                    executed_steps.append(step)
                    # Update context with step result
                    context.data[f"{step.step_id}_result"] = execution_record.output_data
                else:
                    # Step failed - trigger compensation (Saga pattern)
                    self.logger.error(f"Step {step.step_id} failed: {execution_record.error_message}")
                    await self._compensate_executed_steps(executed_steps, context)
                    raise Exception(f"Process failed at step {step.step_id}: {execution_record.error_message}")
            
            self.logger.info(f"Process {process_name} completed successfully")
            return context
            
        except Exception as e:
            self.logger.error(f"Process {process_name} failed: {str(e)}")
            raise
    
    async def _execute_step_with_patterns(self, step: Step, context: Context) -> StepExecution:
        """Execute single step with all patterns applied"""
        
        # Circuit breaker check
        circuit_breaker = self._get_circuit_breaker(step.step_id)
        if not circuit_breaker.can_execute():
            execution_record = StepExecution(
                step_id=step.step_id,
                process_id=context.process_id,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                status=ExecutionStatus.FAILED,
                error_message="Circuit breaker is OPEN"
            )
            await self.event_store.store_execution(execution_record)
            return execution_record
        
        # Create execution record
        execution_record = StepExecution(
            step_id=step.step_id,
            process_id=context.process_id,
            started_at=datetime.now(),
            input_data=context.data.copy()
        )
        
        try:
            # Pre-execution validation
            if not await step.validate(context):
                raise Exception(f"Step validation failed for {step.step_id}")
            
            # Execute step
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
            
            # Store in event store
            await self.event_store.store_execution(execution_record)
            
            # Add to context trace
            context.execution_trace.append({
                "step_id": step.step_id,
                "status": execution_record.status.value,
                "timestamp": execution_record.completed_at.isoformat()
            })
        
        return execution_record
    
    async def _compensate_executed_steps(self, executed_steps: List[Step], context: Context):
        """Implement saga compensation pattern"""
        self.logger.info("Starting compensation for executed steps")
        
        # Compensate in reverse order
        for step in reversed(executed_steps):
            try:
                compensation_result = await step.compensate(context)
                if compensation_result.success:
                    self.logger.info(f"Successfully compensated step {step.step_id}")
                else:
                    self.logger.error(f"Failed to compensate step {step.step_id}: {compensation_result.error}")
            except Exception as e:
                self.logger.error(f"Exception during compensation of step {step.step_id}: {str(e)}")
    
    def _get_circuit_breaker(self, step_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for step"""
        if step_id not in self.circuit_breakers:
            self.circuit_breakers[step_id] = CircuitBreaker()
        return self.circuit_breakers[step_id]
    
    def _build_steps_from_config(self, steps_config: List[Dict]) -> List[Step]:
        """Build step instances from configuration"""
        # This is a simplified implementation
        # In real implementation, you'd have step factories/registries
        steps = []
        for config in steps_config:
            step_type = StepType(config["type"])
            step_id = config["name"]
            
            # Example step creation - you'd extend this
            if step_type == StepType.VALIDATION:
                step = ValidationStep(step_id, lambda ctx: True)  # Placeholder
            elif step_type == StepType.COMMAND:
                step = CommandStep(step_id, lambda ctx: {"created": True}, config.get("dependencies", []))
            elif step_type == StepType.QUERY:
                step = QueryStep(step_id, lambda ctx: {"data": "queried"})
            else:
                step = CommandStep(step_id, lambda ctx: {"executed": True})
            
            steps.append(step)
        
        return steps
    
    def _resolve_dependencies(self, steps: List[Step]) -> List[Step]:
        """Topological sort based on dependencies"""
        # Simplified dependency resolution
        step_map = {step.step_id: step for step in steps}
        resolved = []
        unresolved = set(steps)
        
        while unresolved:
            for step in list(unresolved):
                deps = step.get_dependencies()
                if all(dep_id in [s.step_id for s in resolved] for dep_id in deps):
                    resolved.append(step)
                    unresolved.remove(step)
                    break
            else:
                # Circular dependency or unresolved dependency
                raise Exception("Circular dependency detected or unresolvable dependencies")
        
        return resolved

# =====================================================
# CONFIGURATION-DRIVEN PROCESS DEFINITION
# =====================================================

class ProcessDefinitionLoader:
    """Load process definitions from YAML/JSON"""
    
    @staticmethod
    def load_from_yaml(file_path: str) -> Dict:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    
    @staticmethod
    def load_from_json(file_path: str) -> Dict:
        with open(file_path, 'r') as file:
            return json.load(file)

# =====================================================
# FRAMEWORK INTEGRATION LAYER
# =====================================================

class FrameworkAdapter(ABC):
    """Abstract adapter for framework integration"""
    
    @abstractmethod
    def extract_context(self, request: Any) -> Context:
        """Extract context from framework request"""
        pass
    
    @abstractmethod
    def format_response(self, context: Context, result: Any) -> Any:
        """Format response for framework"""
        pass

class DjangoAdapter(FrameworkAdapter):
    """Django/DRF adapter"""
    
    def extract_context(self, request) -> Context:
        context = Context()
        context.user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else None
        context.data = request.data if hasattr(request, 'data') else {}
        context.metadata = {
            "method": request.method,
            "path": request.path,
            "remote_addr": request.META.get('REMOTE_ADDR')
        }
        return context
    
    def format_response(self, context: Context, result: Any):
        from rest_framework.response import Response
        return Response({
            "success": True,
            "data": result,
            "process_id": context.process_id,
            "execution_trace": context.execution_trace
        })

# =====================================================
# USAGE EXAMPLE
# =====================================================

async def main():
    """Example usage demonstrating all patterns working together"""
    
    # Setup
    event_store = EventStore()
    engine = ProcessEngine(event_store)
    
    # Example process definition
    process_definition = {
        "name": "user_registration",
        "steps": [
            {"name": "validate_email", "type": "validation", "dependencies": []},
            {"name": "create_user", "type": "command", "dependencies": ["validate_email"]},
            {"name": "send_welcome_email", "type": "side_effect", "dependencies": ["create_user"]}
        ]
    }
    
    # Create context
    context = Context()
    context.data = {"email": "user@example.com", "name": "John Doe"}
    
    try:
        # Execute process
        result_context = await engine.execute_process(process_definition, context)
        
        print("Process completed successfully!")
        print(f"Process ID: {result_context.process_id}")
        print(f"Final context data: {result_context.data}")
        print(f"Execution trace: {result_context.execution_trace}")
        
        # Show event store contents
        events = await event_store.get_process_history(result_context.process_id)
        print(f"\nEvent store contains {len(events)} events for this process")
        
    except Exception as e:
        print(f"Process failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())