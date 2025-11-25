"""
Flask application for Prospect-to-Lead LangGraph Campaign.
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from typing import Dict, Any, Optional
import json
import csv
import io
from datetime import datetime

from configs.workflow_loader import WorkflowLoader
from configs.secrets_provider import SecretsProvider
from configs.overrides_manager import OverridesManager
from database.db_service import DatabaseService
from database.run_logger import RunLogger
from agents.graph_builder import GraphBuilder
from agents.execution_engine import ExecutionEngine
from agents.agent_factory import create_agent
from utils.rate_limiter import RateLimiter
from utils.error_handler import ErrorHandler
from utils.input_validator import InputValidator
from utils.metrics_collector import MetricsCollector


# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)  # Enable CORS for frontend
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize services
workflow_loader = WorkflowLoader(config_dir="./configs")
secrets_provider = SecretsProvider()
overrides_manager = OverridesManager()
db_service = DatabaseService(db_path=os.getenv("DATABASE_PATH", "./database/prospect_workflow.db"))
run_logger = RunLogger(
    db_service=db_service,
    log_dir=os.getenv("LOG_DIR", "./logs"),
    enable_full_traces=os.getenv("ENABLE_FULL_TRACES", "False").lower() == "true"
)

# Initialize utilities
rate_limiter = RateLimiter(
    db_service=db_service,
    max_leads_per_run=int(os.getenv("MAX_LEADS_PER_RUN", 50)),
    max_leads_per_day=int(os.getenv("MAX_LEADS_PER_DAY", 200))
)
input_validator = InputValidator()
metrics_collector = MetricsCollector()

# Initialize graph builder and execution engine
graph_builder = GraphBuilder(
    workflow_loader=workflow_loader,
    agent_factory=create_agent,
    secrets_provider=secrets_provider,
    logger=run_logger
)

execution_engine = ExecutionEngine(
    workflow_loader=workflow_loader,
    graph_builder=graph_builder,
    db_service=db_service,
    run_logger=run_logger,
    progress_callback=lambda progress: socketio.emit('progress_update', progress, room=progress.get('run_id')),
    metrics_collector=metrics_collector
)

execution_engine.initialize_graph()

# Store active runs for progress tracking
active_runs: Dict[str, Dict[str, Any]] = {}


# ==================== API ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get performance metrics."""
    try:
        global_metrics = metrics_collector.get_global_metrics()
        return jsonify(global_metrics)
    except Exception as e:
        return jsonify({
            "error": "Failed to get metrics",
            "message": str(e)
        }), 500


@app.route('/api/metrics/runs/<run_id>', methods=['GET'])
def get_run_metrics(run_id: str):
    """Get metrics for a specific run."""
    try:
        # Validate run_id
        valid, error = input_validator.validate_run_id(run_id)
        if not valid:
            return jsonify({"error": "Invalid run ID", "message": error}), 400
        
        # Get run logs to calculate metrics
        logs = db_service.get_run_logs(run_id)
        
        # Calculate metrics from logs
        node_timings = {}
        tool_calls = {}
        errors = []
        
        for log in logs:
            agent_name = log.get("agent_name")
            duration = log.get("duration_ms")
            step = log.get("step")
            
            if agent_name and duration:
                if agent_name not in node_timings:
                    node_timings[agent_name] = []
                node_timings[agent_name].append(duration)
            
            if step == "tool_call":
                tool_name = "unknown"
                if log.get("input_data"):
                    try:
                        input_data = json.loads(log["input_data"])
                        tool_name = input_data.get("tool", "unknown")
                    except:
                        pass
                key = f"{agent_name}.{tool_name}"
                tool_calls[key] = tool_calls.get(key, 0) + 1
            
            if step == "error":
                errors.append({
                    "agent": agent_name,
                    "error": log.get("error_data")
                })
        
        # Calculate averages
        node_metrics = {}
        for agent_name, timings in node_timings.items():
            node_metrics[agent_name] = {
                "avg_duration_ms": sum(timings) / len(timings) if timings else 0,
                "total_duration_ms": sum(timings),
                "call_count": len(timings)
            }
        
        return jsonify({
            "run_id": run_id,
            "node_metrics": node_metrics,
            "tool_calls": tool_calls,
            "error_count": len(errors),
            "errors": errors
        })
    
    except Exception as e:
        return jsonify({
            "error": "Failed to get run metrics",
            "message": str(e)
        }), 500


