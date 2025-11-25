"""
Error Handler: Categorizes and handles errors gracefully.
"""

from typing import Dict, Any, Optional
from enum import Enum
import traceback


class ErrorCategory(Enum):
    """Error categories for handling."""
    TRANSIENT = "transient"  # Retryable (network, rate limits)
    PERMANENT = "permanent"  # Not retryable (invalid input, auth)
    SYSTEM = "system"  # System errors (database, config)
    API_ERROR = "api_error"  # API-specific errors


class ErrorHandler:
    """
    Handles and categorizes errors.
    
    Provides:
    - Error categorization
    - Graceful degradation
    - Error context extraction
    """
    
    @staticmethod
    def categorize_error(error: Exception) -> ErrorCategory:
        """
        Categorize an error.
        
        Args:
            error: Exception instance
            
        Returns:
            Error category
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Transient errors (retryable)
        transient_indicators = [
            "timeout", "connection", "network", "rate limit", "429",
            "503", "502", "temporary", "retry"
        ]
        
        if any(indicator in error_message for indicator in transient_indicators):
            return ErrorCategory.TRANSIENT
        
        # API errors
        if "api" in error_message or error_type in ["HTTPError", "RequestException"]:
            if "401" in error_message or "403" in error_message:
                return ErrorCategory.PERMANENT  # Auth errors are permanent
            return ErrorCategory.API_ERROR
        
        # System errors
        system_types = ["DatabaseError", "ConfigError", "ValueError"]
        if error_type in system_types:
            return ErrorCategory.SYSTEM
        
        # Default to permanent (don't retry unknown errors)
        return ErrorCategory.PERMANENT
    
    @staticmethod
    def extract_error_context(error: Exception) -> Dict[str, Any]:
        """
        Extract error context for logging.
        
        Args:
            error: Exception instance
            
        Returns:
            Error context dictionary
        """
        return {
            "type": type(error).__name__,
            "message": str(error),
            "category": ErrorHandler.categorize_error(error).value,
            "traceback": traceback.format_exc()
        }
    
    @staticmethod
    def should_retry(error: Exception, attempt: int, max_attempts: int = 3) -> bool:
        """
        Determine if error should be retried.
        
        Args:
            error: Exception instance
            attempt: Current attempt number
            max_attempts: Maximum retry attempts
            
        Returns:
            True if should retry
        """
        if attempt >= max_attempts:
            return False
        
        category = ErrorHandler.categorize_error(error)
        return category in [ErrorCategory.TRANSIENT, ErrorCategory.API_ERROR]
    
    @staticmethod
    def handle_error(
        error: Exception,
        context: Dict[str, Any],
        logger: Optional[Any] = None,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle error with graceful degradation.
        
        Args:
            error: Exception instance
            context: Additional context
            logger: Logger instance (optional)
            run_id: Run ID (optional)
            
        Returns:
            Error response dictionary
        """
        category = ErrorHandler.categorize_error(error)
        error_context = ErrorHandler.extract_error_context(error)
        error_context.update(context)
        
        # Log error
        if logger and run_id:
            logger.log_agent_error(
                run_id=run_id,
                agent_name=context.get("agent_name", "unknown"),
                error_data=error_context
            )
        
        # Determine action based on category
        if category == ErrorCategory.TRANSIENT:
            return {
                "error": True,
                "category": category.value,
                "message": "Temporary error occurred. Will retry.",
                "retryable": True,
                "context": error_context
            }
        elif category == ErrorCategory.PERMANENT:
            return {
                "error": True,
                "category": category.value,
                "message": str(error),
                "retryable": False,
                "context": error_context
            }
        else:
            return {
                "error": True,
                "category": category.value,
                "message": str(error),
                "retryable": False,
                "context": error_context
            }
