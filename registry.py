"""Step registry / plugin pattern for constructing Steps by name.

Register step constructors (callables) with a name. A constructor is expected to
be a callable that accepts at least (step_id: str, **params) and returns an instance
of a subclass of processor.step.Step.

Example:
    @registry.register("validation")
    def build_validation(step_id, validation_func=None, **kwargs):
        return ValidationStep(step_id, validation_func or (lambda ctx: True))

Or programmatically:
    registry.register("my_custom", my_builder)
    builder = registry.get("my_custom")
    step = builder("my_step", some_param=123)
"""

from typing import Callable, Dict, Any, Optional, Iterable
import threading

class StepRegistryError(Exception):
    pass

class StepRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._registry: Dict[str, Callable[..., object]] = {}

    def register(self, name: str, constructor: Optional[Callable[..., object]] = None):
        """Register a constructor under `name`.

        Can be used as a decorator:
            @registry.register("validation")
            def make_validation(step_id, **params): ...
        Or called directly:
            registry.register("validation", make_validation)
        """
        if constructor is None:
            # used as decorator
            def _decorator(func: Callable[..., object]):
                self._do_register(name, func)
                return func
            return _decorator
        else:
            self._do_register(name, constructor)
            return constructor

    def _do_register(self, name: str, constructor: Callable[..., object]):
        with self._lock:
            if name in self._registry:
                raise StepRegistryError(f"Step constructor already registered under name '{name}'")
            self._registry[name] = constructor

    def unregister(self, name: str):
        with self._lock:
            if name in self._registry:
                del self._registry[name]

    def get(self, name: str) -> Callable[..., object]:
        with self._lock:
            if name not in self._registry:
                raise StepRegistryError(f"No step constructor registered under name '{name}'")
            return self._registry[name]

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._registry

    def list(self) -> Iterable[str]:
        with self._lock:
            return list(self._registry.keys())

# single shared registry instance
registry = StepRegistry()

# --- Register default step constructors for the package built-ins ---
# We import locally to avoid top-level circular imports when package imported.
def _register_builtin_steps():
    from .steps.validation import ValidationStep
    from .steps.command import CommandStep
    from .steps.query import QueryStep

    # validation: allow user to pass 'validation_func' in params
    @registry.register("validation")
    def _make_validation(step_id: str, validation_func=None, **params):
        if validation_func is None:
            # default to always-true validation if not provided
            validation_func = lambda ctx: True
        return ValidationStep(step_id, validation_func)

    # command: accepts 'command_func', optional 'dependencies', 'retry_count'
    @registry.register("command")
    def _make_command(step_id: str, command_func=None, dependencies=None, retry_count: int = 0, **params):
        if command_func is None:
            raise StepRegistryError("command steps require 'command_func' in params")
        return CommandStep(step_id, command_func, dependencies=dependencies or [], retry_count=retry_count)

    # query: accepts 'query_func'
    @registry.register("query")
    def _make_query(step_id: str, query_func=None, **params):
        if query_func is None:
            raise StepRegistryError("query steps require 'query_func' in params")
        return QueryStep(step_id, query_func)

    # side_effect: map to CommandStep by default (user may register their own)
    @registry.register("side_effect")
    def _make_side_effect(step_id: str, command_func=None, dependencies=None, retry_count: int = 0, **params):
        if command_func is None:
            # graceful default: a no-op command
            async def _noop(ctx): 
                return {"executed": True}
            command_func = _noop
        return CommandStep(step_id, command_func, dependencies=dependencies or [], retry_count=retry_count)

# Initialize built-ins on import
try:
    _register_builtin_steps()
except Exception:
    # don't raise at import-time in hostile environments; re-raise if registration used incorrectly later.
    pass