@app.route('/api/rate-limits', methods=['GET'])
def get_rate_limits():
    """Get current rate limit usage."""
    try:
        usage = rate_limiter.get_daily_usage()
        return jsonify(usage)
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch rate limits",
            "message": str(e)
        }), 500


@app.route('/api/run', methods=['POST'])
def trigger_run():
    """
    Trigger a campaign execution.
    
    Request body:
    {
        "workflow_name": "prospect_to_lead_v1",
        "config_overrides": {}  # Optional
    }
    """
    try:
        data = request.get_json() or {}
        
        workflow_name = data.get("workflow_name", "prospect_to_lead_v1")
        config_overrides = data.get("config_overrides")
        
        # Validate campaign name
        valid, error = input_validator.validate_workflow_name(workflow_name)
        if not valid:
            return jsonify({"error": "Invalid campaign name", "message": error}), 400
        
        # Get requested leads count from ICP or defaults
        requested_leads = 50  # Default
        if config_overrides and isinstance(config_overrides, dict):
            # Try to get from ICP config
            icp = config_overrides.get("agents", {}).get("prospect_search", {}).get("inputs", {}).get("icp")
            if icp:
                tool_config = config_overrides.get("agents", {}).get("prospect_search", {}).get("tool_config", {})
                requested_leads = tool_config.get("max_results", 50)
        
        # Check rate limits
        allowed, error_msg, usage_info = rate_limiter.check_all_limits(requested_leads)
        if not allowed:
            return jsonify({
                "error": "Rate limit exceeded",
                "message": error_msg,
                "usage": usage_info
            }), 429
        
        # Create run in database
        workflow_config = workflow_loader.get_workflow()
        campaign_name = data.get("campaign_name") or workflow_name
        
        run_id = db_service.create_run(
            workflow_name=workflow_name,
            config_snapshot=workflow_config,
            campaign_name=campaign_name
        )
        
        # Store run info
        active_runs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "campaign_name": campaign_name,
            "started_at": datetime.utcnow().isoformat()
        }
        
        # Execute campaign asynchronously
        # In production, use a task queue (Celery) for long-running campaigns
        # For now, we'll run it in a background thread
        import threading
        
        def execute_in_background():
            try:
                initial_state = {
                    "run_id": run_id,
                    "workflow_name": workflow_name
                }
                
                execution_engine.execute_workflow(
                    run_id=run_id,
                    initial_state=initial_state,
                    config_overrides=config_overrides
                )
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                
                # Get the last agent that failed from the error
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": error_traceback,
                    "category": "permanent"
                }
                
                # Try to extract agent name from traceback
                agent_name = "execution_engine"
                if "agent.execute" in error_traceback or "_process" in error_traceback:
                    # Try to find agent name in traceback
                    import re
                    agent_match = re.search(r'agents/(\w+)_agent\.py', error_traceback)
                    if agent_match:
                        agent_name = agent_match.group(1)
                
                db_service.update_run_status(run_id, "failed", error_message=str(e))
                socketio.emit('progress_update', {
                    "run_id": run_id,
                    "status": "failed",
                    "current_agent": agent_name,
                    "agent_name": agent_name,
                    "error": error_info,
                    "message": f"Campaign failed at {agent_name}: {str(e)}"
                }, room=run_id)
        
        # Start background thread
        thread = threading.Thread(target=execute_in_background)
        thread.daemon = True
        thread.start()
        
        # Start metrics collection
        metrics_collector.start_run(run_id)
        
        return jsonify({
            "run_id": run_id,
            "status": "running",
            "message": "Campaign execution started",
            "rate_limit_info": usage_info
        }), 202
    
    except Exception as e:
        return jsonify({
            "error": "Invalid request",
            "message": str(e)
        }), 400


