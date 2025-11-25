"""
API Metrics Endpoint: Provides observability metrics.
"""

from flask import Blueprint, jsonify
from utils.observability import metrics_collector

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/api/metrics', methods=['GET'])
def get_metrics():
    """
    Get system metrics for observability.
    
    Returns:
        Comprehensive metrics dictionary
    """
    try:
        summary = metrics_collector.get_metrics_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch metrics",
            "message": str(e)
        }), 500


@metrics_bp.route('/api/metrics/nodes/<agent_name>', methods=['GET'])
def get_node_metrics(agent_name: str):
    """
    Get metrics for a specific agent/node.
    
    Args:
        agent_name: Agent name
        
    Returns:
        Node-specific metrics
    """
    try:
        stats = metrics_collector.get_node_stats(agent_name=agent_name)
        return jsonify(stats)
    except Exception as e:
        return jsonify({
            "error": "Failed to fetch node metrics",
            "message": str(e)
        }), 500

