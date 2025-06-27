import asyncio
from ai import AIService

async def main():
    # Model configurations for xai (add openai if needed)
    model_configs = {
        "xai": {
            "name": "grok-3-latest",
            "endpoint": "https://api.x.ai/v1/chat/completions",
            "api_key": "your-xai-key"
        }
        # Add more models here if needed
    }

    # Initialize AIService
    ai_service = AIService(
        tenant_id="tenant1",
        redis_url="redis://localhost:6379",
        model_configs=model_configs,
        primary_model="xai"
    )

    # Example error message and code context
    error_message = "TypeError: 'NoneType' object is not subscriptable at line 45"
    code_context = """
    def process_data(data):
        result = data.get('items')  # Line 45
        return result[0]['name']
    """
    project_info = {
        "language": "Python",
        "framework": "Flask",
        "version": "3.9"
    }

    # Run debug and fix pipeline
    result = await ai_service.debug_and_fix(
        error_message=error_message,
        code_context=code_context,
        project_info=project_info
    )

    print("AI Debug Analysis:", result["analysis"])
    print("Model Used:", result["model_used"])
    print("Latency (s):", result["latency"])

if __name__ == "__main__":
    asyncio.run(main()) 