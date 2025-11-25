"""
SecretsProvider: Manages API keys and credentials.
Uses hardcoded API keys from configs.api_keys module.
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

# Try to import hardcoded API keys
try:
    from configs.api_keys import (
        CLAY_API_KEY,
        APOLLO_API_KEY,
        GEMINI_API_KEY,
        SENDGRID_API_KEY,
        SENDER_EMAIL,
        SENDGRID_FROM_EMAIL,
        SENDGRID_FROM_NAME,
        PDL_API_KEY,
        EXPLORIUM_API_KEY,
        OPENAI_API_KEY,
        GROQ_API_KEY,
        HUNTER_API_KEY,
        GOOGLE_SHEETS_CREDS,
        GOOGLE_SHEETS_ID,
        DATABASE_PATH,
        SECRET_KEY,
        LOG_DIR,
        LOG_LEVEL,
        ENABLE_FULL_TRACES,
        MAX_LEADS_PER_RUN,
        MAX_LEADS_PER_DAY
    )
    USE_HARDCODED_KEYS = True
except ImportError:
    # Fallback to environment variables if api_keys.py doesn't exist
    USE_HARDCODED_KEYS = False
    from dotenv import load_dotenv


class SecretsProvider:
    """
    Provides API keys and credentials from environment variables.
    
    Handles:
    - Loading .env file
    - Providing keys to agents/tools
    - Redacting keys in logs
    """
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize secrets provider.
        
        Args:
            env_file: Path to .env file (only used if hardcoded keys not available)
        """
        self.env_file = env_file
        self._secrets_cache: Dict[str, str] = {}
        
        if not USE_HARDCODED_KEYS:
            self._load_env()
    
    def _load_env(self) -> None:
        """Load environment variables from .env file (fallback only)."""
        try:
            from dotenv import load_dotenv
            env_path = Path(self.env_file)
            
            if env_path.exists():
                load_dotenv(env_path)
            else:
                # Try loading from project root
                root_env = Path(".") / self.env_file
                if root_env.exists():
                    load_dotenv(root_env)
        except ImportError:
            pass  # dotenv not available
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value by key.
        
        Args:
            key: Secret key name
            default: Default value if not found
            
        Returns:
            Secret value or default
        """
        if key in self._secrets_cache:
            return self._secrets_cache[key]
        
        # Use hardcoded keys if available
        if USE_HARDCODED_KEYS:
            value = self._get_hardcoded_secret(key)
        else:
            # Fallback to environment variables
            value = os.getenv(key, default)
        
        if value:
            self._secrets_cache[key] = value
        
        return value or default
    
    def _get_hardcoded_secret(self, key: str) -> Optional[str]:
        """Get secret from hardcoded API keys."""
        from configs.api_keys import (
            CLAY_API_KEY,
            APOLLO_API_KEY,
            GEMINI_API_KEY,
            SENDGRID_API_KEY,
            SENDER_EMAIL,
            SENDGRID_FROM_EMAIL,
            SENDGRID_FROM_NAME,
            PDL_API_KEY,
            EXPLORIUM_API_KEY,
            OPENAI_API_KEY,
            GROQ_API_KEY,
            HUNTER_API_KEY,
            GOOGLE_SHEETS_CREDS,
            GOOGLE_SHEETS_ID,
            DATABASE_PATH,
            SECRET_KEY,
            LOG_DIR,
            LOG_LEVEL,
            ENABLE_FULL_TRACES,
            MAX_LEADS_PER_RUN,
            MAX_LEADS_PER_DAY
        )
        
        key_mapping = {
            "CLAY_API_KEY": CLAY_API_KEY,
            "APOLLO_API_KEY": APOLLO_API_KEY,
            "GEMINI_API_KEY": GEMINI_API_KEY,
            "SENDGRID_API_KEY": SENDGRID_API_KEY,
            "SENDER_EMAIL": SENDER_EMAIL,
            "SENDGRID_FROM_EMAIL": SENDGRID_FROM_EMAIL,
            "SENDGRID_FROM_NAME": SENDGRID_FROM_NAME,
            "PDL_API_KEY": PDL_API_KEY,
            "EXPLORIUM_API_KEY": EXPLORIUM_API_KEY,
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "GROQ_API_KEY": GROQ_API_KEY,
            "HUNTER_API_KEY": HUNTER_API_KEY,
            "GOOGLE_SHEETS_CREDS": GOOGLE_SHEETS_CREDS,
            "GOOGLE_SHEETS_ID": GOOGLE_SHEETS_ID,
            "DATABASE_PATH": DATABASE_PATH,
            "SECRET_KEY": SECRET_KEY,
            "LOG_DIR": LOG_DIR,
            "LOG_LEVEL": LOG_LEVEL,
            "ENABLE_FULL_TRACES": str(ENABLE_FULL_TRACES).lower(),
            "MAX_LEADS_PER_RUN": str(MAX_LEADS_PER_RUN),
            "MAX_LEADS_PER_DAY": str(MAX_LEADS_PER_DAY),
        }
        
        return key_mapping.get(key)
    
    def get_gemini_api_key(self) -> Optional[str]:
        """Get Google Gemini API key."""
        return self.get_secret("GEMINI_API_KEY")
    
    def get_clay_api_key(self) -> Optional[str]:
        """Get Clay API key."""
        return self.get_secret("CLAY_API_KEY")
    
    def get_apollo_api_key(self) -> Optional[str]:
        """Get Apollo API key."""
        return self.get_secret("APOLLO_API_KEY")
    
    def get_explorium_api_key(self) -> Optional[str]:
        """Get Explorium API key."""
        return self.get_secret("EXPLORIUM_API_KEY")
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return self.get_secret("OPENAI_API_KEY")
    
    def get_groq_api_key(self) -> Optional[str]:
        """Get Groq API key."""
        return self.get_secret("GROQ_API_KEY")
    
    def get_hunter_api_key(self) -> Optional[str]:
        """Get Hunter.io API key."""
        return self.get_secret("HUNTER_API_KEY")
    
    def get_clearbit_api_key(self) -> Optional[str]:
        """Get Clearbit API key."""
        return self.get_secret("CLEARBIT_API_KEY")
    
    def get_pdl_api_key(self) -> Optional[str]:
        """Get PDL API key."""
        return self.get_secret("PDL_API_KEY")
    
    def get_sendgrid_api_key(self) -> Optional[str]:
        """Get SendGrid API key."""
        return self.get_secret("SENDGRID_API_KEY")
    
    def get_sendgrid_from_email(self) -> Optional[str]:
        """Get SendGrid from email."""
        # Try SENDGRID_FROM_EMAIL first, fallback to SENDER_EMAIL
        return self.get_secret("SENDGRID_FROM_EMAIL") or self.get_secret("SENDER_EMAIL")
    
    def get_sendgrid_from_name(self) -> Optional[str]:
        """Get SendGrid from name."""
        return self.get_secret("SENDGRID_FROM_NAME")
    
    def get_google_sheets_creds_path(self) -> Optional[str]:
        """Get Google Sheets service account credentials path."""
        return self.get_secret("GOOGLE_SHEETS_CREDS")
    
    def get_google_sheets_id(self) -> Optional[str]:
        """Get Google Sheets ID."""
        return self.get_secret("GOOGLE_SHEETS_ID")
    
    def get_database_path(self) -> str:
        """Get database path."""
        return self.get_secret("DATABASE_PATH", "./database/prospect_workflow.db")
    
    def redact_secret(self, text: str) -> str:
        """
        Redact secret values from text (for logging).
        
        Args:
            text: Text that may contain secrets
            
        Returns:
            Text with secrets redacted
        """
        redacted = text
        
        # Redact common API key patterns
        for key, value in self._secrets_cache.items():
            if value and len(value) > 8:
                # Replace with masked version
                masked = value[:4] + "*" * (len(value) - 8) + value[-4:]
                redacted = redacted.replace(value, masked)
        
        # Redact email addresses (PII)
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        redacted = re.sub(email_pattern, '[EMAIL_REDACTED]', redacted)
        
        # Redact phone numbers (PII)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        redacted = re.sub(phone_pattern, '[PHONE_REDACTED]', redacted)
        
        return redacted
    
    def validate_required_secrets(self, required_keys: list[str]) -> Dict[str, bool]:
        """
        Validate that required secrets are present.
        
        Args:
            required_keys: List of required secret keys
            
        Returns:
            Dictionary mapping keys to presence status
        """
        status = {}
        
        for key in required_keys:
            value = self.get_secret(key)
            status[key] = value is not None and value != ""
        
        return status
    
    def inject_into_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject secrets into a tool configuration dictionary.
        
        Args:
            config: Tool configuration dictionary
            
        Returns:
            Configuration with secrets injected
        """
        injected = config.copy()
        
        # Map of config keys to secret getters
        secret_mappings = {
            "gemini_api_key": self.get_gemini_api_key,
            "clay_api_key": self.get_clay_api_key,
            "apollo_api_key": self.get_apollo_api_key,
            "clearbit_api_key": self.get_clearbit_api_key,
            "pdl_api_key": self.get_pdl_api_key,
            "sendgrid_api_key": self.get_sendgrid_api_key,
            "from_email": self.get_sendgrid_from_email,
            "from_name": self.get_sendgrid_from_name,
        }
        
        for key, getter in secret_mappings.items():
            if key in injected:
                secret = getter()
                if secret:
                    injected[key] = secret
        
        return injected

