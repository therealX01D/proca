from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import inspect
import importlib
import logging
from functools import wraps

# Import our base classes (assumed from previous artifact)
from business_logic_engine import Step, StepType, StepResult, Context

# class ExamplePlugin(StepPlugin):
#     """Example plugin implementation"""
    
#     def get_plugin_name(self) -> str:
#         return "example_plugin"
    
#     def get_step_classes(self) -> Dict[str, Type[Step]]:
#         # This would return actual step classes
#         return {
#             "custom_validation": CustomValidationStep,
#             "external_api": ExternalApiStep
#         }
    
#     def get_services(self) -> Dict[str, Any]:
#         return {
#             "custom_service": CustomService(),
#             "api_client": ExternalApiClient()
#         }

# # Mock step classes for the example
# class CustomValidationStep(Step):
#     """Example custom validation step"""
    
#     async def execute(self, context: Context) -> StepResult:
#         # Custom validation logic
#         return StepResult(success=True, data={"validated": True})

# class ExternalApiStep(Step):
#     """Example external API step"""
    
#     def __init__(self, step_id: str, step_type: StepType, api_client):
#         super().__init__(step_id, step_type)
#         self.api_client = api_client
    
#     async def execute(self, context: Context) -> StepResult:
#         # External API call logic
#         return StepResult(success=True, data={"api_response": "success"})

# class CustomService:
#     """Example custom service"""
    
#     def process_data(self, data):
#         return {"processed": data}

# class ExternalApiClient:
#     """Example API client"""
    
#     async def call_api(self, endpoint, data):
#         return {"status": "success", "data": data}

# # =====================================================
# # COMPREHENSIVE USAGE EXAMPLE
# # =====================================================

# async def demonstrate_factory_system():
#     """Comprehensive demonstration of the factory system"""
    
#     print("Step Factory System Demonstration")
#     print("=" * 50)
    
#     # 1. Setup the system
#     service_locator = ServiceLocator()
#     engine = EnhancedProcessEngine(service_locator=service_locator)
    
#     # 2. Register some services
#     service_locator.register_service("email_service", MockEmailService())
#     service_locator.register_service("database_service", MockDatabaseService())
#     service_locator.register_service("http_client", MockHttpClient())
    
#     print(" System initialized with default steps and services")
    
#     # 3. Show available steps
#     available_steps = engine.get_available_steps()
#     print(f"\nAvailable Steps ({len(available_steps)}):")
#     for name, info in available_steps.items():
#         print(f"  {name}: {info['description']} (category: {info['category']})")
    
#     # 4. Load a plugin
#     plugin = ExamplePlugin()
#     engine.load_plugin(plugin)
#     print(f"\n Loaded plugin: {plugin.get_plugin_name()}")
    
#     # 5. Create steps from configuration
#     step_configs = [
#         {
#             "name": "validate_input",
#             "type": "validation",
#             "parameters": {
#                 "validation_func": "validate_email"
#             }
#         },
#         {
#             "name": "save_to_db",
#             "type": "database",
#             "dependencies": ["validate_input"],
#             "parameters": {
#                 "query": "INSERT INTO users (email) VALUES (?)",
#                 "transaction_required": True
#             }
#         },
#         {
#             "name": "send_welcome",
#             "type": "email",
#             "dependencies": ["save_to_db"],
#             "parameters": {
#                 "template": "welcome_email"
#             }
#         },
#         {
#             "name": "custom_step",
#             "type": "custom_validation",  # From plugin
#             "dependencies": []
#         }
#     ]
    
#     print(f"\n Creating {len(step_configs)} steps from configuration...")
    
#     steps = engine.factory.create_steps_from_config_list(step_configs)
    
#     for step in steps:
#         print(f"   Created: {step.step_id} ({type(step).__name__})")
    
#     # 6. Show step metadata
#     print(f"\n Step Metadata Examples:")
#     for step_name in ["validation", "database", "email"]:
#         metadata = engine.registry.get_metadata(step_name)
#         print(f"  • {step_name}:")
#         print(f"    - Required services: {metadata.required_services}")
#         print(f"    - Supported types: {[t.value for t in metadata.supported_types]}")
#         print(f"    - Schema: {metadata.configuration_schema}")
    
#     print(f"\n Factory system demonstration completed!")

# # Mock services for demonstration
# class MockEmailService:
#     async def send_email(self, template, recipient, data):
#         print(f" Sent email using template '{template}' to {recipient}")

# class MockDatabaseService:
#     async def execute_query(self, query, parameters=None, transaction=False):
#         print(f"  Executed query: {query} (transaction: {transaction})")
#         return {"affected_rows": 1}

# class MockHttpClient:
#     async def request(self, method, url, headers=None, timeout=30):
#         print(f" HTTP {method} request to {url}")
#         return {"status": 200, "data": {"success": True}}

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(demonstrate_factory_system())