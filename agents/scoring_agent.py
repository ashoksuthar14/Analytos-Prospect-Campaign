"""
ScoringAgent: Ranks leads by weighted scoring criteria.
"""

from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from utils.detailed_logger import DetailedLogger
import time


class ScoringAgent(BaseAgent):
    """
    Agent that scores and ranks leads.
    
    Scoring criteria:
    - fit_score: 0.5 weight (company fit)
    - engagement: 0.3 weight (engagement signals)
    - intent: 0.2 weight (buying intent signals)
    
    Normalizes to 0-100 scale.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider=None, logger=None):
        """Initialize ScoringAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize detailed logger for continuous monitoring
        self.detailed_logger = DetailedLogger()
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process lead scoring.
        
        Args:
            input_data: Input data with leads array
            state: Current workflow state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with 'ranked_leads' array (sorted by score)
        """
        start_time = time.time()
        
        # Log agent start
        self.detailed_logger.log_agent_start(run_id or "no_run_id", self.name, input_data)
        
        leads = input_data.get("leads")
        
        # Get ICP criteria from state (passed from prospect_search agent)
        icp_industry = None
        if state and isinstance(state, dict):
            # Try to get ICP from state
            icp = state.get("icp") or state.get("prospect_search", {}).get("icp")
            if icp and isinstance(icp, dict):
                icp_industry = icp.get("industry")

        # Unwrap common containers
        if isinstance(leads, dict):
            for candidate_key in ("leads", "ranked_leads", "results", "data"):
                candidate = leads.get(candidate_key)
                if isinstance(candidate, list):
                    leads = candidate
                    break
            else:
                leads = []

        # Handle None or empty leads gracefully
        if leads is None:
            return {
                "ranked_leads": [],
                "total_scored": 0,
                "top_score": 0,
                "average_score": 0,
                "status": "skipped",
                "message": "No leads to score from previous agent"
            }

        # Ensure leads is a list
        if not isinstance(leads, list):
            leads = list(leads) if leads else []
        
        tool_config = self.config.get("tool_config", {})
        weights = tool_config.get("weights", {
            "fit_score": 0.5,
            "engagement": 0.3,
            "intent": 0.2
        })
        normalize_to = tool_config.get("normalize_to", 100)
        
        ranked_leads = []
        
        # Handle empty leads list
        if not leads:
            return {
                "ranked_leads": [],
                "total_scored": 0,
                "top_score": 0,
                "average_score": 0,
                "status": "no_leads",
                "message": "No leads to score"
            }
        
        for lead in leads:
            # Skip None or invalid leads
            if not lead or not isinstance(lead, dict):
                continue
            
            # Check industry match FIRST - if no match, score = 0
            if icp_industry:
                lead_industry = lead.get("industry")
                industry_matches = self._check_industry_match(icp_industry, lead_industry)
                
                if not industry_matches:
                    # Industry mismatch - set score to 0
                    scored_lead = lead.copy()
                    scored_lead["fit_score"] = 0.0
                    scored_lead["score"] = 0.0
                    scored_lead["fit_score_breakdown"] = 0.0
                    scored_lead["engagement_score"] = 0.0
                    scored_lead["intent_score"] = 0.0
                    scored_lead["industry_mismatch"] = True
                    scored_lead["rejection_reason"] = f"Industry mismatch: wanted '{icp_industry}', got '{lead_industry}'"
                    
                    self.detailed_logger.log_decision(
                        run_id or "no_run_id",
                        self.name,
                        f"❌ Score = 0 for {lead.get('company_name')}",
                        f"Industry mismatch: wanted '{icp_industry}', got '{lead_industry}'"
                    )
                    
                    ranked_leads.append(scored_lead)
                    continue
                
            # Calculate individual scores
            fit_score = self._calculate_fit_score(lead, icp_industry)
            engagement_score = self._calculate_engagement_score(lead)
            intent_score = self._calculate_intent_score(lead)
            
            # Calculate weighted average
            weighted_score = (
                fit_score * weights.get("fit_score", 0.5) +
                engagement_score * weights.get("engagement", 0.3) +
                intent_score * weights.get("intent", 0.2)
            )
            
            # Normalize to target scale
            normalized_score = (weighted_score / 1.0) * normalize_to
            
            # Add scores directly to the lead (not nested)
            scored_lead = lead.copy()
            scored_lead["fit_score"] = round(normalized_score, 2)  # Main score (for database)
            scored_lead["score"] = round(normalized_score, 2)      # Alias for consistency
            scored_lead["fit_score_breakdown"] = round(fit_score, 2)
            scored_lead["engagement_score"] = round(engagement_score, 2)
            scored_lead["intent_score"] = round(intent_score, 2)
            
            ranked_leads.append(scored_lead)
        
        # Sort by score descending
        ranked_leads.sort(key=lambda x: x["score"], reverse=True)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log completion
        result = {
            "leads": ranked_leads,  # Changed from "ranked_leads" to "leads" for downstream compatibility
            "ranked_leads": ranked_leads,  # Keep for backward compatibility
            "total_scored": len(ranked_leads),
            "top_score": ranked_leads[0]["score"] if ranked_leads else 0,
            "average_score": sum(l["score"] for l in ranked_leads) / len(ranked_leads) if ranked_leads else 0
        }
        
        self.detailed_logger.log_agent_complete(run_id or "no_run_id", self.name, {
            "total_scored": len(ranked_leads),
            "top_score": result["top_score"],
            "average_score": result["average_score"]
        }, duration_ms)
        
        return result
    
    def _check_industry_match(self, target_industry: str, lead_industry: str) -> bool:
        """
        Check if lead industry matches target industry.
        
        Args:
            target_industry: Target industry from ICP
            lead_industry: Lead's industry
            
        Returns:
            True if matches, False otherwise
        """
        if not target_industry:
            return True  # No filter, accept all
        
        if not lead_industry:
            return False  # No industry data, reject
        
        # Normalize for comparison
        target_lower = str(target_industry).lower().strip()
        lead_lower = str(lead_industry).lower().strip()
        
        # Define industry keyword mappings
        industry_keywords = {
            "manufacturing": ["manufacturing", "industrial", "factory", "production"],
            "technology": ["technology", "software", "tech", "it services"],
            "healthcare": ["healthcare", "health care", "medical", "hospital", "pharma"],
            "financial services": ["financial", "finance", "banking", "insurance", "fintech"],
            "retail": ["retail", "e-commerce", "ecommerce", "consumer goods"],
            "professional services": ["professional services", "consulting", "legal", "accounting"],
            "real estate": ["real estate", "property", "real-estate"],
            "education": ["education", "educational", "e-learning", "elearning", "training", "learning"],
            "transportation & logistics": ["transportation", "logistics", "shipping", "freight"],
            "energy & utilities": ["energy", "utilities", "power", "oil", "gas"]
        }
        
        # Get keywords for target industry
        keywords = industry_keywords.get(target_lower, [target_lower])
        
        # Check if ANY keyword matches
        for keyword in keywords:
            if keyword in lead_lower:
                return True
        
        return False
    
    def _calculate_fit_score(self, lead: Dict[str, Any], icp_industry: str = None) -> float:
        """
        Calculate fit score (0-1) based on company fit.
        
        Args:
            lead: Lead dictionary
            icp_industry: Target industry from ICP (optional)
            
        Returns:
            Fit score between 0 and 1
        """
        if not lead or not isinstance(lead, dict):
            return 0.5  # Default score for invalid leads
            
        score = 0.5  # Base score
        
        # Revenue range fit (if in target range, boost score)
        revenue = lead.get("revenue")
        if revenue and isinstance(revenue, (int, float)):
            if 20000000 <= revenue <= 200000000:
                score += 0.2
            elif 10000000 <= revenue <= 500000000:
                score += 0.1
        
        # Employee count fit
        employee_count = lead.get("employee_count")
        if employee_count and isinstance(employee_count, (int, float)):
            if 100 <= employee_count <= 1000:
                score += 0.2
            elif 50 <= employee_count <= 2000:
                score += 0.1
        
        # Industry match - bonus if matches ICP
        if icp_industry:
            lead_industry = lead.get("industry")
            if self._check_industry_match(icp_industry, lead_industry):
                score += 0.2  # Bonus for matching target industry
        
        return min(score, 1.0)
    
    def _calculate_engagement_score(self, lead: Dict[str, Any]) -> float:
        """
        Calculate engagement score (0-1) based on engagement signals.
        
        Args:
            lead: Lead dictionary
            
        Returns:
            Engagement score between 0 and 1
        """
        score = 0.3  # Base score
        
        # Check for enrichment data (indicates active company)
        enrichment = lead.get("enrichment", {})
        if enrichment:
            score += 0.2
        
        # LinkedIn presence
        if enrichment.get("linkedin_url"):
            score += 0.2
        
        # Tech stack data
        tech_stack = enrichment.get("tech_stack", [])
        if tech_stack:
            score += 0.2
        
        # Firmographics completeness
        firmographics = enrichment.get("firmographics", {})
        if firmographics.get("founded_year"):
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_intent_score(self, lead: Dict[str, Any]) -> float:
        """
        Calculate intent score (0-1) based on buying intent signals.
        
        Args:
            lead: Lead dictionary
            
        Returns:
            Intent score between 0 and 1
        """
        score = 0.2  # Base score
        
        # Check for signals in workflow state or lead data
        # This would typically come from external signals (funding, hiring, etc.)
        # For now, we'll use heuristics
        
        # Recent activity signals
        enrichment = lead.get("enrichment", {})
        firmographics = enrichment.get("firmographics", {})
        
        # Company age (newer companies more likely to buy)
        founded_year = firmographics.get("founded_year")
        if founded_year:
            import datetime
            current_year = datetime.datetime.now().year
            age = current_year - founded_year
            if age <= 5:
                score += 0.3
            elif age <= 10:
                score += 0.2
        
        # Tech stack indicates growth
        tech_stack = enrichment.get("tech_stack", [])
        if len(tech_stack) >= 3:
            score += 0.2
        
        # Role details indicate decision maker
        role_details = enrichment.get("role_details", {})
        if role_details.get("seniority") in ["executive", "c-suite", "director"]:
            score += 0.3
        
        return min(score, 1.0)

