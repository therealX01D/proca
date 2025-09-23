from abc import ABC, abstractmethod
import logging
from typing import Dict,Type, Any, List
from .step import Step,StepType
from .registry import StepRegistry,StepMetadata
from .service_locator import ServiceLocator

class StepPlugin(ABC):
    """Interface for step plugins"""
    
    @abstractmethod
    def get_plugin_name(self) -> str:
        """Get plugin name"""
        pass
    
    @abstractmethod
    def get_step_classes(self) -> Dict[str, Type[Step]]:
        """Get step classes provided by this plugin"""
        pass
    
    @abstractmethod
    def get_services(self) -> Dict[str, Any]:
        """Get services provided by this plugin"""
        pass
    
    def initialize(self, service_locator: ServiceLocator) -> None:
        """Initialize plugin with service locator"""
        pass

class PluginManager:
    """Manages step plugins"""
    
    def __init__(self, registry: StepRegistry, service_locator: ServiceLocator):
        self.registry = registry
        self.service_locator = service_locator
        self.plugins: Dict[str, StepPlugin] = {}
        self.logger = logging.getLogger("plugin_manager")
    
    def load_plugin(self, plugin: StepPlugin) -> None:
        """Load a step plugin"""
        
        plugin_name = plugin.get_plugin_name()
        
        if plugin_name in self.plugins:
            self.logger.warning(f"Plugin {plugin_name} already loaded, replacing...")
        
        try:
            # Initialize plugin
            plugin.initialize(self.service_locator)
            
            # Register step classes
            step_classes = plugin.get_step_classes()
            for step_name, step_class in step_classes.items():
                metadata = StepMetadata(
                    step_class=step_class,
                    description=f"Step from plugin {plugin_name}",
                    category=f"plugin_{plugin_name}",
                    supported_types=[StepType.COMMAND],  # Default
                    required_services=[]
                )
                self.registry.register(step_name, step_class, metadata)
            
            # Register services
            services = plugin.get_services()
            for service_name, service in services.items():
                self.service_locator.register_service(f"{plugin_name}_{service_name}", service)
            
            self.plugins[plugin_name] = plugin
            
            self.logger.info(f"Successfully loaded plugin: {plugin_name}")
            self.logger.info(f"  - Steps: {list(step_classes.keys())}")
            self.logger.info(f"  - Services: {list(services.keys())}")
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            raise
    
    def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin"""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")
        
        # This would require more complex cleanup in a real implementation
        del self.plugins[plugin_name]
        self.logger.info(f"Unloaded plugin: {plugin_name}")
    
    def list_plugins(self) -> List[str]:
        """List loaded plugins"""
        return list(self.plugins.keys())
