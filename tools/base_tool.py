"""
Base tool class with retry logic and error handling.
"""

import time
import requests
from typing import Dict, Any, Optional, Callable
from functools import wraps


def retry_with_backoff(
    max_retries: int = 3,
    backoff_multiplier: float = 2,
    initial_delay: float = 1.0
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_multiplier: Multiplier for exponential backoff
        initial_delay: Initial delay in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= backoff_multiplier
                    else:
                        raise
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class BaseTool:
    """
    Base class for API integration tools.
    
    Provides:
    - Retry logic with exponential backoff
    - Error handling
    - Rate limiting support
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize base tool.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        if api_key:
            self._setup_auth()
    
    def _setup_auth(self) -> None:
        """Setup authentication headers."""
        # Override in subclasses
        pass
    
    @retry_with_backoff(max_retries=3, backoff_multiplier=2)
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            headers: Additional headers
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        url = f"{self.base_url}{endpoint}" if self.base_url else endpoint
        request_headers = headers or {}
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=request_headers,
                timeout=30
            )
            response.raise_for_status()
            
            # Handle empty responses
            if not response.text:
                return {}
            
            try:
                return response.json()
            except ValueError:
                # If response is not JSON, return text
                return {"response": response.text, "status_code": response.status_code}
                
        except requests.exceptions.HTTPError as e:
            # Try to get error message from response
            error_msg = str(e)
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                    if not error_msg:
                        error_msg = str(e)
                except:
                    error_msg = e.response.text or str(e)
            
            if e.response and e.response.status_code == 429:
                # Rate limit exceeded
                retry_after = int(e.response.headers.get("Retry-After", 60))
                time.sleep(retry_after)
                raise RuntimeError(f"Rate limit exceeded: {error_msg}")
            
            raise RuntimeError(f"API request failed ({e.response.status_code if e.response else 'unknown'}): {error_msg}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request failed: {str(e)}")

