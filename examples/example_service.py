class CustomService:
    """Example custom service"""
    
    def process_data(self, data):
        return {"processed": data}

class ExternalApiClient:
    """Example API client"""
    
    async def call_api(self, endpoint, data):
        return {"status": "success", "data": data}