@app.route('/api/runs', methods=['GET'])
def list_runs():
    """
    List all runs with optional filters.
    
    Query parameters:
    - workflow_name: Filter by campaign name
    - status: Filter by status
    - limit: Maximum results (default: 50)
    - offset: Offset for pagination (default: 0)
    """
    try:
        workflow_name = request.args.get('workflow_name')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        runs, total = db_service.get_runs(
            workflow_name=workflow_name,
            status=status,
            limit=limit,
            offset=offset,
            return_total=True
        )
        
        # Parse JSON fields and format progress
        for run in runs:
            if run.get('config_snapshot'):
                try:
                    run['config_snapshot'] = json.loads(run['config_snapshot'])
                except:
                    pass
            if run.get('metrics'):
                try:
                    run['metrics'] = json.loads(run['metrics'])
                except:
                    pass
            
            # Ensure progress object structure for frontend compatibility
            if run.get('progress') is not None:
                run['progress'] = {
                    'progress_percent': float(run['progress'])
                }
            else:
                # If no progress stored, try to calculate or default to 0
                run['progress'] = {
                    'progress_percent': 0
                }
        
        return jsonify({
            "runs": runs,
            "total": total
        })
    
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch runs",
            "message": str(e)
        }), 500


@app.route('/api/runs/<run_id>', methods=['GET'])
def get_run(run_id: str):
    """Get run details and artifacts."""
    try:
        # Validate run ID
        is_valid, error_msg = input_validator.validate_run_id(run_id)
        if not is_valid:
            return jsonify({
                "error": "Invalid run ID",
                "message": error_msg
            }), 400
        
        run = db_service.get_run(run_id)
        if not run:
            return jsonify({
                "error": "Run not found"
            }), 404
        
        # Parse JSON fields
        if run.get('config_snapshot'):
            try:
                run['config_snapshot'] = json.loads(run['config_snapshot'])
            except:
                pass
        if run.get('metrics'):
            try:
                run['metrics'] = json.loads(run['metrics'])
            except:
                pass
        
        # Get progress
        progress = execution_engine.get_progress(run_id)
        run['progress'] = progress
        
        return jsonify(run)
    
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch run",
            "message": str(e)
        }), 500


@app.route('/api/runs/<run_id>/leads', methods=['GET'])
def get_run_leads(run_id: str):
    """
    Get leads for a run (paginated).
    
    Query parameters:
    - limit: Maximum results (default: 100)
    - offset: Offset for pagination (default: 0)
    """
    try:
        # Validate run ID
        is_valid, error_msg = input_validator.validate_run_id(run_id)
        if not is_valid:
            return jsonify({
                "error": "Invalid run ID",
                "message": error_msg
            }), 400
        
        # Validate pagination
        limit = request.args.get('limit', '100')
        offset = request.args.get('offset', '0')
        
        try:
            limit = int(limit) if limit else 100
            offset = int(offset) if offset else 0
        except ValueError:
            return jsonify({
                "error": "Invalid pagination parameters",
                "message": "limit and offset must be integers"
            }), 400
        
        is_valid, error_msg = input_validator.validate_pagination(limit, offset)
        if not is_valid:
            return jsonify({
                "error": "Invalid pagination",
                "message": error_msg
            }), 400
        
        leads = db_service.get_leads_by_run(run_id, limit=limit, offset=offset)
        
        # Parse JSON fields
        for lead in leads:
            if lead.get('enrichment_data'):
                try:
                    enrichment_str = lead['enrichment_data']
                    if isinstance(enrichment_str, str):
                        lead['enrichment_data'] = json.loads(enrichment_str)
                except (json.JSONDecodeError, TypeError):
                    lead['enrichment_data'] = None
        
        return jsonify({
            "leads": leads,
            "total": len(leads),
            "limit": limit,
            "offset": offset
        })
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error fetching leads: {error_trace}")  # Debug log
        return jsonify({
            "error": "Failed to fetch leads",
            "message": str(e),
            "traceback": error_trace if app.debug else None
        }), 500


