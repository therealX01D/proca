from abc import ABC, abstractmethod
from .core import Context
from typing import Any

class FrameworkAdapter(ABC):
    @abstractmethod
    def extract_context(self, request: Any) -> Context:
        pass

    @abstractmethod
    def format_response(self, context: Context, result: Any) -> Any:
        pass

class DjangoAdapter(FrameworkAdapter):
    def extract_context(self, request) -> Context:
        context = Context()
        context.user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else None
        context.data = request.data if hasattr(request, 'data') else {}
        context.metadata = {
            "method": getattr(request, "method", None),
            "path": getattr(request, "path", None),
            "remote_addr": request.META.get('REMOTE_ADDR') if getattr(request, "META", None) else None
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
