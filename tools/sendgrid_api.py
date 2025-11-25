"""
SendGrid API integration tool.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from tools.base_tool import BaseTool

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


class SendGridAPI(BaseTool):
    """
    SendGrid API client for email sending and tracking.
    
    Documentation: https://docs.sendgrid.com/
    """
    
    def __init__(self, api_key: str, from_email: str, from_name: str):
        """
        Initialize SendGrid API client.
        
        Args:
            api_key: SendGrid API key
            from_email: Default sender email
            from_name: Default sender name
        """
        if not SENDGRID_AVAILABLE:
            raise ImportError("sendgrid package not installed. Install with: pip install sendgrid")
        super().__init__(api_key=api_key)
        self.from_email = from_email
        self.from_name = from_name
        self.sg = sendgrid.SendGridAPIClient(api_key=api_key)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email via SendGrid.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body
            from_email: Sender email (uses default if not provided)
            from_name: Sender name (uses default if not provided)
            
        Returns:
            Response with message ID and status
        """
        try:
            message = Mail(
                from_email=Email(from_email or self.from_email, from_name or self.from_name),
                to_emails=to_email,
                subject=subject,
                plain_text_content=body
            )
            
            response = self.sg.send(message)
            
            return {
                "message_id": response.headers.get("X-Message-Id"),
                "status": "sent",
                "provider": "sendgrid",
                "status_code": response.status_code
            }
        except Exception as e:
            raise RuntimeError(f"SendGrid send failed: {str(e)}")
    
    def get_email_stats(
        self,
        message_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get email statistics (opens, clicks, etc.).
        
        Args:
            message_id: Specific message ID (optional)
            start_date: Start date for stats
            end_date: End date for stats
            
        Returns:
            Statistics dictionary
        """
        try:
            # SendGrid stats API endpoint
            params = {}
            if start_date:
                params["start_date"] = start_date.strftime("%Y-%m-%d")
            if end_date:
                params["end_date"] = end_date.strftime("%Y-%m-%d")
            
            response = self.sg.client.stats.get(query_params=params)
            
            if response.status_code == 200:
                stats = response.body
                return {
                    "opens": stats.get("opens", 0),
                    "clicks": stats.get("clicks", 0),
                    "bounces": stats.get("bounces", 0),
                    "spam_reports": stats.get("spam_reports", 0)
                }
            else:
                return {}
        except Exception as e:
            # Return empty stats on error
            return {}
    
    def track_event(
        self,
        message_id: str,
        event_type: str
    ) -> Dict[str, Any]:
        """
        Track email event (open, click, etc.).
        
        Args:
            message_id: Message ID
            event_type: Event type (open, click, bounce, etc.)
            
        Returns:
            Event data dictionary
        """
        # SendGrid webhooks provide event data
        # This is a placeholder for manual tracking if needed
        return {
            "message_id": message_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat()
        }

