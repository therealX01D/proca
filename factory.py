from typing import Optional,Callable,Dict,List
from .service_locator import ServiceLocator
from .registry import StepRegistry
from .core import StepConfiguration,StepValidationError,StepCreationError,Context
from .step import Step,StepType,StepResult
from functools import wraps
import importlib
import logging
import inspect

class StepFactory:
    """Advanced factory for creating steps from configuration"""
    
    def __init__(self, 
                 registry: StepRegistry,
                 service_locator: Optional['ServiceLocator'] = None):
        self.registry = registry
        self.service_locator = service_locator or ServiceLocator()
        self.logger = logging.getLogger("step_factory")
        self._creation_strategies: Dict[str, Callable] = {}
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """Setup default creation strategies"""
        self._creation_strategies.update({
            "class_instantiation": self._create_by_class_instantiation,
            "builder_pattern": self._create_by_builder_pattern,
            "prototype_pattern": self._create_by_prototype,
            "dependency_injection": self._create_with_dependency_injection
        })
    
    def create_step(self, config: StepConfiguration) -> Step:
        """Create a step instance from configuration"""
        
        self.logger.debug(f"Creating step: {config.name} (type: {config.type})")
        
        try:
            # Validate configuration
            self._validate_configuration(config)
            
            # Determine creation strategy
            strategy = self._determine_creation_strategy(config)
            
            # Create the step
            step = strategy(config)
            
            # Post-process the step
            step = self._post_process_step(step, config)
            
            self.logger.info(f"Successfully created step: {config.name}")
            return step
            
        except Exception as e:
            self.logger.error(f"Failed to create step {config.name}: {e}")
            raise StepCreationError(f"Failed to create step {config.name}: {e}") from e
    
    def create_steps_from_config_list(self, configs: List[Dict]) -> List[Step]:
        """Create multiple steps from configuration list"""
        steps = []
        
        for config_dict in configs:
            try:
                config = self._parse_configuration(config_dict)
                step = self.create_step(config)
                steps.append(step)
            except Exception as e:
                self.logger.error(f"Failed to create step from config {config_dict}: {e}")
                raise
        
        return steps
    
    def _validate_configuration(self, config: StepConfiguration) -> None:
        """Validate step configuration against schema"""
        
        # Check if step type exists
        if not self.registry._steps.get(config.type) and not self.registry._aliases.get(config.type):
            available = list(self.registry._steps.keys()) + list(self.registry._aliases.keys())
            raise StepValidationError(
                f"Unknown step type: {config.type}. Available: {', '.join(sorted(available))}"
            )
        
        # Validate against schema
        try:
            metadata = self.registry.get_metadata(config.type)
            schema = metadata.configuration_schema
            
            # Basic schema validation (in production, use jsonschema library)
            if "required" in schema:
                for required_field in schema["required"]:
                    if required_field not in config.parameters:
                        raise StepValidationError(
                            f"Missing required parameter '{required_field}' for step {config.name}"
                        )
        
        except Exception as e:
            raise StepValidationError(f"Configuration validation failed: {e}")
    
    def _determine_creation_strategy(self, config: StepConfiguration) -> Callable:
        """Determine the best creation strategy for the step"""
        
        # Check for explicit strategy in config
        if "creation_strategy" in config.custom_config:
            strategy_name = config.custom_config["creation_strategy"]
            if strategy_name in self._creation_strategies:
                return self._creation_strategies[strategy_name]
        
        # Default strategy based on step complexity
        metadata = self.registry.get_metadata(config.type)
        
        if metadata.required_services:
            return self._creation_strategies["dependency_injection"]
        elif config.parameters:
            return self._creation_strategies["class_instantiation"]
        else:
            return self._creation_strategies["class_instantiation"]
    
    def _create_by_class_instantiation(self, config: StepConfiguration) -> Step:
        """Create step by direct class instantiation"""
        
        step_class = self.registry.get_step_class(config.type)
        
        # Prepare constructor arguments
        init_args = {
            "step_id": config.name,
            "step_type": StepType(config.type) if config.type in [t.value for t in StepType] else StepType.COMMAND
        }
        
        # Add configured parameters
        init_args.update(config.parameters)
        
        # Filter args to match constructor signature
        sig = inspect.signature(step_class.__init__)
        filtered_args = {k: v for k, v in init_args.items() if k in sig.parameters}
        
        return step_class(**filtered_args)
    
    def _create_with_dependency_injection(self, config: StepConfiguration) -> Step:
        """Create step with dependency injection"""
        
        step_class = self.registry.get_step_class(config.type)
        metadata = self.registry.get_metadata(config.type)
        
        # Resolve dependencies
        dependencies = {}
        for service_name in metadata.required_services:
            try:
                service = self.service_locator.get_service(service_name)
                dependencies[service_name] = service
            except Exception as e:
                raise StepCreationError(f"Failed to resolve service {service_name}: {e}")
        
        # Combine dependencies with parameters
        init_args = {
            "step_id": config.name,
            "step_type": StepType(config.type) if config.type in [t.value for t in StepType] else StepType.COMMAND,
            **dependencies,
            **config.parameters
        }
        
        # Filter args to match constructor signature
        sig = inspect.signature(step_class.__init__)
        filtered_args = {k: v for k, v in init_args.items() if k in sig.parameters}
        
        return step_class(**filtered_args)
    
    def _create_by_builder_pattern(self, config: StepConfiguration) -> Step:
        """Create step using builder pattern"""
        
        # Look for builder class
        step_class = self.registry.get_step_class(config.type)
        builder_class_name = f"{step_class.__name__}Builder"
        
        try:
            # Try to find builder in same module
            module = importlib.import_module(step_class.__module__)
            builder_class = getattr(module, builder_class_name)
            
            builder = builder_class()
            builder.with_id(config.name)
            builder.with_type(StepType(config.type) if config.type in [t.value for t in StepType] else StepType.COMMAND)
            
            # Apply parameters
            for key, value in config.parameters.items():
                method_name = f"with_{key}"
                if hasattr(builder, method_name):
                    getattr(builder, method_name)(value)
            
            return builder.build()
            
        except (ImportError, AttributeError):
            # Fallback to direct instantiation
            self.logger.warning(f"Builder not found for {step_class}, falling back to direct instantiation")
            return self._create_by_class_instantiation(config)
    
    def _create_by_prototype(self, config: StepConfiguration) -> Step:
        """Create step using prototype pattern"""
        
        # This would be used for steps that are expensive to initialize
        # and can be cloned from a prototype
        
        prototype_key = f"{config.type}_prototype"
        
        if hasattr(self, prototype_key):
            prototype = getattr(self, prototype_key)
            # Clone the prototype (implementation depends on step design)
            cloned_step = prototype.clone() if hasattr(prototype, 'clone') else prototype
            cloned_step.step_id = config.name
            return cloned_step
        else:
            # No prototype available, use regular instantiation
            return self._create_by_class_instantiation(config)
    
    def _post_process_step(self, step: Step, config: StepConfiguration) -> Step:
        """Apply post-processing to the created step"""
        
        # Apply retry configuration
        if config.retry_config:
            step.retry_count = config.retry_config.get("max_attempts", 0)
        
        # Set timeout if specified
        if config.timeout_seconds:
            step.timeout_seconds = config.timeout_seconds
        
        # Apply decorators based on configuration
        if config.critical:
            step = self._apply_critical_step_decorator(step)
        
        if config.parallel_execution:
            step = self._apply_parallel_execution_decorator(step)
        
        if config.compensation_required:
            step.requires_compensation = True
        
        return step
    
    def _apply_critical_step_decorator(self, step: Step) -> Step:
        """Apply critical step decorator"""
        
        original_execute = step.execute
        
        @wraps(original_execute)
        async def critical_execute(context: Context) -> StepResult:
            try:
                result = await original_execute(context)
                if not result.success:
                    # Critical step failure - add special handling
                    result.metadata = result.metadata or {}
                    result.metadata["critical_failure"] = True
                    self.logger.critical(f"Critical step {step.step_id} failed: {result.error}")
                return result
            except Exception as e:
                self.logger.critical(f"Critical step {step.step_id} threw exception: {e}")
                raise
        
        step.execute = critical_execute
        return step
    
    def _apply_parallel_execution_decorator(self, step: Step) -> Step:
        """Apply parallel execution decorator"""
        step.parallel_execution = True
        return step
    
    def _parse_configuration(self, config_dict: Dict) -> StepConfiguration:
        """Parse configuration dictionary into StepConfiguration object"""
        
        return StepConfiguration(
            name=config_dict["name"],
            type=config_dict["type"],
            step_class=config_dict.get("step_class"),
            dependencies=config_dict.get("dependencies", []),
            required_context=config_dict.get("required_context", []),
            optional_context=config_dict.get("optional_context", []),
            parameters=config_dict.get("parameters", {}),
            retry_config=config_dict.get("retry", {}),
            timeout_seconds=config_dict.get("timeout_seconds"),
            compensation_required=config_dict.get("compensation_required", False),
            parallel_execution=config_dict.get("parallel_execution", False),
            async_execution=config_dict.get("async_execution", False),
            optional=config_dict.get("optional", False),
            critical=config_dict.get("critical", False),
            validation_rules=config_dict.get("validation_rules", []),
            custom_config=config_dict.get("custom_config", {})
        )
    
    def register_creation_strategy(self, name: str, strategy: Callable):
        """Register a custom creation strategy"""
        self._creation_strategies[name] = strategy
