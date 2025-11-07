from indexer.zoekt_client import ZoektClient
from ai.workflows.error_analysis_graph import ErrorAnalysisWorkflow, WorkflowConfig
from dotenv import load_dotenv
import os
from ai.services.ai_service import AIService

load_dotenv()
primary_model_name = os.getenv("AI_NAME")
def getErrorAnalysisWorkflow():
    if (not primary_model_name):
        return
    workflow_config = WorkflowConfig(
        primary_model=primary_model_name
    )

    zoekt = ZoektClient("http://localhost:6070")
    workflow = ErrorAnalysisWorkflow(workflow_config)
    workflow.setup(zoekt)
    return workflow

    