"""
Agent package for Prospect-to-Lead workflow.
"""

from agents.base_agent import BaseAgent
from agents.graph_builder import GraphBuilder
from agents.execution_engine import ExecutionEngine
from agents.agent_factory import create_agent, register_agent, get_agent_registry

# Import all agent implementations
from agents.prospect_search_agent import ProspectSearchAgent
from agents.data_enrichment_agent import DataEnrichmentAgent
from agents.scoring_agent import ScoringAgent
from agents.apollo_contact_sync_agent import ApolloContactSyncAgent
from agents.outreach_content_agent import OutreachContentAgent
from agents.outreach_executor_agent import OutreachExecutorAgent
from agents.response_tracker_agent import ResponseTrackerAgent
from agents.feedback_trainer_agent import FeedbackTrainerAgent

# Register all agents
register_agent("ProspectSearchAgent", ProspectSearchAgent)
register_agent("DataEnrichmentAgent", DataEnrichmentAgent)
register_agent("ScoringAgent", ScoringAgent)
register_agent("ApolloContactSyncAgent", ApolloContactSyncAgent)
register_agent("OutreachContentAgent", OutreachContentAgent)
register_agent("OutreachExecutorAgent", OutreachExecutorAgent)
register_agent("ResponseTrackerAgent", ResponseTrackerAgent)
register_agent("FeedbackTrainerAgent", FeedbackTrainerAgent)

__all__ = [
    "BaseAgent",
    "GraphBuilder",
    "ExecutionEngine",
    "create_agent",
    "register_agent",
    "get_agent_registry",
    "ProspectSearchAgent",
    "DataEnrichmentAgent",
    "ScoringAgent",
    "ApolloContactSyncAgent",
    "OutreachContentAgent",
    "OutreachExecutorAgent",
    "ResponseTrackerAgent",
    "FeedbackTrainerAgent"
]
