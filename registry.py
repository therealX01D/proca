from dataclasses import dataclass, field
from typing import Dict, List, Any,Optional,Type
from .step import Step,StepType
from .core import StepCreationError
import inspect
import logging
@dataclass
class StepMetadata:
    """Metadata about a step class"""
    step_class: Type[Step]
    description: str
    category: str
    supported_types: List[StepType]
    required_services: List[str]
    configuration_schema: Dict[str, Any]
    examples: List[Dict] = field(default_factory=list)
    version: str = "1.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)

class StepRegistry:
    """Central registry for all available step types"""
    
    def __init__(self):
        self._steps: Dict[str, StepMetadata] = {}
        self._aliases: Dict[str, str] = {}
        self._categories: Dict[str, List[str]] = {}
        self.logger = logging.getLogger("step_registry")
    
    def register(self, 
                 name: str, 
                 step_class: Type[Step],
                 metadata: Optional[StepMetadata] = None,
                 aliases: List[str] = None) -> None:
        """Register a step class with optional metadata"""
        
        if name in self._steps:
            self.logger.warning(f"Overriding existing step registration: {name}")
        
        # Create default metadata if not provided
        if metadata is None:
            metadata = StepMetadata(
                step_class=step_class,
                description=step_class.__doc__ or f"Step implementation: {name}",
                category="custom",
                supported_types=[StepType.COMMAND],  # Default assumption
                required_services=[],
                configuration_schema=self._extract_schema_from_class(step_class)
            )
        
        self._steps[name] = metadata
        
        # Register aliases
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name
        
        # Update categories
        category = metadata.category
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        
        self.logger.info(f"Registered step: {name} (category: {category})")
    
    def get_step_class(self, name: str) -> Type[Step]:
        """Get step class by name or alias"""
        # Check aliases first
        actual_name = self._aliases.get(name, name)
        
        if actual_name not in self._steps:
            available = list(self._steps.keys()) + list(self._aliases.keys())
            raise StepCreationError(
                f"Unknown step type: {name}. Available: {', '.join(sorted(available))}"
            )
        
        return self._steps[actual_name].step_class
    
    def get_metadata(self, name: str) -> StepMetadata:
        """Get step metadata by name"""
        actual_name = self._aliases.get(name, name)
        if actual_name not in self._steps:
            raise StepCreationError(f"Unknown step type: {name}")
        return self._steps[actual_name]
    
    def list_steps(self, category: Optional[str] = None) -> List[str]:
        """List all registered steps, optionally filtered by category"""
        if category:
            return self._categories.get(category, [])
        return list(self._steps.keys())
    
    def list_categories(self) -> List[str]:
        """List all step categories"""
        return list(self._categories.keys())
    
    def validate_step_type(self, name: str, step_type: StepType) -> bool:
        """Validate if step supports the given type"""
        metadata = self.get_metadata(name)
        return step_type in metadata.supported_types
    
    def _extract_schema_from_class(self, step_class: Type[Step]) -> Dict[str, Any]:
        """Extract configuration schema from step class"""
        schema = {"type": "object", "properties": {}}
        
        # Inspect __init__ method for parameters
        try:
            sig = inspect.signature(step_class.__init__)
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'step_id', 'step_type']:
                    continue
                
                param_schema = {"type": "string"}  # Default
                
                # Try to infer type from annotation
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_schema = {"type": "integer"}
                    elif param.annotation == float:
                        param_schema = {"type": "number"}
                    elif param.annotation == bool:
                        param_schema = {"type": "boolean"}
                    elif param.annotation == list:
                        param_schema = {"type": "array"}
                    elif param.annotation == dict:
                        param_schema = {"type": "object"}
                
                # Check if required (no default value)
                if param.default == inspect.Parameter.empty:
                    schema.setdefault("required", []).append(param_name)
                else:
                    param_schema["default"] = param.default
                
                schema["properties"][param_name] = param_schema
        
        except Exception as e:
            self.logger.warning(f"Could not extract schema from {step_class}: {e}")
        
        return schema