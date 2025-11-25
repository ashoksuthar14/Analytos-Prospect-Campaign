"""
Rate Limiter: Enforces rate limits for workflow execution.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from database.db_service import DatabaseService
import json


class RateLimiter:
    """
    Rate limiter for workflow execution.
    
    Enforces:
    - Maximum leads per run (default: 50)
    - Maximum leads per day (default: 200)
    """
    
    def __init__(
        self,
        db_service: DatabaseService,
        max_leads_per_run: int = 50,
        max_leads_per_day: int = 200
    ):
        """
        Initialize rate limiter.
        
        Args:
            db_service: Database service instance
            max_leads_per_run: Maximum leads per run
            max_leads_per_day: Maximum leads per day
        """
        self.db_service = db_service
        self.max_leads_per_run = max_leads_per_run
        self.max_leads_per_day = max_leads_per_day
    
    def check_run_limit(self, requested_leads: int) -> tuple[bool, Optional[str]]:
        """
        Check if run limit would be exceeded.
        
        Args:
            requested_leads: Number of leads requested for this run
            
        Returns:
            Tuple of (allowed, error_message)
        """
        if requested_leads > self.max_leads_per_run:
            return False, (
                f"Requested {requested_leads} leads exceeds limit of "
                f"{self.max_leads_per_run} leads per run"
            )
        
        return True, None
    
    def check_daily_limit(self, requested_leads: int) -> tuple[bool, Optional[str]]:
        """
        Check if daily limit would be exceeded.
        
        Args:
            requested_leads: Number of leads requested for this run
            
        Returns:
            Tuple of (allowed, error_message, leads_used_today)
        """
        # Get leads used today
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        # Get all runs started today
        runs_today = self.db_service.get_runs(
            status=None,  # All statuses
            limit=1000  # Get all runs
        )
        
        total_leads_today = 0
        for run in runs_today:
            run_started = datetime.fromisoformat(run['started_at'].replace('Z', '+00:00'))
            if run_started.date() == today:
                # Get metrics to count leads
                metrics = run.get('metrics')
                if metrics:
                    if isinstance(metrics, str):
                        try:
                            metrics = json.loads(metrics)
                        except:
                            metrics = {}
                    total_leads_today += metrics.get('total_leads', 0)
        
        if total_leads_today + requested_leads > self.max_leads_per_day:
            remaining = self.max_leads_per_day - total_leads_today
            return False, (
                f"Daily limit exceeded. Used {total_leads_today}/{self.max_leads_per_day} leads today. "
                f"Requested {requested_leads} would exceed limit. Remaining: {remaining}"
            ), total_leads_today
        
        return True, None, total_leads_today
    
    def check_all_limits(self, requested_leads: int) -> tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check all rate limits.
        
        Args:
            requested_leads: Number of leads requested
            
        Returns:
            Tuple of (allowed, error_message, usage_info)
        """
        # Check run limit
        run_allowed, run_error = self.check_run_limit(requested_leads)
        if not run_allowed:
            return False, run_error, {}
        
        # Check daily limit
        daily_allowed, daily_error, leads_used = self.check_daily_limit(requested_leads)
        if not daily_allowed:
            return False, daily_error, {"leads_used_today": leads_used}
        
        return True, None, {
            "leads_used_today": leads_used,
            "leads_remaining_today": self.max_leads_per_day - leads_used - requested_leads
        }
