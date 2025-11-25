"""
Main entry point for the Prospect-to-Lead workflow application.
"""

import os
from app.app import app, socketio

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Prospect-to-Lead Workflow Server on port {port}")
    print(f"Debug mode: {debug}")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)

