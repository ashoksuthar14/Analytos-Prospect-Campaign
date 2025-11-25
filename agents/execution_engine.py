"""
Execution Engine: Manages campaign execution with state management.
"""

from typing import Dict, Any, Optional, Callable
import threading

try:
    from langgraph.graph.graph import CompiledGraph
except ImportError:
    raise ImportError("langgraph not installed. Install with: pip install langgraph")

from database.db_service import DatabaseService
from database.run_logger import RunLogger
from agents.graph_builder import GraphBuilder
from configs.workflow_loader import WorkflowLoader
from configs.secrets_provider import SecretsProvider
from utils.error_handler import ErrorHandler
from utils.metrics_collector import MetricsCollector
import json
import time


class ExecutionEngine:
    """
    Manages campaign execution with state management and progress tracking.
    
    Handles:
    - Campaign execution
    - State management
    - Progress tracking
    - Error recovery
    - WebSocket updates (for real-time progress)
    """
    
    def __init__(
        self,
        workflow_loader: WorkflowLoader,
        graph_builder: GraphBuilder,
        db_service: DatabaseService,
        run_logger: RunLogger,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        metrics_collector: Optional[Any] = None
    ):
        """
        Initialize execution engine.
        
        Args:
            workflow_loader: WorkflowLoader instance
            graph_builder: GraphBuilder instance
            db_service: DatabaseService instance
            run_logger: RunLogger instance
            progress_callback: Optional callback for progress updates
            metrics_collector: Optional metrics collector instance
        """
        self.workflow_loader = workflow_loader
        self.graph_builder = graph_builder
        self.db_service = db_service
        self.run_logger = run_logger
        self.progress_callback = progress_callback
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.error_handler = ErrorHandler()
        self.human_input_events: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._human_lock = threading.Lock()
        self._latest_agent_statuses: Dict[str, Dict[str, Any]] = {}
        self._status_lock = threading.Lock()
    
    def initialize_graph(self, apply_overrides: bool = True) -> None:
        """
        Initialize and compile the campaign graph.
        
        Args:
            apply_overrides: Whether to apply overrides.json
        """
        self.graph = self.graph_builder.build_graph(apply_overrides=apply_overrides)
    
    def execute_workflow(
        self,
        run_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a campaign run.
        
        Args:
            run_id: Run ID
            initial_state: Initial state (optional)
            config_overrides: Runtime configuration overrides (optional)
            
        Returns:
            Final state dictionary
        """
        # Initialize graph if not already done
        if not self.graph:
            self.initialize_graph()
        
        # Get run from database
        run = self.db_service.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        # Update status to running
        self.db_service.update_run_status(run_id, "running")
        self._notify_progress({
            "run_id": run_id,
            "status": "running",
            "message": "Campaign execution started"
        })
        
        # Initialize state
        state = initial_state or {}
        state["run_id"] = run_id
        state["workflow_name"] = run["workflow_name"]
        
        # Apply config overrides if provided
        if config_overrides:
            state["config_overrides"] = config_overrides
        
        try:
            # Execute graph
            final_state = self._execute_graph(state)
            
            # Calculate metrics
            metrics = self._calculate_metrics(final_state)
            
            # Record run completion in metrics collector
            if self.metrics_collector:
                self.metrics_collector.end_run(run_id, success=True)
            
            # Update run status to completed
            self.db_service.update_run_status(run_id, "completed", metrics=metrics)
            
            self._notify_progress({
                "run_id": run_id,
                "status": "completed",
                "message": "Campaign execution completed",
                "metrics": metrics
            })
            
            return final_state
            
        except Exception as e:
            # Record run failure in metrics collector
            if self.metrics_collector:
                self.metrics_collector.end_run(run_id, success=False)
            
            # Categorize error
            error_context = ErrorHandler.extract_error_context(e)
            error_category = ErrorHandler.categorize_error(e)
            
            # Handle error
            error_info = ErrorHandler.handle_error(
                error=e,
                context={
                    "run_id": run_id,
                    "agent_name": "execution_engine",
                    "workflow_name": state.get("workflow_name")
                },
                logger=self.run_logger,
                run_id=run_id
            )
            
            # Update run status to failed
            error_message = error_info.get("message", str(e))
            self.db_service.update_run_status(run_id, "failed", error_message=error_message)
            
            self._notify_progress({
                "run_id": run_id,
                "status": "failed",
                "message": f"Campaign execution failed: {error_message}",
                "error": error_info,
                "category": error_category.value
            })
            
            raise
    
    def _execute_graph(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the compiled graph.
        
        Args:
            state: Initial state
            
        Returns:
            Final state
        """
        if not self.graph:
            raise RuntimeError("Graph not initialized. Call initialize_graph() first.")
        
        # Get agent order for progress tracking
        agent_order = self.workflow_loader.get_agent_order()
        run_id = state.get("run_id")
        
        # Prepare agent status tracking
        def snapshot_statuses(status_map: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
            """Return a shallow copy of agent status map safe for emission."""
            return {name: status.copy() for name, status in status_map.items()}

        agent_statuses = {
            name: {
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "duration_ms": None,
                "result_status": None
            }
            for name in agent_order
        }

        # Execute graph node by node (for progress tracking)
        current_state = state.copy()
        current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
        self._store_agent_statuses(run_id, current_state["agent_statuses"])
        completed_agents = []

        # Send initial snapshot
        self._notify_progress({
            "run_id": run_id,
            "status": "pending",
            "current_agent": None,
            "completed_agents": completed_agents,
            "total_agents": len(agent_order),
            "progress": 0,
            "agent_statuses": current_state["agent_statuses"]
        })

        for agent_name in agent_order:
            try:
                agent_statuses[agent_name]["status"] = "running"
                agent_statuses[agent_name]["started_at"] = time.time()
                agent_statuses[agent_name]["result_status"] = None
                current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
                self._store_agent_statuses(run_id, current_state["agent_statuses"])

                agent_config = self.workflow_loader.get_agent_config(agent_name) or {}
                human_config = agent_config.get("human_in_loop", {}) if isinstance(agent_config, dict) else {}
                human_data = None

                if human_config.get("enabled"):
                    # Move agent into waiting state and notify clients
                    agent_statuses[agent_name]["status"] = "waiting_input"
                    agent_statuses[agent_name]["started_at"] = None
                    current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
                    self._store_agent_statuses(run_id, current_state["agent_statuses"])

                    human_prompt_payload = {
                        "agent": agent_name,
                        "prompt": human_config.get("prompt", "Manual input required"),
                        "description": human_config.get("description"),
                        "fields": human_config.get("fields"),
                        "input_schema": human_config.get("input_schema"),
                        "run_id": run_id
                    }

                    self._notify_progress({
                        "run_id": run_id,
                        "status": "waiting_input",
                        "current_agent": agent_name,
                        "completed_agents": completed_agents,
                        "total_agents": len(agent_order),
                        "progress": len(completed_agents) / len(agent_order) * 100,
                        "agent_statuses": current_state["agent_statuses"],
                        "human_in_loop": human_prompt_payload
                    })

                    # Persist status for visibility
                    self.db_service.update_run_status(run_id, "waiting_input")

                    human_data = self._wait_for_human_input(
                        run_id,
                        agent_name,
                        human_config
                    )

                    # Record provided human input in state for downstream agents
                    if human_data is not None:
                        human_inputs = current_state.setdefault("human_inputs", {})
                        human_inputs[agent_name] = human_data

                    # Resume execution
                    agent_statuses[agent_name]["status"] = "running"
                    agent_statuses[agent_name]["started_at"] = time.time()
                    current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
                    self._store_agent_statuses(run_id, current_state["agent_statuses"])

                    self.db_service.update_run_status(run_id, "running")

                    self._notify_progress({
                        "run_id": run_id,
                        "status": "running",
                        "current_agent": agent_name,
                        "completed_agents": completed_agents,
                        "total_agents": len(agent_order),
                        "progress": len(completed_agents) / len(agent_order) * 100,
                        "agent_statuses": current_state["agent_statuses"],
                        "human_in_loop_ack": {
                            "agent": agent_name,
                            "received": True
                        }
                    })

                agent_start_time = agent_statuses[agent_name]["started_at"] or time.time()
 
                # Notify progress
                self._notify_progress({
                    "run_id": run_id,
                    "status": "running",
                    "current_agent": agent_name,
                    "completed_agents": completed_agents,
                    "total_agents": len(agent_order),
                    "progress": len(completed_agents) / len(agent_order) * 100,
                    "agent_statuses": current_state["agent_statuses"]
                })
                
                # Get agent and execute
                agent = self.graph_builder.get_agent(agent_name)
                if agent:
                    # Check conditional branching
                    if not agent.check_condition(current_state):
                        # Skip this agent
                        agent_statuses[agent_name]["status"] = "skipped"
                        agent_statuses[agent_name]["finished_at"] = time.time()
                        agent_statuses[agent_name]["duration_ms"] = 0
                        completed_agents.append(agent_name)
                        current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
                        self._store_agent_statuses(run_id, current_state["agent_statuses"])
                        self._notify_progress({
                            "run_id": run_id,
                            "status": "running",
                            "message": f"Skipping agent {agent_name} due to condition",
                            "current_agent": agent_name,
                            "completed_agents": completed_agents,
                            "total_agents": len(agent_order),
                            "progress": len(completed_agents) / len(agent_order) * 100,
                            "agent_statuses": current_state["agent_statuses"]
                        })
                        continue
                    
                    # Execute agent
                    current_state = agent.execute(current_state, run_id=run_id)
                    completed_agents.append(agent_name)
                    duration_ms = (time.time() - agent_start_time) * 1000
                    agent_output = current_state.get(f"{agent_name}_output", {})
                    agent_statuses[agent_name]["status"] = "completed"
                    agent_statuses[agent_name]["finished_at"] = time.time()
                    agent_statuses[agent_name]["duration_ms"] = round(duration_ms, 2)
                    if isinstance(agent_output, dict):
                        agent_statuses[agent_name]["result_status"] = agent_output.get("status")
                    current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
                    self._store_agent_statuses(run_id, current_state["agent_statuses"])
                    
                    # Store intermediate results in database
                    self._store_intermediate_results(run_id, agent_name, current_state)

                    # Emit update after completion
                    self._notify_progress({
                        "run_id": run_id,
                        "status": "running",
                        "current_agent": agent_name,
                        "completed_agents": completed_agents,
                        "total_agents": len(agent_order),
                        "progress": len(completed_agents) / len(agent_order) * 100,
                        "agent_statuses": current_state["agent_statuses"]
                    })
                
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                agent_statuses[agent_name]["status"] = "failed"
                agent_statuses[agent_name]["finished_at"] = time.time()
                agent_statuses[agent_name]["duration_ms"] = round((time.time() - agent_start_time) * 1000, 2)
                agent_statuses[agent_name]["result_status"] = "failed"
                current_state["agent_statuses"] = snapshot_statuses(agent_statuses)
                self._store_agent_statuses(run_id, current_state["agent_statuses"])
                
                # Log error but continue with next agent if possible
                error_data = {
                    "agent": agent_name,
                    "error": str(e),
                    "type": type(e).__name__,
                    "traceback": error_traceback,
                    "category": "permanent"
                }
                
                self._notify_progress({
                    "run_id": run_id,
                    "status": "failed",
                    "current_agent": agent_name,
                    "agent_name": agent_name,
                    "error": error_data,
                    "message": f"Error in agent {agent_name}: {str(e)}",
                    "agent_statuses": current_state["agent_statuses"]
                })
                
                # Re-raise if it's a critical error
                raise
        
        return current_state
    
    def _store_intermediate_results(
        self,
        run_id: str,
        agent_name: str,
        state: Dict[str, Any]
    ) -> None:
        """
        Store intermediate results in database.
        
        Args:
            run_id: Run ID
            agent_name: Agent name
            state: Current state
        """
        output_key = f"{agent_name}_output"
        output_data = state.get(output_key)
        
        if not output_data:
            return
        
        # Store based on agent type
        # IMPORTANT: Only save leads ONCE after scoring (not after prospect_search or data_enrichment)
        # This prevents duplicates and ensures scores are saved
        if agent_name == "scoring":
            # Store leads with scores and capture generated lead IDs
            leads = output_data.get("leads", []) or output_data.get("ranked_leads", [])
            if isinstance(leads, list) and leads:
                lead_ids = self.db_service.bulk_create_leads(run_id, leads)
                # Propagate lead IDs back into state for downstream agents
                for lead, lead_id in zip(leads, lead_ids):
                    lead["lead_id"] = lead_id
                # Ensure alternate references share the IDs
                if isinstance(output_data.get("ranked_leads"), list):
                    output_data["ranked_leads"] = leads
                state[output_key] = output_data
        
        elif agent_name == "apollo_contact_sync":
            # Update existing leads with Apollo contact IDs
            leads = output_data.get("leads", [])
            if isinstance(leads, list):
                for lead in leads:
                    apollo_contact_id = lead.get("apollo_contact_id")
                    apollo_synced_at = lead.get("apollo_synced_at")
                    apollo_sync_status = lead.get("apollo_sync_status")
                    lead_id = lead.get("lead_id")
                    
                    if lead_id and apollo_contact_id:
                        # Update the lead with Apollo sync info
                        try:
                            with self.db_service.get_connection() as conn:
                                conn.execute(
                                    """
                                    UPDATE leads 
                                    SET apollo_contact_id = ?,
                                        apollo_synced_at = ?,
                                        apollo_sync_status = ?
                                    WHERE lead_id = ?
                                    """,
                                    (apollo_contact_id, apollo_synced_at, apollo_sync_status, lead_id)
                                )
                        except Exception as e:
                            print(f"Warning: Could not update lead {lead_id} with Apollo ID: {e}")
        
        elif agent_name == "outreach_content":
            messages = output_data.get("messages", [])
            if isinstance(messages, list):
                for msg in messages:
                    lead_id = msg.get("lead_id")
                    if not lead_id:
                        continue
                    message_payload = {
                        "message_id": msg.get("message_id"),
                        "subject": msg.get("subject"),
                        "body": msg.get("body"),
                        "personalization_used": msg.get("personalization_used"),
                        "status": "draft"
                    }
                    message_id = self.db_service.create_message(run_id, lead_id, message_payload)
                    msg["message_id"] = message_id
                state[output_key] = output_data
        
        elif agent_name == "outreach_executor":
            # Messages are persisted and updated directly within the executor
            pass
        
        elif agent_name == "response_tracker":
            # Responses are stored separately
            pass
    
    def _calculate_metrics(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate run-level metrics from final state.
        
        Args:
            final_state: Final state dictionary
        
        Returns:
            Metrics dictionary
        """
        metrics = {
            "leads_found": 0,
            "leads_enriched": 0,
            "messages_sent": 0,
            "replies": 0,
            "meetings": 0
        }
 
        # Extract metrics from state
        prospect_output = final_state.get("prospect_search_output", {})
        if isinstance(prospect_output, dict):
            leads = prospect_output.get("leads", [])
            if isinstance(leads, list):
                metrics["leads_found"] = len(leads)
 
        # Count messages from outreach_executor output
        executor_output = final_state.get("outreach_executor_output", {})
        messages = executor_output.get("messages", [])
        if isinstance(messages, list):
            metrics["messages_sent"] = len(messages)
 
        # Count responses from response_tracker output
        tracker_output = final_state.get("response_tracker_output", {})
        responses = tracker_output.get("responses", [])
        if isinstance(responses, list):
            metrics["replies"] = sum(1 for r in responses if r.get("replied"))
            metrics["meetings"] = sum(1 for r in responses if r.get("meeting_scheduled"))
 
        return metrics

    def _wait_for_human_input(
        self,
        run_id: str,
        agent_name: str,
        human_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Pause execution until human input is provided.

        Args:
            run_id: Run identifier
            agent_name: Agent requesting input
            human_config: Human-in-loop configuration

        Returns:
            Provided human input payload or None
        """
        wait_key = (run_id, agent_name)
        event = threading.Event()

        with self._human_lock:
            # Overwrite any stale event for safety
            self.human_input_events[wait_key] = {
                "event": event,
                "data": None,
                "config": human_config
            }

        event.wait()

        with self._human_lock:
            entry = self.human_input_events.pop(wait_key, None)

        if entry:
            return entry.get("data")

        return None

    def provide_human_input(
        self,
        run_id: str,
        agent_name: str,
        input_payload: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Resume execution for an agent waiting on human input.

        Args:
            run_id: Run identifier
            agent_name: Agent awaiting input
            input_payload: Human-provided payload (optional)

        Returns:
            True if the input was accepted, False if no agent was waiting.
        """
        wait_key = (run_id, agent_name)

        with self._human_lock:
            entry = self.human_input_events.get(wait_key)
            if not entry:
                return False

            entry["data"] = input_payload
            entry_event = entry.get("event")
            if isinstance(entry_event, threading.Event):
                entry_event.set()

        return True

    def _store_agent_statuses(self, run_id: str, statuses: Dict[str, Dict[str, Any]]) -> None:
        """Persist the latest agent status snapshot for a run."""
        with self._status_lock:
            self._latest_agent_statuses[run_id] = {
                name: status.copy() for name, status in statuses.items()
            }

    def _notify_progress(self, progress_data: Dict[str, Any]) -> None:
        """
        Notify progress callback if available and update database.
        
        Args:
            progress_data: Progress data dictionary
        """
        # Extract run_id and progress percentage
        run_id = progress_data.get("run_id")
        progress_percent = progress_data.get("progress")
        status = progress_data.get("status")
        
        # If we have progress, update the database
        if run_id and progress_percent is not None:
            try:
                self.db_service.update_run_status(
                    run_id=run_id, 
                    status=status or "running", 
                    progress=progress_percent
                )
            except Exception as e:
                # Don't fail execution if DB update fails
                print(f"Warning: Failed to update progress in DB: {e}")
        
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception:
                # Ignore callback errors
                pass
    
    def get_progress(self, run_id: str) -> Dict[str, Any]:
        """
        Get current execution progress.
        
        Args:
            run_id: Run ID
            
        Returns:
            Progress dictionary
        """
        run = self.db_service.get_run(run_id)
        if not run:
            return {"error": "Run not found"}
        
        # Get run logs to determine progress
        logs = self.db_service.get_run_logs(run_id)
        agent_order = self.workflow_loader.get_agent_order()
        
        completed_agents = set()
        for log in logs:
            agent_name = log.get("agent_name")
            step = log.get("step")
            if agent_name and step == "output":
                completed_agents.add(agent_name)
        
        progress = {
            "run_id": run_id,
            "status": run["status"],
            "completed_agents": list(completed_agents),
            "total_agents": len(agent_order),
            "progress_percent": len(completed_agents) / len(agent_order) * 100 if agent_order else 0,
            "agent_statuses": self._latest_agent_statuses.get(run_id)
        }
        
        return progress