@app.route('/api/runs/<run_id>/messages', methods=['GET'])
def get_run_messages(run_id: str):
    """
    Get messages for a run (paginated).
    
    Query parameters:
    - limit: Maximum results (default: 100)
    - offset: Offset for pagination (default: 0)
    """
    try:
        # Validate run ID
        is_valid, error_msg = input_validator.validate_run_id(run_id)
        if not is_valid:
            return jsonify({
                "error": "Invalid run ID",
                "message": error_msg
            }), 400
        
        # Validate pagination
        limit = request.args.get('limit', '100')
        offset = request.args.get('offset', '0')
        
        try:
            limit = int(limit) if limit else 100
            offset = int(offset) if offset else 0
        except ValueError:
            return jsonify({
                "error": "Invalid pagination parameters",
                "message": "limit and offset must be integers"
            }), 400
        
        is_valid, error_msg = input_validator.validate_pagination(limit, offset)
        if not is_valid:
            return jsonify({
                "error": "Invalid pagination",
                "message": error_msg
            }), 400
        
        messages = db_service.get_messages_by_run(run_id, limit=limit, offset=offset)
        
        # Parse JSON fields
        for message in messages:
            if message.get('personalization_used'):
                try:
                    message['personalization_used'] = json.loads(message['personalization_used'])
                except:
                    pass
        
        return jsonify({
            "messages": messages,
            "total": len(messages),
            "limit": limit,
            "offset": offset
        })
    
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch messages",
            "message": str(e)
        }), 500


@app.route('/api/runs/<run_id>/responses', methods=['GET'])
def get_run_responses(run_id: str):
    """Get all responses for messages in a run."""
    try:
        # Validate run ID
        is_valid, error_msg = input_validator.validate_run_id(run_id)
        if not is_valid:
            return jsonify({
                "error": "Invalid run ID",
                "message": error_msg
            }), 400
        
        responses = db_service.get_responses_by_run(run_id)
        
        return jsonify({
            "responses": responses,
            "total": len(responses)
        })
    
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch responses",
            "message": str(e)
        }), 500


