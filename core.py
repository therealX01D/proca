from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime
import uuid

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
    process_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_trace: List[Dict] = field(default_factory=list)

@dataclass
class StepResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StepExecution:
    step_id: str
    process_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Any = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
class StepCreationError(Exception):
    """Raised when step creation fails"""
    pass

class StepValidationError(Exception):
    """Raised when step configuration validation fails"""
    pass

@dataclass
class StepConfiguration:
    """Comprehensive step configuration"""
    name: str
    type: str
    step_class: Optional[str] = None  # Fully qualified class name
    dependencies: List[str] = field(default_factory=list)
    required_context: List[str] = field(default_factory=list)
    optional_context: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    retry_config: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[int] = None
    compensation_required: bool = False
    parallel_execution: bool = False
    async_execution: bool = False
    optional: bool = False
    critical: bool = False
    validation_rules: List[Dict] = field(default_factory=list)
    custom_config: Dict[str, Any] = field(default_factory=dict)
