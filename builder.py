from typing import Optional,Dict,Any
from abc import abstractmethod,ABC
from .step import Step,StepType
class StepBuilder(ABC):
    """Abstract base class for step builders"""
    
    def __init__(self):
        self._step_id: Optional[str] = None
        self._step_type: Optional[StepType] = None
        self._parameters: Dict[str, Any] = {}
    
    def with_id(self, step_id: str) -> 'StepBuilder':
        self._step_id = step_id
        return self
    
    def with_type(self, step_type: StepType) -> 'StepBuilder':
        self._step_type = step_type
        return self
    
    def with_parameter(self, key: str, value: Any) -> 'StepBuilder':
        self._parameters[key] = value
        return self
    
    @abstractmethod
    def build(self) -> Step:
        """Build the step instance"""
        pass

# class DatabaseStepBuilder(StepBuilder):
#     """Builder for database-related steps"""
    
#     def __init__(self):
#         super().__init__()
#         self._connection_string: Optional[str] = None
#         self._query: Optional[str] = None
#         self._timeout: Optional[int] = None
#         self._transaction_required: bool = False
    
#     def with_connection_string(self, connection_string: str) -> 'DatabaseStepBuilder':
#         self._connection_string = connection_string
#         return self
    
#     def with_query(self, query: str) -> 'DatabaseStepBuilder':
#         self._query = query
#         return self
    
#     def with_timeout(self, timeout: int) -> 'DatabaseStepBuilder':
#         self._timeout = timeout
#         return self
    
#     def with_transaction(self, required: bool = True) -> 'DatabaseStepBuilder':
#         self._transaction_required = required
#         return self
    
#     def build(self) -> Step:
        """Build database step"""
        # from .database_steps import DatabaseStep  # Import specific implementation
        
        # return DatabaseStep(
        #     step_id=self._step_id,
        #     step_type=self._step_type,
        #     connection_string=self._connection_string,
        #     query=self._query,
        #     timeout=self._timeout,
        #     transaction_required=self._transaction_required,
        #     **self._parameters
        # )