@app.route('/api/runs/<run_id>/agents/<agent_name>/human-input', methods=['POST'])
def provide_human_input(run_id: str, agent_name: str):
    """Provide human-in-the-loop input to resume a paused agent."""
    try:
        # Validate run ID
        is_valid, error_msg = input_validator.validate_run_id(run_id)
        if not is_valid:
            return jsonify({
                "error": "Invalid run ID",
                "message": error_msg
            }), 400

        if not agent_name or not isinstance(agent_name, str):
            return jsonify({
                "error": "Invalid agent name"
            }), 400

        payload = request.get_json() or {}

        accepted = execution_engine.provide_human_input(
            run_id=run_id,
            agent_name=agent_name,
            input_payload=payload
        )

        if not accepted:
            return jsonify({
                "error": "No agent awaiting input",
                "run_id": run_id,
                "agent": agent_name
            }), 404

        return jsonify({
            "status": "accepted",
            "run_id": run_id,
            "agent": agent_name
        })

    except Exception as e:
        return jsonify({
            "error": "Failed to submit human input",
            "message": str(e)
        }), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current campaign configuration."""
    try:
        workflow = workflow_loader.get_workflow(apply_overrides=True)
        return jsonify(workflow)
    
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch config",
            "message": str(e)
        }), 500


@app.route('/api/feedback/pending', methods=['GET'])
def get_pending_recommendations():
    """
    Get pending recommendations.
    
    Query parameters:
    - run_id: Optional run ID filter
    """
    try:
        run_id = request.args.get('run_id')
        recommendations = db_service.get_pending_recommendations(run_id=run_id)
        
        # Parse JSON fields
        for rec in recommendations:
            if rec.get('old_value'):
                try:
                    rec['old_value'] = json.loads(rec['old_value'])
                except:
                    pass
            if rec.get('new_value'):
                try:
                    rec['new_value'] = json.loads(rec['new_value'])
                except:
                    pass
        
        return jsonify({
            "recommendations": recommendations,
            "total": len(recommendations)
        })
    
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch recommendations",
            "message": str(e)
        }), 500


@app.route('/api/feedback/approve', methods=['POST'])
def approve_recommendation():
    """
    Approve a recommendation and apply it to overrides.json.
    
    Request body:
    {
        "rec_id": "recommendation_id"
    }
    """
    try:
        data = request.get_json() or {}
        rec_id = data.get("rec_id")
        
        # Validate input
        if not rec_id:
            return jsonify({
                "error": "Missing rec_id"
            }), 400
        
        if not isinstance(rec_id, str):
            return jsonify({
                "error": "Invalid rec_id",
                "message": "rec_id must be a string"
            }), 400
        
        # Get recommendation from database
        recommendations = db_service.get_pending_recommendations()
        rec = next((r for r in recommendations if r['rec_id'] == rec_id), None)
        
        if not rec:
            return jsonify({
                "error": "Recommendation not found"
            }), 404
        
        # Parse values
        old_value = rec.get('old_value')
        new_value = rec.get('new_value')
        
        if isinstance(old_value, str):
            try:
                old_value = json.loads(old_value)
            except:
                pass
        
        if isinstance(new_value, str):
            try:
                new_value = json.loads(new_value)
            except:
                pass
        
        # Apply to overrides.json
        field = rec.get('field', '')
        overrides_manager.apply_recommendation(
            field=field,
            new_value=new_value
        )
        
        # Update database
        db_service.approve_recommendation(rec_id)
        
        # Update Google Sheets if configured
        from tools.google_sheets import GoogleSheetsAPI
        creds_path = secrets_provider.get_google_sheets_creds_path()
        if creds_path:
            try:
                sheets_api = GoogleSheetsAPI(
                    credentials_path=creds_path,
                    sheet_id=secrets_provider.get_google_sheets_id()
                )
                sheets_api.update_recommendation_status(
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    status="Approved"
                )
            except Exception as e:
                # Log but don't fail
                print(f"Warning: Failed to update Google Sheets: {e}")
        
        # Reload workflow to apply overrides
        execution_engine.initialize_graph(apply_overrides=True)
        
        return jsonify({
            "message": "Recommendation approved and applied",
            "rec_id": rec_id,
            "field": field,
            "applied_at": overrides_manager.get_overrides().get("applied_at")
        })
    
    except Exception as e:
        return jsonify({
            "error": "Failed to approve recommendation",
            "message": str(e)
        }), 500


@app.route('/api/export/runs/<run_id>/csv', methods=['GET'])
def export_run_csv(run_id: str):
    """Export run data as CSV."""
    try:
        # Get all data
        leads = db_service.get_leads_by_run(run_id, limit=10000)
        messages = db_service.get_messages_by_run(run_id, limit=10000)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write leads
        writer.writerow(['Type', 'Company Name', 'Contact Email', 'Contact Name', 'Score', 'Status'])
        for lead in leads:
            writer.writerow([
                'Lead',
                lead.get('company_name', ''),
                lead.get('contact_email', ''),
                lead.get('contact_name', ''),
                lead.get('score', ''),
                ''
            ])
        
        # Write messages
        for message in messages:
            writer.writerow([
                'Message',
                '',
                '',
                '',
                '',
                message.get('status', '')
            ])
        
        output.seek(0)
        
        return app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=run_{run_id}.csv'}
        )
    
    except Exception as e:
        return jsonify({
            "error": "Failed to export CSV",
            "message": str(e)
        }), 500


@app.route('/api/export/runs/<run_id>/json', methods=['GET'])
def export_run_json(run_id: str):
    """Export run data as JSON."""
    try:
        run = db_service.get_run(run_id)
        leads = db_service.get_leads_by_run(run_id, limit=10000)
        messages = db_service.get_messages_by_run(run_id, limit=10000)
        responses = db_service.get_responses_by_run(run_id)
        
        export_data = {
            "run": run,
            "leads": leads,
            "messages": messages,
            "responses": responses,
            "exported_at": datetime.utcnow().isoformat()
        }
        
        return jsonify(export_data)
    
    except Exception as e:
        return jsonify({
            "error": "Failed to export JSON",
            "message": str(e)
        }), 500


# ==================== WEBSOCKET ROUTES ====================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    emit('connected', {'message': 'Connected to campaign server'})


@socketio.on('join_run')
def handle_join_run(data):
    """Join a run room for progress updates."""
    run_id = data.get('run_id')
    if run_id:
        socketio.server.enter_room(request.sid, run_id)
        emit('joined', {'run_id': run_id, 'message': f'Joined run {run_id}'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    pass
# ==================== SEQUENCE MANAGEMENT ====================

@app.route('/api/sequences/search', methods=['GET', 'POST'])
def search_sequences():
    """
    Search for Apollo sequences.
    
    Query params (GET) or JSON body (POST):
    - q_name: Optional keyword to filter sequences
    - page: Page number (default: 1)
    - per_page: Results per page (default: 25)
    """
    try:
        from tools.apollo_api import ApolloAPI
        
        # Get query params or JSON body
        if request.method == 'POST':
            data = request.get_json() or {}
        else:
            data = request.args
        
        q_name = data.get('q_name')
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 25))
        
        # Initialize Apollo API
        apollo_key = secrets_provider.get_apollo_api_key()
        if not apollo_key:
            return jsonify({
                "error": "Apollo API key not configured",
                "sequences": []
            }), 400
        
        apollo_api = ApolloAPI(apollo_key)
        
        # Search sequences
        response = apollo_api.search_sequences(
            q_name=q_name,
            page=page,
            per_page=per_page
        )
        
        sequences = response.get("emailer_campaigns", [])
        pagination = response.get("pagination", {})
        
        # Simplify sequence data
        simplified_sequences = []
        for seq in sequences:
            simplified_sequences.append({
                "id": seq.get("id"),
                "name": seq.get("name"),
                "active": seq.get("active", False),
                "num_contacts": seq.get("num_contacts", 0),
                "num_steps": seq.get("num_steps", 0),
                "created_at": seq.get("created_at"),
                "permissions": seq.get("permissions", {})
            })
        
        return jsonify({
            "sequences": simplified_sequences,
            "pagination": pagination,
            "total": len(simplified_sequences)
        })
        
    except Exception as e:
        error_handler.handle_error("api", e, {"endpoint": "search_sequences"})
        return jsonify({
            "error": str(e),
            "sequences": []
        }), 500


@app.route('/api/sequences/<sequence_id>/add-contacts', methods=['POST'])
def add_contacts_to_sequence(sequence_id: str):
    """
    Add contacts to an Apollo sequence.
    
    JSON body:
    - contact_ids: List of Apollo contact IDs (required)
    - run_id: Optional run ID to associate with
    - settings: Optional sequence settings (allow_active_in_other, etc.)
    """
    try:
        from tools.apollo_api import ApolloAPI
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        contact_ids = data.get('contact_ids', [])
        if not contact_ids or not isinstance(contact_ids, list):
            return jsonify({"error": "contact_ids array is required"}), 400
        
        run_id = data.get('run_id')
        settings = data.get('settings', {})
        
        # Initialize Apollo API
        apollo_key = secrets_provider.get_apollo_api_key()
        if not apollo_key:
            return jsonify({"error": "Apollo API key not configured"}), 400
        
        apollo_api = ApolloAPI(apollo_key)
        
        # Add contacts to sequence
        response = apollo_api.add_contacts_to_sequence(
            sequence_id=sequence_id,
            contact_ids=contact_ids,
            sequence_active_in_other_campaigns=settings.get('allow_active_in_other', False),
            sequence_finished_in_other_campaigns=settings.get('allow_finished_in_other', True),
            sequence_no_email=settings.get('allow_no_email', False),
            sequence_unsubscribed_email=settings.get('allow_unsubscribed', False)
        )
        
        # Parse response
        contacts = response.get("contacts", [])
        emailer_campaign = response.get("emailer_campaign", {})
        
        added_count = sum(1 for c in contacts if c.get("status") in ["added", "success"])
        failed_count = len(contacts) - added_count
        
        # Log to database if run_id provided
        if run_id:
            try:
                run_logger.log_agent_step(
                    run_id=run_id,
                    agent_name="sequence_manager",
                    step="add_to_sequence",
                    input_data={"sequence_id": sequence_id, "contact_count": len(contact_ids)},
                    output_data={"added": added_count, "failed": failed_count}
                )
            except Exception as log_error:
                print(f"Failed to log sequence addition: {log_error}")
        
        return jsonify({
            "success": True,
            "sequence_id": sequence_id,
            "sequence_name": emailer_campaign.get("name"),
            "added_count": added_count,
            "failed_count": failed_count,
            "total_contacts": len(contact_ids),
            "contacts": contacts
        })
        
    except Exception as e:
        error_handler.handle_error("api", e, {
            "endpoint": "add_contacts_to_sequence",
            "sequence_id": sequence_id
        })
        return jsonify({"error": str(e)}), 500


@app.route('/api/runs/<run_id>/leads-with-apollo-ids', methods=['GET'])
def get_run_leads_with_apollo_ids(run_id: str):
    """
    Get leads from a run that have Apollo contact IDs.
    Useful for adding to sequences.
    """
    try:
        # Get all leads for the run
        leads = db_service.get_leads_by_run(run_id, limit=1000)
        
        # Filter leads that have apollo_contact_id
        leads_with_apollo_ids = []
        for lead in leads:
            if lead.get("apollo_contact_id"):
                leads_with_apollo_ids.append({
                    "lead_id": lead.get("lead_id"),
                    "apollo_contact_id": lead.get("apollo_contact_id"),
                    "company_name": lead.get("company_name"),
                    "contact_name": lead.get("contact_name"),
                    "contact_email": lead.get("contact_email"),
                    "contact_title": lead.get("contact_title"),
                    "score": lead.get("score"),
                    "apollo_synced_at": lead.get("apollo_synced_at")
                })
        
        return jsonify({
            "run_id": run_id,
            "leads": leads_with_apollo_ids,
            "total": len(leads_with_apollo_ids)
        })
        
    except Exception as e:
        error_handler.handle_error("api", e, {
            "endpoint": "get_run_leads_with_apollo_ids",
            "run_id": run_id
        })
        return jsonify({"error": str(e)}), 500


@app.route('/api/contacts/all-with-apollo-ids', methods=['GET'])
def get_all_contacts_with_apollo_ids():
    """
    Get ALL contacts from database that have Apollo contact IDs.
    Not limited to a specific run - shows all synced contacts.
    
    Query params:
    - limit: Max results (default: 1000)
    - search: Search by company name, contact name, or email
    """
    try:
        limit = int(request.args.get('limit', 1000))
        search_term = request.args.get('search', '').lower()
        
        # Get all contacts from database with apollo_contact_id
        with db_service.get_connection() as conn:
            query = """
                SELECT 
                    lead_id,
                    apollo_contact_id,
                    company_name,
                    contact_name,
                    contact_email,
                    contact_title,
                    score,
                    apollo_synced_at,
                    run_id,
                    created_at
                FROM leads
                WHERE apollo_contact_id IS NOT NULL
                  AND apollo_contact_id != ''
                ORDER BY created_at DESC
                LIMIT ?
            """
            rows = conn.execute(query, (limit,)).fetchall()
            
            contacts = []
            for row in rows:
                contact = {
                    "lead_id": row[0],
                    "apollo_contact_id": row[1],
                    "company_name": row[2],
                    "contact_name": row[3],
                    "contact_email": row[4],
                    "contact_title": row[5],
                    "score": row[6],
                    "apollo_synced_at": row[7],
                    "run_id": row[8],
                    "created_at": row[9]
                }
                
                # Apply search filter if provided
                if search_term:
                    company = (contact.get("company_name") or "").lower()
                    name = (contact.get("contact_name") or "").lower()
                    email = (contact.get("contact_email") or "").lower()
                    
                    if search_term in company or search_term in name or search_term in email:
                        contacts.append(contact)
                else:
                    contacts.append(contact)
        
        return jsonify({
            "contacts": contacts,
            "total": len(contacts)
        })
        
    except Exception as e:
        error_handler.handle_error("api", e, {
            "endpoint": "get_all_contacts_with_apollo_ids"
        })
        return jsonify({"error": str(e), "contacts": []}), 500


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred"
    }), 500


@app.errorhandler(400)
def bad_request(error):
    """Handle 400 errors."""
    return jsonify({
        "error": "Bad request",
        "message": "Invalid request parameters"
    }), 400


# Serve frontend static files
@app.route('/')
def index():
    """Serve main dashboard."""
    import os
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route('/<path:filename>')
def serve_frontend(filename):
    """Serve frontend static files."""
    import os
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    # Only serve files that exist and are safe
    if filename.endswith(('.html', '.js', '.css', '.json', '.png', '.jpg', '.svg', '.ico')):
        return send_from_directory(frontend_path, filename)
    return jsonify({"error": "Not found"}), 404


if __name__ == '__main__':
    # Run Flask app
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)

