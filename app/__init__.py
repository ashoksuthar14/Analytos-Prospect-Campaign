"""
Flask application package.
"""

from app.app import app, socketio

__all__ = ["app", "socketio"]
