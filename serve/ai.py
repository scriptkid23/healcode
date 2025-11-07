from indexer.zoekt_client import ZoektClient
from ai.workflows.error_analysis_graph import ErrorAnalysisWorkflow, WorkflowConfig
from dotenv import load_dotenv
import os
from ai.services.ai_service import AIService

load_dotenv()
primary_model_name = os.getenv("AI_NAME")
ai_model_name = os.getenv("AI_MODEL")
ai_endpoint = os.getenv("END_POINT")
ai_api_key = os.getenv("AI_API_KEY")

def getErrorAnalysisWorkflow():
    if (not primary_model_name):
        return
    workflow_config = WorkflowConfig(
        primary_model=primary_model_name
    )
    model_configs = {
        primary_model_name: {
            "name": ai_model_name,
            "endpoint": ai_endpoint,
            "api_key": ai_api_key
        }
    }
    ai_service = AIService(
        tenant_id="tenant1",
        redis_url="redis://localhost:6379",
        model_configs=model_configs,
        primary_model=primary_model_name,
    )

    zoekt = ZoektClient("http://localhost:6070")
    workflow = ErrorAnalysisWorkflow(workflow_config)
    workflow.setup(zoekt)
    return workflow

    