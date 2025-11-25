"""
GraphBuilder: Dynamically builds LangGraph from workflow.json.
"""

from typing import Dict, Any, List, Callable, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph
from configs.workflow_loader import WorkflowLoader
from agents.base_agent import BaseAgent


class GraphBuilder:
    """
    Builds LangGraph workflow from workflow.json configuration.
    
    Handles:
    - Dynamic node creation from agent configs
    - Edge creation based on dependencies
    - Conditional branching
    - State management
    """
    
    def __init__(
        self,
        workflow_loader: WorkflowLoader,
        agent_factory: Callable[[str, Dict[str, Any], Any, Any], BaseAgent],
        secrets_provider: Any,
        logger: Optional[Any] = None
    ):
        """
        Initialize graph builder.
        
        Args:
            workflow_loader: WorkflowLoader instance
            agent_factory: Function to create agent instances
            secrets_provider: SecretsProvider instance
            logger: RunLogger instance (optional)
        """
        self.workflow_loader = workflow_loader
        self.agent_factory = agent_factory
        self.secrets_provider = secrets_provider
        self.logger = logger
        self.workflow = None
        self.graph = None
        self.agents = {}
    
    def build_graph(self, apply_overrides: bool = True) -> CompiledGraph:
        """
        Build LangGraph from workflow configuration.
        
        Args:
            apply_overrides: Whether to apply overrides.json
            
        Returns:
            Compiled LangGraph
        """
        # Load workflow
        self.workflow = self.workflow_loader.get_workflow(apply_overrides=apply_overrides)
        
        # Create state graph with dict-based state (LangGraph supports dict states)
        graph = StateGraph(dict)
        
        # Create nodes for each agent
        agent_order = self.workflow_loader.get_agent_order()
        
        for agent_name in agent_order:
            agent_config = self.workflow_loader.get_agent_config(agent_name)
            if agent_config:
                # Create agent instance
                agent = self.agent_factory(
                    agent_name,
                    agent_config,
                    self.secrets_provider,
                    self.logger
                )
                self.agents[agent_name] = agent
                
                # Add node to graph
                graph.add_node(agent_name, self._create_node_wrapper(agent))
        
        # Set entry point (first agent with no dependencies)
        entry_point = None
        for agent_name in agent_order:
            agent_config = self.workflow_loader.get_agent_config(agent_name)
            dependencies = agent_config.get("dependencies", [])
            if not dependencies:
                entry_point = agent_name
                break
        
        if entry_point:
            graph.set_entry_point(entry_point)
        
        # Add edges based on dependencies
        for agent_name in agent_order:
            agent_config = self.workflow_loader.get_agent_config(agent_name)
            dependencies = agent_config.get("dependencies", [])
            
            if dependencies:
                # Add edges from dependencies
                for dep in dependencies:
                    conditional = agent_config.get("conditional_branching")
                    
                    if conditional:
                        # Add conditional edge
                        graph.add_conditional_edges(
                            dep,
                            self._create_condition_checker(agent_config),
                            {
                                "continue": agent_name,
                                "skip": self._get_next_agent(agent_name, agent_order)
                            }
                        )
                    else:
                        # Add regular edge
                        graph.add_edge(dep, agent_name)
            
            # Check if this is the last agent
            if agent_name == agent_order[-1]:
                graph.add_edge(agent_name, END)
        
        # Compile graph
        self.graph = graph.compile()
        return self.graph
    
    def _create_node_wrapper(self, agent: BaseAgent) -> Callable:
        """
        Create a wrapper function for agent execution in LangGraph.
        
        Args:
            agent: Agent instance
            
        Returns:
            Node function for LangGraph
        """
        def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            """Execute agent and return updated state."""
            run_id = state.get("run_id")
            return agent.execute(state, run_id=run_id)
        
        return node_function
    
    def _create_condition_checker(
        self,
        agent_config: Dict[str, Any]
    ) -> Callable:
        """
        Create conditional edge checker function.
        
        Args:
            agent_config: Agent configuration
            
        Returns:
            Condition checker function
        """
        conditional = agent_config.get("conditional_branching", {})
        action = conditional.get("action", "skip_next")
        
        def check_condition(state: Dict[str, Any]) -> str:
            """Check condition and return next node."""
            agent = self.agents.get(agent_config["name"])
            if agent and agent.check_condition(state):
                return "continue"
            else:
                return "skip"
        
        return check_condition
    
    def _get_next_agent(self, current_agent: str, agent_order: List[str]) -> str:
        """
        Get next agent in execution order.
        
        Args:
            current_agent: Current agent name
            agent_order: Ordered list of agent names
            
        Returns:
            Next agent name or END
        """
        try:
            current_idx = agent_order.index(current_agent)
            if current_idx < len(agent_order) - 1:
                return agent_order[current_idx + 1]
        except ValueError:
            pass
        
        return END
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get agent instance by name.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Agent instance or None
        """
        return self.agents.get(agent_name)
    
    def get_workflow(self) -> Dict[str, Any]:
        """Get workflow configuration."""
        return self.workflow or self.workflow_loader.get_workflow()

