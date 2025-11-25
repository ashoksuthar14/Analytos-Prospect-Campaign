"""
Input Validator: Validates inputs for API endpoints and agents.
"""

from typing import Dict, Any, List, Optional
import re
import json


class InputValidator:
    """
    Validates inputs for API endpoints and workflow components.
    
    Provides:
    - Input validation
    - SQL injection prevention
    - XSS prevention
    - Data type validation
    """
    
    @staticmethod
    def validate_workflow_name(name: str) -> tuple[bool, Optional[str]]:
        """
        Validate workflow name.
        
        Args:
            name: Workflow name
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not name or not isinstance(name, str):
            return False, "Workflow name must be a non-empty string"
        
        if len(name) > 100:
            return False, "Workflow name must be less than 100 characters"
        
        # Check for SQL injection patterns
        if re.search(r"[';\"\\]", name):
            return False, "Workflow name contains invalid characters"
        
        return True, None
    
    @staticmethod
    def validate_run_id(run_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate run ID format.
        
        Args:
            run_id: Run ID
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not run_id or not isinstance(run_id, str):
            return False, "Run ID must be a non-empty string"
        
        # UUID format validation
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, run_id, re.IGNORECASE):
            return False, "Invalid run ID format"
        
        return True, None
    
    @staticmethod
    def validate_icp(icp: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate ICP (Ideal Customer Profile) data.
        
        Args:
            icp: ICP dictionary
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not isinstance(icp, dict):
            return False, "ICP must be a dictionary"
        
        # Validate revenue range
        if "revenue_range" in icp:
            revenue_range = icp["revenue_range"]
            if isinstance(revenue_range, dict):
                min_rev = revenue_range.get("min")
                max_rev = revenue_range.get("max")
                if min_rev is not None and not isinstance(min_rev, (int, float)):
                    return False, "Revenue min must be a number"
                if max_rev is not None and not isinstance(max_rev, (int, float)):
                    return False, "Revenue max must be a number"
                if min_rev is not None and max_rev is not None and min_rev > max_rev:
                    return False, "Revenue min must be less than max"
        
        # Validate employee count
        if "employee_count" in icp:
            emp_count = icp["employee_count"]
            if isinstance(emp_count, dict):
                min_emp = emp_count.get("min")
                max_emp = emp_count.get("max")
                if min_emp is not None and not isinstance(min_emp, int):
                    return False, "Employee min must be an integer"
                if max_emp is not None and not isinstance(max_emp, int):
                    return False, "Employee max must be an integer"
                if min_emp is not None and max_emp is not None and min_emp > max_emp:
                    return False, "Employee min must be less than max"
        
        return True, None
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """
        Sanitize string input.
        
        Args:
            value: String value
            max_length: Maximum length
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value)[:max_length]
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', value)
        return sanitized[:max_length]
    
    @staticmethod
    def validate_pagination(limit: int, offset: int) -> tuple[bool, Optional[str]]:
        """
        Validate pagination parameters.
        
        Args:
            limit: Limit value
            offset: Offset value
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            return False, "Limit must be an integer between 1 and 1000"
        
        if not isinstance(offset, int) or offset < 0:
            return False, "Offset must be a non-negative integer"
        
        return True, None
    
    @staticmethod
    def validate_json_structure(data: Any, required_fields: List[str]) -> tuple[bool, Optional[str]]:
        """
        Validate JSON structure has required fields.
        
        Args:
            data: Data to validate
            required_fields: List of required field names
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not isinstance(data, dict):
            return False, "Data must be a dictionary"
        
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        return True, None
    
    @staticmethod
    def prevent_sql_injection(value: str) -> bool:
        """
        Check if value contains SQL injection patterns.
        
        Args:
            value: String value to check
            
        Returns:
            True if safe, False if potentially dangerous
        """
        dangerous_patterns = [
            r"([';])+.*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)",
            r"(--|#|/\*|\*/)",
            r"(UNION|SELECT).*FROM",
            r"EXEC\s*\(|EXECUTE\s*\("
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True
