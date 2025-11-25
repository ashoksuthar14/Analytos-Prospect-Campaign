"""
Base Agent class with ReAct-style reasoning using Groq/OpenAI/Gemini.
"""

import json
import time
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from configs.secrets_provider import SecretsProvider

# Try to import Groq, OpenAI, and Gemini
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


LIST_INPUT_KEYS = {
    "leads",
    "ranked_leads",
    "messages",
    "message_ids",
    "responses",
    "recommendations",
    "pending_recommendations",
    "pending_feedback"
}


class BaseAgent(ABC):
    """
    Base class for all campaign agents.
    
    Provides:
    - ReAct-style reasoning with Groq/OpenAI/Gemini
    - Tool calling interface
    - Input/output handling
    - Error handling
    """
    
    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        secrets_provider: SecretsProvider,
        logger: Optional[Any] = None
    ):
        """
        Initialize base agent.
        
        Args:
            name: Agent name
            config: Agent configuration from campaign.json
            secrets_provider: Secrets provider instance
            logger: RunLogger instance (optional)
        """
        self.name = name
        self.config = config
        self.secrets_provider = secrets_provider
        self.logger = logger
        
        # Initialize LLM (prioritize Groq over OpenAI over Gemini)
        self.llm_provider = None
        self.model = None
        self.openai_client = None
        self.groq_client = None
        
        # Try Groq first (for outreach message generation)
        groq_key = secrets_provider.get_groq_api_key()
        if groq_key and GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=groq_key)
                self.llm_provider = "groq"
                print(f"[{self.name}] ✅ Using Groq for content generation")
            except Exception as e:
                print(f"[{self.name}] ❌ Groq initialization failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            if not groq_key:
                print(f"[{self.name}] ⚠️  Groq API key not found")
            if not GROQ_AVAILABLE:
                print(f"[{self.name}] ⚠️  Groq library not available")
        
        # Fallback to OpenAI if Groq not available (only for non-outreach agents)
        if not self.llm_provider:
            openai_key = secrets_provider.get_openai_api_key()
            if openai_key and OPENAI_AVAILABLE:
                try:
                    self.openai_client = OpenAI(api_key=openai_key)
                    self.llm_provider = "openai"
                    print(f"[{self.name}] ⚠️  Using OpenAI as fallback (Groq not available)")
                except Exception as e:
                    print(f"[{self.name}] ❌ OpenAI initialization failed: {e}")
        
        # Fallback to Gemini if neither Groq nor OpenAI available
        if not self.llm_provider:
            gemini_key = secrets_provider.get_gemini_api_key()
            if gemini_key and GEMINI_AVAILABLE:
                try:
                    genai.configure(api_key=gemini_key)
                    model_name = config.get("tool_config", {}).get("model", "gemini-2.0-flash-exp")
                    self.model = genai.GenerativeModel(model_name)
                    self.llm_provider = "gemini"
                    print(f"[{self.name}] Using Gemini for content generation")
                except Exception as e:
                    print(f"[{self.name}] Gemini initialization failed: {e}")
    
    def execute(
        self,
        state: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the agent with ReAct-style reasoning.
        
        Args:
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Updated state with agent output
        """
        if run_id and self.logger:
            self.logger.log_agent_start(
                run_id=run_id,
                agent_name=self.name,
                input_data=self._extract_input(state)
            )
        
        start_time = time.time()
        
        try:
            # Extract input from state based on agent config
            input_data = self._extract_input(state)
            
            # Perform agent-specific execution
            output_data = self._execute_agent(input_data, state, run_id)
            
            # Update state with output
            updated_state = self._update_state(state, output_data)
            
            # Record timing (optional - don't fail campaign if metrics fail)
            duration_ms = (time.time() - start_time) * 1000
            if run_id:
                try:
                    from utils.observability import metrics_collector as obs_metrics
                    if obs_metrics:
                        obs_metrics.record_node_timing(run_id, self.name, duration_ms)
                except (ImportError, AttributeError, Exception):
                    # Silently fail if metrics recording fails - don't break campaign
                    pass
            
            if run_id and self.logger:
                # Handle both RunLogger and DetailedLogger
                try:
                    # Try RunLogger method first
                    if hasattr(self.logger, 'log_agent_output'):
                        self.logger.log_agent_output(
                            run_id=run_id,
                            agent_name=self.name,
                            output_data=output_data,
                            duration_ms=int(duration_ms)
                        )
                    # Otherwise skip logging - agents use their own DetailedLogger
                except (AttributeError, Exception):
                    # If method doesn't exist or fails, skip logging
                    pass
            
            return updated_state
            
        except Exception as e:
            # Record error
            from utils.error_handler import ErrorHandler
            
            # Get error type
            try:
                error_type = ErrorHandler.categorize_error(e).value if ErrorHandler else "unknown"
            except:
                error_type = "unknown"
            
            # Try to record in metrics (optional - don't fail campaign if metrics fail)
            if run_id:
                try:
                    from utils.metrics_collector import metrics_collector as metrics
                    if metrics:
                        metrics.record_error(self.name, e)
                except (ImportError, AttributeError, Exception):
                    # Silently fail if metrics recording fails - don't break campaign
                    pass
            
            error_data = {
                "type": type(e).__name__,
                "error_type": error_type,
                "message": str(e),
                "traceback": self._get_traceback(e)
            }
            
            if run_id and self.logger:
                self.logger.log_agent_error(
                    run_id=run_id,
                    agent_name=self.name,
                    error_data=error_data
                )
            
            raise
    
    def _extract_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract input data from state based on agent configuration.
        
        Args:
            state: Current campaign state
            
        Returns:
            Input data dictionary
        """
        # Get base inputs config
        inputs_config = self.config.get("inputs", {}).copy()
        
        # Apply config overrides from state if present
        config_overrides = state.get("config_overrides", {})
        if config_overrides and isinstance(config_overrides, dict):
            # Check if there are overrides for this agent
            agent_overrides = config_overrides.get("agents", {}).get(self.name, {})
            if agent_overrides:
                # Deep merge agent-specific overrides into inputs
                if "inputs" in agent_overrides:
                    inputs_config = self._deep_merge_dicts(inputs_config, agent_overrides["inputs"])
                # Also update tool_config in self.config for other methods that use it
                if "tool_config" in agent_overrides:
                    self.config["tool_config"] = self._deep_merge_dicts(
                        self.config.get("tool_config", {}),
                        agent_overrides["tool_config"]
                    )
        
        input_data = {}
        
        for key, value in inputs_config.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                # Reference to previous agent output
                ref_path = value[2:-2].strip()  # Remove {{ and }}
                resolved_value = self._resolve_reference(state, ref_path)

                # Handle different reference formats:
                # 1. "prospect_search.output" -> try "prospect_search_output" first
                # 2. "prospect_search_output.leads" -> direct path
                if resolved_value is None and "." in ref_path:
                    parts = ref_path.split(".")
                    agent_name = parts[0]
                    alt_ref = f"{agent_name}_output"

                    if alt_ref in state:
                        output_data = state.get(alt_ref, {})

                        if ref_path.endswith(".output"):
                            # If the caller expects a list (e.g. leads), surface the list value directly
                            if isinstance(output_data, dict):
                                if key in output_data:
                                    resolved_value = output_data.get(key)
                                else:
                                    # Common fallbacks for list-like payloads
                                    resolved_value = (
                                        output_data.get("leads")
                                        or output_data.get("ranked_leads")
                                        or output_data.get("messages")
                                        or output_data.get("results")
                                        or output_data
                                    )
                            else:
                                resolved_value = output_data
                        else:
                            # Try the full path with _output prefix
                            remaining_path = ".".join(parts[1:])
                            if remaining_path:
                                alt_ref_path = f"{alt_ref}.{remaining_path}"
                                resolved_value = self._resolve_reference(state, alt_ref_path)

                # If we still have a dict and the requested key exists within it, extract it
                if isinstance(resolved_value, dict) and key in resolved_value:
                    resolved_value = resolved_value.get(key)

                # Default list-like keys to empty lists instead of None
                if resolved_value is None and key in LIST_INPUT_KEYS:
                    resolved_value = []

                input_data[key] = resolved_value
            elif isinstance(value, (dict, list)):
                # Direct value
                input_data[key] = value
            else:
                input_data[key] = value
        
        return input_data
    
    def _resolve_reference(self, state: Dict[str, Any], ref_path: str) -> Any:
        """
        Resolve reference path in state (e.g., "prospect_search.output" or "prospect_search_output.leads").
        
        Args:
            state: Current campaign state
            ref_path: Reference path
            
        Returns:
            Resolved value or None if not found
        """
        parts = ref_path.split(".")
        value = state
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                value = value[int(part)]
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _deep_merge_dicts(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_dicts(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _update_state(
        self,
        state: Dict[str, Any],
        output_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update state with agent output.
        
        Args:
            state: Current campaign state
            output_data: Agent output data
            
        Returns:
            Updated state
        """
        updated_state = state.copy()
        updated_state[f"{self.name}_output"] = output_data
        updated_state["last_agent"] = self.name
        return updated_state
    
    def _execute_agent(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute agent-specific logic.
        
        This method should be implemented by subclasses.
        
        Args:
            input_data: Extracted input data
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Output data dictionary
        """
        return self._process(input_data, state, run_id)
    
    @abstractmethod
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process agent logic (to be implemented by subclasses).
        
        Args:
            input_data: Input data
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Output data dictionary
        """
        pass
    
    def _call_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call a tool and log it.
        
        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters
            run_id: Run ID for logging
            
        Returns:
            Tool output
        """
        
        # This will be implemented by subclasses or tool manager
        # For now, it's a placeholder
        if run_id and self.logger:
            self.logger.log_tool_call(
                run_id=run_id,
                agent_name=self.name,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=None
            )
        
        return {}
    
    def _reason_with_gemini(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Use LLM (Groq, OpenAI, or Gemini) for reasoning/task planning.
        
        Args:
            prompt: Prompt for LLM
            context: Additional context dictionary
            temperature: Temperature for generation
            
        Returns:
            LLM response text
        """
        # Get temperature from config or use default
        if temperature is None:
            temperature = self.config.get("tool_config", {}).get("temperature", 0.7)
        
        max_tokens = self.config.get("tool_config", {}).get("max_tokens", 1000)
        
        # Use Groq if available (prioritized for outreach messages)
        if self.llm_provider == "groq" and self.groq_client:
            try:
                # Get model from config or use default (try newer models first)
                model_name = self.config.get("tool_config", {}).get("model", "llama-3.3-70b-versatile")
                
                # Fallback models if primary fails
                models_to_try = [model_name, "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
                last_error = None
                
                for model in models_to_try:
                    try:
                        print(f"[{self.name}] 🚀 Calling Groq API with model: {model}")
                        response = self.groq_client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": "You are a professional B2B sales email writer."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        result = response.choices[0].message.content.strip()
                        print(f"[{self.name}] ✅ Groq API call successful with {model}")
                        return result
                    except Exception as e:
                        last_error = str(e)
                        if "decommissioned" not in str(e).lower():
                            # If it's not a decommissioned model error, raise it
                            raise
                        continue
                
                # If all models failed
                raise RuntimeError(f"All Groq models failed. Last error: {last_error}")
            except Exception as e:
                print(f"[{self.name}] ❌ Groq API error: {str(e)}")
                import traceback
                traceback.print_exc()
                raise RuntimeError(f"Groq API error: {str(e)}")
        
        # Fallback to OpenAI if Groq not available
        elif self.llm_provider == "openai" and self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Fast and cost-effective
                    messages=[
                        {"role": "system", "content": "You are a professional B2B sales email writer."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                raise RuntimeError(f"OpenAI API error: {str(e)}")
        
        # Fallback to Gemini
        elif self.llm_provider == "gemini" and self.model:
            try:
                from google.generativeai.types import HarmCategory, HarmBlockThreshold
                
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens
                    },
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )
                
                # Check if response was blocked
                if not response.candidates:
                    raise RuntimeError("Gemini API returned no candidates (empty response)")
                
                # Check for safety blocks
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    if str(candidate.finish_reason) == "FinishReason.SAFETY":
                        safety_ratings = []
                        if hasattr(candidate, 'safety_ratings'):
                            safety_ratings = [f"{r.category.name}:{r.probability.name}" for r in candidate.safety_ratings]
                        raise RuntimeError(f"Gemini content blocked by safety filters: {', '.join(safety_ratings)}")
                
                # Try to get text
                if hasattr(response, 'text') and response.text:
                    return response.text
                
                # Fallback: extract from parts
                if candidate.content and candidate.content.parts:
                    text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text')]
                    if text_parts:
                        return "".join(text_parts)
                
                raise RuntimeError("Gemini API returned candidates without usable text content")
                
            except Exception as e:
                raise RuntimeError(f"Gemini API error: {str(e)}")
        
        else:
            error_msg = f"No LLM provider initialized for {self.name}. "
            if not self.groq_client:
                error_msg += "Groq not available. "
            if not self.openai_client:
                error_msg += "OpenAI not available. "
            if not self.model:
                error_msg += "Gemini not available. "
            error_msg += "Please check GROQ_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY."
            raise ValueError(error_msg)
    
    def _get_traceback(self, exception: Exception) -> str:
        """Get traceback string from exception."""
        import traceback
        return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    
    def check_condition(self, state: Dict[str, Any]) -> bool:
        """
        Check conditional branching condition if defined.
        
        Args:
            state: Current campaign state
            
        Returns:
            True if condition passes, False otherwise
        """
        conditional = self.config.get("conditional_branching")
        if not conditional:
            return True
        
        condition = conditional.get("condition")
        if not condition:
            return True
        
        # Parse condition (simple evaluations for now)
        # Example: "score < 50"
        try:
            # Get the value to check
            if "<" in condition:
                key, threshold = condition.split("<")
                key = key.strip()
                threshold = float(threshold.strip())
                
                # Resolve key from state
                value = self._resolve_reference(state, key)
                if value is None:
                    return True  # Default to pass if value not found
                
                return float(value) >= threshold  # Pass if condition is NOT met (to continue)
            elif ">" in condition:
                key, threshold = condition.split(">")
                key = key.strip()
                threshold = float(threshold.strip())
                
                value = self._resolve_reference(state, key)
                if value is None:
                    return True
                
                return float(value) <= threshold
            else:
                # Default to pass if condition format not recognized
                return True
        except Exception:
            # Default to pass on error
            return True

