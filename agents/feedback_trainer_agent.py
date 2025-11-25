"""
FeedbackTrainerAgent: Analyzes performance and generates optimization recommendations.
"""

from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from configs.secrets_provider import SecretsProvider
import json

try:
    from tools.google_sheets import GoogleSheetsAPI
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    GoogleSheetsAPI = None


class FeedbackTrainerAgent(BaseAgent):
    """
    Agent that analyzes performance and generates recommendations.
    
    Analyzes:
    - Open rates by subject line
    - Reply rates by persona/segment
    - Meeting rates by ICP filter
    - Overall performance metrics
    
    Writes recommendations to Google Sheets for approval.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize FeedbackTrainerAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize Google Sheets API
        self.sheets_api = None
        tool_config = config.get("tool_config", {})
        self.sheets_id = tool_config.get("sheets_id") or secrets_provider.get_google_sheets_id()
        self.worksheet_name = tool_config.get("worksheet_name", "Feedback")
        
        creds_path = secrets_provider.get_google_sheets_creds_path()
        if creds_path and GOOGLE_SHEETS_AVAILABLE and GoogleSheetsAPI:
            try:
                self.sheets_api = GoogleSheetsAPI(
                    credentials_path=creds_path,
                    sheet_id=self.sheets_id
                )
                # Auto-create sheet if needed
                if not self.sheets_id:
                    self.sheets_id = self.sheets_api.create_sheet_if_not_exists(
                        sheet_name=self.worksheet_name,
                        headers=["Run ID", "Field", "Old Value", "New Value", "Reason", "Status", "Created At"]
                    )
            except Exception as e:
                # Log error but continue (skip database logging since run_id is None)
                self.sheets_api = None
                # Only log to file if available
                if logger and hasattr(logger, '_log_to_json'):
                    try:
                        logger._log_to_json(
                            run_id=None,
                            agent_name=self.name,
                            step="error",
                            error_data={"type": "GoogleSheetsInit", "message": str(e)},
                            input_data=None,
                            output_data=None,
                            duration_ms=None
                        )
                    except:
                        pass  # Silently fail if logging not available
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process feedback analysis and generate recommendations.
        
        Args:
            input_data: Input data with responses, messages, leads
            state: Current workflow state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with recommendations and metrics
        """
        responses = input_data.get("responses", [])
        messages = input_data.get("messages", [])
        leads = input_data.get("leads", [])
        tool_config = self.config.get("tool_config", {})
        analytics_metrics = tool_config.get("analytics_metrics", ["open_rate", "reply_rate", "meeting_rate"])
        analysis_dimensions = tool_config.get("analysis_dimensions", ["subject_line", "persona", "icp_filter"])
        
        # Calculate overall metrics
        metrics = self._calculate_metrics(responses, analytics_metrics)
        
        # Analyze performance
        analysis = self._analyze_performance(responses, messages, leads, analysis_dimensions)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, analysis, state)
        
        # Write to Google Sheets
        if self.sheets_api and recommendations:
            try:
                self.sheets_api.write_recommendations(
                    recommendations=recommendations,
                    worksheet_name=self.worksheet_name,
                    run_id=run_id
                )
            except Exception as e:
                if run_id and self.logger:
                    self.logger.log_agent_error(
                        run_id=run_id,
                        agent_name=self.name,
                        error_data={"type": "GoogleSheetsWrite", "message": str(e)}
                    )
        
        return {
            "recommendations": recommendations,
            "metrics": metrics,
            "analysis": analysis,
            "status": "waiting_approval"
        }
    
    def _calculate_metrics(
        self,
        responses: List[Dict[str, Any]],
        metric_names: List[str]
    ) -> Dict[str, float]:
        """
        Calculate performance metrics.
        
        Args:
            responses: List of response dictionaries
            metric_names: List of metric names to calculate
            
        Returns:
            Dictionary of metrics
        """
        total = len(responses)
        if total == 0:
            return {metric: 0.0 for metric in metric_names}
        
        opens = sum(1 for r in responses if r.get("opened", False))
        replies = sum(1 for r in responses if r.get("replied", False))
        meetings = sum(1 for r in responses if r.get("meeting_scheduled", False))
        
        metrics = {}
        if "open_rate" in metric_names:
            metrics["open_rate"] = opens / total if total > 0 else 0.0
        if "reply_rate" in metric_names:
            metrics["reply_rate"] = replies / total if total > 0 else 0.0
        if "meeting_rate" in metric_names:
            metrics["meeting_rate"] = meetings / total if total > 0 else 0.0
        
        return metrics
    
    def _analyze_performance(
        self,
        responses: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        leads: List[Dict[str, Any]],
        dimensions: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze performance by dimension.
        
        Args:
            responses: List of responses
            messages: List of messages
            leads: List of leads
            dimensions: List of dimensions to analyze
            
        Returns:
            Analysis dictionary
        """
        analysis = {}
        
        # Create message_id to response mapping
        response_map = {r.get("message_id"): r for r in responses}
        
        if "subject_line" in dimensions:
            # Analyze by subject line
            subject_performance = {}
            for msg in messages:
                subject = msg.get("subject", "")
                msg_id = msg.get("message_id")
                response = response_map.get(msg_id, {})
                
                if subject not in subject_performance:
                    subject_performance[subject] = {"total": 0, "opens": 0, "replies": 0}
                
                subject_performance[subject]["total"] += 1
                if response.get("opened"):
                    subject_performance[subject]["opens"] += 1
                if response.get("replied"):
                    subject_performance[subject]["replies"] += 1
            
            analysis["subject_line"] = subject_performance
        
        # A/B testing analysis
        ab_variants = {}
        for msg in messages:
            variant = msg.get("ab_variant")
            if variant:
                msg_id = msg.get("message_id")
                response = response_map.get(msg_id, {})
                
                if variant not in ab_variants:
                    ab_variants[variant] = {"total": 0, "opens": 0, "replies": 0, "meetings": 0}
                
                ab_variants[variant]["total"] += 1
                if response.get("opened"):
                    ab_variants[variant]["opens"] += 1
                if response.get("replied"):
                    ab_variants[variant]["replies"] += 1
                if response.get("meeting_scheduled"):
                    ab_variants[variant]["meetings"] += 1
        
        if ab_variants:
            # Calculate rates
            for variant in ab_variants:
                total = ab_variants[variant]["total"]
                ab_variants[variant]["open_rate"] = ab_variants[variant]["opens"] / total if total > 0 else 0
                ab_variants[variant]["reply_rate"] = ab_variants[variant]["replies"] / total if total > 0 else 0
                ab_variants[variant]["meeting_rate"] = ab_variants[variant]["meetings"] / total if total > 0 else 0
            
            analysis["ab_variants"] = ab_variants
        
        # Add other dimension analyses as needed
        
        return analysis
    
    def _generate_recommendations(
        self,
        metrics: Dict[str, float],
        analysis: Dict[str, Any],
        state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate optimization recommendations.
        
        Args:
            metrics: Performance metrics
            analysis: Performance analysis
            state: Current workflow state
            
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        # Analyze metrics and suggest improvements
        if metrics.get("open_rate", 0) < 0.2:
            recommendations.append({
                "field": "outreach_content.tone",
                "old_value": "friendly, concise, value-driven",
                "new_value": "more urgent, benefit-focused",
                "reason": f"Low open rate ({metrics.get('open_rate', 0):.1%}). Suggest more compelling subject lines."
            })
        
        if metrics.get("reply_rate", 0) < 0.05:
            recommendations.append({
                "field": "outreach_content.body",
                "old_value": "current template",
                "new_value": "shorter, more direct CTA",
                "reason": f"Low reply rate ({metrics.get('reply_rate', 0):.1%}). Suggest shorter emails with clearer value proposition."
            })
        
        # Analyze subject line performance
        subject_analysis = analysis.get("subject_line", {})
        if subject_analysis:
            best_subject = max(
                subject_analysis.items(),
                key=lambda x: x[1].get("opens", 0) / max(x[1].get("total", 1), 1)
            )[0]
            
            recommendations.append({
                "field": "outreach_content.subject_template",
                "old_value": "current",
                "new_value": best_subject,
                "reason": f"Best performing subject line: {best_subject}"
            })
        
        # A/B testing analysis
        if analysis.get("ab_variants"):
            ab_analysis = analysis["ab_variants"]
            best_variant = max(
                ab_analysis.items(),
                key=lambda x: x[1].get("reply_rate", 0)
            )[0]
            
            recommendations.append({
                "field": "outreach_content.ab_testing.variants",
                "old_value": "current variants",
                "new_value": best_variant,
                "reason": f"Best performing A/B variant: {best_variant} with {ab_analysis[best_variant].get('reply_rate', 0):.1%} reply rate"
            })
        
        # Scoring weights recommendations
        if metrics.get("reply_rate", 0) < 0.05:
            recommendations.append({
                "field": "scoring.weights.fit_score",
                "old_value": 0.5,
                "new_value": 0.6,
                "reason": "Increase fit score weight to target better-fitting companies."
            })
        
        return recommendations
    

