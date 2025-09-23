from typing import Dict , Any , Callable, List
import logging
class ServiceLocator:
    """Service locator for dependency injection"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self.logger = logging.getLogger("service_locator")
    
    def register_service(self, name: str, service: Any) -> None:
        """Register a service instance"""
        self._services[name] = service
        self.logger.debug(f"Registered service: {name}")
    
    def register_factory(self, name: str, factory: Callable, singleton: bool = False) -> None:
        """Register a service factory"""
        self._factories[name] = factory
        if singleton:
            self._singletons[name] = None
        self.logger.debug(f"Registered factory: {name} (singleton: {singleton})")
    
    def get_service(self, name: str) -> Any:
        """Get service by name"""
        
        # Check direct services first
        if name in self._services:
            return self._services[name]
        
        # Check factories
        if name in self._factories:
            # Handle singletons
            if name in self._singletons:
                if self._singletons[name] is None:
                    self._singletons[name] = self._factories[name]()
                return self._singletons[name]
            else:
                return self._factories[name]()
        
        raise ValueError(f"Service not found: {name}")
    
    def list_services(self) -> List[str]:
        """List all available services"""
        return list(self._services.keys()) + list(self._factories.keys())
