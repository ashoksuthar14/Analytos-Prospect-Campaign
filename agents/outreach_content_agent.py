"""
OutreachContentAgent: Generates personalized outreach messages using Groq.
"""

from typing import Dict, Any, List, Optional
from uuid import uuid4
from agents.base_agent import BaseAgent


class OutreachContentAgent(BaseAgent):
    """
    Agent that generates personalized outreach messages.
    
    Uses Groq to generate:
    - Personalized subject lines
    - Personalized email bodies
    - Uses company context, role, signals, tech stack
    """
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process outreach content generation.
        
        Args:
            input_data: Input data with ranked_leads
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with 'messages' array
        """
        # Try to get ranked_leads from input_data
        ranked_leads = input_data.get("ranked_leads")
        
        # If not found, try to get leads from apollo_contact_sync output
        if not ranked_leads:
            ranked_leads = input_data.get("leads")
        
        # If input_data is a dict with nested structure, extract leads
        if isinstance(input_data, dict) and not ranked_leads:
            # Try common output structures
            ranked_leads = input_data.get("ranked_leads") or input_data.get("leads")
            # If it's nested in an output structure
            if isinstance(ranked_leads, dict):
                ranked_leads = ranked_leads.get("ranked_leads") or ranked_leads.get("leads", [])
        
        tool_config = self.config.get("tool_config", {})
        
        # Handle None or empty ranked_leads gracefully
        if ranked_leads is None:
            return {
                "messages": [],
                "total_generated": 0,
                "tone": tool_config.get("tone", "friendly, concise, value-driven"),
                "ab_testing_enabled": False,
                "status": "skipped",
                "message": "No ranked leads to generate content for"
            }
        
        # If ranked_leads is a dict (from scoring.output), extract the ranked_leads array
        if isinstance(ranked_leads, dict):
            ranked_leads = ranked_leads.get("ranked_leads") or ranked_leads.get("leads", [])
        
        # Ensure it's a list
        if not isinstance(ranked_leads, list):
            ranked_leads = []
        
        top_n = input_data.get("top_n", 20)
        tool_config = self.config.get("tool_config", {})
        tone = tool_config.get("tone", "friendly, concise, value-driven")
        personalization_fields = tool_config.get("personalization_fields", [])
        ab_testing = tool_config.get("ab_testing", {})
        
        # Get source company information (from config overrides or defaults)
        source_company = input_data.get("source_company", {})
        if not source_company:
            # Try to get from config
            source_company = self.config.get("inputs", {}).get("source_company", {})
        
        # Set defaults if not provided
        if not source_company or not source_company.get("name"):
            source_company = {
                "name": "Analytos",
                "description": "We specialize in automation and AI agent building",
                "value_proposition": "We help companies automate repetitive tasks, build intelligent agents, and scale operations efficiently through custom AI solutions"
            }
        
        # Handle empty ranked_leads list
        if not ranked_leads:
            return {
                "messages": [],
                "total_generated": 0,
                "tone": tone,
                "ab_testing_enabled": bool(ab_testing.get("enabled", False)),
                "status": "no_leads",
                "message": "No ranked leads to generate content for"
            }
        
        # Get top N leads (limit to available leads)
        top_leads = ranked_leads[:min(top_n, len(ranked_leads))]
        
        messages = []
        failed_leads = []
        
        for ranked_lead in top_leads:
            # Handle both flat and nested lead structures
            if "lead" in ranked_lead and isinstance(ranked_lead["lead"], dict):
                lead = ranked_lead["lead"]
            else:
                lead = ranked_lead
            
            # Require persisted lead_id
            lead_id = lead.get("lead_id")
            if not lead_id:
                print(f"[{self.name}] ⚠️  Skipping lead without lead_id: {lead.get('company_name')}")
                failed_leads.append({"lead": lead.get("company_name"), "reason": "missing_lead_id"})
                continue
            
            # Build personalization context
            context = self._build_context(lead, personalization_fields)
            
            try:
                # Generate subject and body using LLM
                variant = self._assign_ab_variant(lead_id, ab_testing)
                print(f"[{self.name}] 🚀 Generating content for {lead.get('company_name')} (lead_id: {lead_id})")
                subject = self._generate_subject(lead, context, tone, variant=variant)
                body = self._generate_body(lead, context, tone, source_company)
                print(f"[{self.name}] ✅ Generated content for {lead.get('company_name')}")
            except Exception as e:
                print(f"[{self.name}] ❌ Failed to generate content for {lead.get('company_name')}: {e}")
                import traceback
                traceback.print_exc()
                
                if run_id and self.logger:
                    self.logger.log_agent_error(
                        run_id=run_id,
                        agent_name=self.name,
                        error_data={"type": type(e).__name__, "message": str(e), "lead": lead.get("company_name")}
                    )
                
                # Don't fail completely - skip this lead and continue
                failed_leads.append({"lead": lead.get("company_name"), "reason": str(e)})
                continue
            
            msg_id = str(uuid4())
            message_entry = {
                "message_id": msg_id,
                "lead_id": lead_id,
                "subject": subject,
                "body": body,
                "personalization_used": personalization_fields,
                "ab_variant": variant  # Track variant for analysis
            }
            messages.append(message_entry)
            
            if run_id and self.logger:
                self.logger.log_tool_call(
                    run_id=run_id,
                    agent_name=self.name,
                    tool_name="llm_api",
                    tool_input={"lead": lead.get("company_name"), "context": context},
                    tool_output={"subject": subject[:50] + "..."}
                )
        
        result = {
            "messages": messages,
            "total_generated": len(messages),
            "tone": tone,
            "ab_testing_enabled": bool(ab_testing.get("enabled", False))
        }
        
        if failed_leads:
            result["failed_leads"] = failed_leads
            result["failed_count"] = len(failed_leads)
            print(f"[{self.name}] ⚠️  {len(failed_leads)} leads failed content generation")
        
        if not messages and failed_leads:
            # If all leads failed, raise an error
            raise RuntimeError(f"Failed to generate outreach content for all leads. Errors: {failed_leads}")
        
        return result
    
    def _assign_ab_variant(
        self,
        lead_id: str,
        ab_testing: Dict[str, Any]
    ) -> Optional[str]:
        """
        Assign A/B test variant to a lead.
        
        Uses consistent hashing to ensure same lead always gets same variant.
        
        Args:
            lead_id: Lead identifier
            ab_testing: A/B testing configuration
            
        Returns:
            Variant name or None
        """
        if not ab_testing.get("enabled", False):
            return None
        
        variants = ab_testing.get("variants", {})
        if not variants:
            return None
        
        # Simple hash-based assignment for consistency
        import hashlib
        hash_value = int(hashlib.md5(lead_id.encode()).hexdigest(), 16)
        variant_names = list(variants.keys())
        variant_index = hash_value % len(variant_names)
        
        return variant_names[variant_index]
    
    def _build_context(self, lead: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """
        Build comprehensive personalization context from enriched lead data.
        
        Args:
            lead: Lead dictionary with all enriched data
            fields: Fields to use for personalization
            
        Returns:
            Context dictionary with all available lead insights
        """
        context = {}
        enrichment = lead.get("enrichment", {})
        
        # Basic company info
        context["company_name"] = lead.get("company_name", "")
        context["contact_name"] = lead.get("contact_name", "")
        context["contact_title"] = lead.get("contact_title", "")
        context["contact_email"] = lead.get("contact_email", "")
        
        # Industry and location
        context["industry"] = lead.get("industry") or enrichment.get("industry", "")
        context["location"] = lead.get("location", "")
        
        # Company size
        context["employee_count"] = lead.get("employee_count") or enrichment.get("employee_count", "")
        context["revenue"] = lead.get("revenue") or enrichment.get("revenue", "")
        
        # Tech stack (from enrichment)
        tech_stack = enrichment.get("tech_stack", [])
        if isinstance(tech_stack, list):
            context["tech_stack"] = tech_stack
        else:
            context["tech_stack"] = []
        
        # Role details
        role_details = enrichment.get("role_details", {})
        context["role"] = lead.get("contact_title") or role_details.get("role", "")
        context["seniority"] = enrichment.get("seniority") or role_details.get("seniority", "")
        
        # Firmographics
        firmographics = enrichment.get("firmographics", {})
        context["founded_year"] = firmographics.get("founded_year")
        context["headquarters"] = firmographics.get("headquarters", "")
        context["company_description"] = firmographics.get("description", "")
        context["company_tags"] = firmographics.get("tags", [])
        
        # LinkedIn
        context["linkedin_url"] = enrichment.get("linkedin_url", "")
        
        # Domain
        context["domain"] = lead.get("domain", "")
        
        # Score (if available)
        context["score"] = lead.get("score", lead.get("fit_score", ""))
        
        return context
    
    def _get_personalization_angle(self, lead_id: str, context: Dict[str, Any]) -> str:
        """
        Get a unique personalization angle for this lead to ensure variety.
        Uses lead_id hash to consistently assign different angles.
        
        Args:
            lead_id: Lead identifier
            context: Lead context
            
        Returns:
            Angle description (tech-focused, growth-focused, efficiency-focused, etc.)
        """
        import hashlib
        hash_value = int(hashlib.md5(str(lead_id).encode()).hexdigest(), 16)
        
        # Available angles based on enriched data
        angles = []
        
        tech_stack = context.get("tech_stack", [])
        if tech_stack and len(tech_stack) > 0:
            angles.append("tech-focused")  # Focus on their tech stack
        
        employee_count = context.get("employee_count", "")
        if employee_count:
            if isinstance(employee_count, (int, float)) and employee_count < 200:
                angles.append("growth-focused")  # Focus on scaling
            elif isinstance(employee_count, (int, float)) and employee_count >= 1000:
                angles.append("efficiency-focused")  # Focus on optimization
        
        company_description = context.get("company_description", "")
        if company_description and any(word in company_description.lower() for word in ["quality", "precision", "control"]):
            angles.append("quality-focused")  # Focus on quality/process improvement
        
        founded_year = context.get("founded_year")
        if founded_year:
            years_old = 2025 - int(founded_year) if isinstance(founded_year, (int, str)) and str(founded_year).isdigit() else None
            if years_old and years_old > 10:
                angles.append("innovation-focused")  # Focus on modernizing established company
        
        industry = context.get("industry", "").lower()
        if "manufacturing" in industry:
            angles.append("production-focused")  # Focus on production efficiency
        elif "technology" in industry or "software" in industry:
            angles.append("automation-focused")  # Focus on automation
        
        # Default angles if none match
        if not angles:
            angles = ["value-focused", "efficiency-focused", "growth-focused"]
        
        # Select angle based on hash for consistency
        selected_angle = angles[hash_value % len(angles)]
        return selected_angle
    
    def _generate_subject(
        self,
        lead: Dict[str, Any],
        context: Dict[str, Any],
        tone: str,
        variant: Optional[str] = None
    ) -> str:
        """
        Generate email subject using Groq.
        
        Args:
            lead: Lead dictionary
            context: Personalization context
            tone: Tone description
            variant: A/B test variant (optional)
            
        Returns:
            Generated subject line
        """
        # Check for A/B test variants
        tool_config = self.config.get("tool_config", {})
        ab_testing = tool_config.get("ab_testing", {})
        
        if variant and variant in ab_testing.get("variants", {}):
            # Use variant-specific prompt
            variant_config = ab_testing["variants"][variant]
            prompt_template = variant_config.get("prompt_template", "")
        else:
            # Expert-level personalized subject line generation
            company_name = context.get('company_name', 'Unknown')
            industry = context.get('industry', 'Manufacturing')
            role = context.get('role', 'Decision Maker')
            tech_stack = context.get('tech_stack', [])
            employee_count = context.get('employee_count', '')
            contact_name = context.get('contact_name', '')
            first_name = contact_name.split()[0] if contact_name else ''
            
            # Build subject line context with specific details
            subject_context_parts = []
            if tech_stack and len(tech_stack) > 0:
                subject_context_parts.append(f"uses {tech_stack[0]}")
            if employee_count and isinstance(employee_count, (int, float)):
                if employee_count < 200:
                    subject_context_parts.append("mid-sized")
                elif employee_count < 1000:
                    subject_context_parts.append("growing")
                else:
                    subject_context_parts.append("enterprise")
            
            subject_context = ", ".join(subject_context_parts) if subject_context_parts else ""
            
            # Get unique personalization angle for this lead
            lead_id = lead.get("lead_id", str(hash(company_name)))
            angle = self._get_personalization_angle(lead_id, context)
            
            tech_example = tech_stack[0] if tech_stack and len(tech_stack) > 0 else 'your tech stack'
            
            # Build angle-specific context
            angle_context = ""
            if angle == "tech-focused" and tech_stack:
                angle_context = f"Focus on their tech stack ({', '.join(tech_stack[:2])}) and how automation integrates"
            elif angle == "growth-focused":
                angle_context = f"Focus on scaling and growth opportunities for a {subject_context if subject_context else 'mid-sized'} company"
            elif angle == "efficiency-focused":
                angle_context = f"Focus on operational efficiency and cost reduction for enterprise operations"
            elif angle == "quality-focused":
                angle_context = "Focus on quality control and process improvement"
            elif angle == "innovation-focused":
                angle_context = "Focus on modernizing and innovating established processes"
            elif angle == "production-focused":
                angle_context = "Focus on production line optimization and manufacturing efficiency"
            elif angle == "automation-focused":
                angle_context = "Focus on automation opportunities and campaign optimization"
            else:
                angle_context = f"Focus on unique value proposition for {company_name}"
            
            prompt_template = f"""Create a UNIQUE, compelling email subject line for {first_name if first_name else 'the contact'} at {company_name}. This must be DIFFERENT from any other subject line.

COMPANY DETAILS:
- Company: {company_name}
- Industry: {industry}
- Role: {role}
{f'- Context: {subject_context}' if subject_context else ''}
{f'- Tech Stack: {", ".join(tech_stack[:3])}' if tech_stack and len(tech_stack) > 0 else ''}

PERSONALIZATION ANGLE: {angle}
{angle_context}

REQUIREMENTS:
- Maximum 60 characters
- Must be SPECIFIC to {company_name} - reference their unique situation
- Use the {angle} angle to create a unique perspective
- Create curiosity or value - what's in it for them?
- Avoid: "Quick question", "Following up", "I noticed", or other overused phrases
- Sound natural and human, not salesy
- MUST be different from generic templates

Write ONLY the subject line (no quotes, no "Subject:" prefix):"""
        
        prompt = prompt_template.format(**context) if "{company_name" in prompt_template else prompt_template
        
        # Use LLM to generate subject (prioritizes Groq)
        try:
            response = self._reason_with_gemini(prompt, None)  # Don't pass context to avoid safety issues
        except Exception as e:
            # If LLM call fails, use a fallback subject
            print(f"[{self.name}] ⚠️  LLM call failed for subject generation: {e}")
            print(f"[{self.name}] Using fallback subject")
            return f"Quick question about {context.get('company_name', 'your company')}"
        
        # Clean up response (remove quotes, extra text)
        subject = response.strip().strip('"').strip("'").strip('`')
        
        # Remove common prefixes that LLM might add
        subject = subject.replace("Subject:", "").replace("Subject Line:", "").strip()
        
        if len(subject) > 60:
            subject = subject[:57] + "..."
        
        return subject or f"Quick question about {context.get('company_name', 'your company')}"
    
    def _generate_body(
        self,
        lead: Dict[str, Any],
        context: Dict[str, Any],
        tone: str,
        source_company: Dict[str, Any] = None
    ) -> str:
        """
        Generate email body using Groq.
        
        Args:
            lead: Lead dictionary
            context: Personalization context
            tone: Tone description
            source_company: Source company information (name, description, value_proposition)
            
        Returns:
            Generated email body
        """
        # Set default source company if not provided
        if not source_company:
            source_company = {
                "name": "Analytos",
                "description": "We specialize in automation and AI agent building",
                "value_proposition": "We help companies automate repetitive tasks, build intelligent agents, and scale operations efficiently through custom AI solutions"
            }
        contact_name = lead.get("contact_name", "there")
        first_name = contact_name.split()[0] if contact_name else "there"
        company_name = context.get("company_name", "your company")
        role = context.get("role", "")
        seniority = context.get("seniority", "")
        industry = context.get('industry', 'Manufacturing')
        tech_stack = context.get("tech_stack", [])
        employee_count = context.get("employee_count", "")
        revenue = context.get("revenue", "")
        company_description = context.get("company_description", "")
        headquarters = context.get("headquarters", "")
        founded_year = context.get("founded_year", "")
        linkedin_url = context.get("linkedin_url", "")
        
        # Build comprehensive context string
        company_insights = []
        if company_description:
            company_insights.append(f"Company Description: {company_description[:200]}")
        if headquarters:
            company_insights.append(f"Headquarters: {headquarters}")
        if founded_year:
            company_insights.append(f"Founded: {founded_year}")
        if employee_count:
            if isinstance(employee_count, (int, float)):
                if employee_count < 200:
                    size_desc = f"mid-sized company with {int(employee_count)} employees"
                elif employee_count < 1000:
                    size_desc = f"growing company with {int(employee_count)} employees"
                else:
                    size_desc = f"enterprise-scale company with {int(employee_count)} employees"
            else:
                size_desc = f"company with {employee_count} employees"
            company_insights.append(f"Company Size: {size_desc}")
        if revenue:
            company_insights.append(f"Revenue: {revenue}")
        
        tech_context = ""
        if tech_stack and len(tech_stack) > 0:
            tech_list = ', '.join(tech_stack[:4])
            tech_context = f"\nTheir Technology Stack: {tech_list}\nThis shows they are investing in technology and may be open to automation solutions."
        
        role_context = ""
        if role:
            role_context = f"\nContact's Role: {role}"
            if seniority:
                role_context += f" ({seniority} level)"
        
        company_context = "\n".join(company_insights) if company_insights else ""
        
        # Build a rich, specific context about the company
        specific_insights = []
        
        # Company description insights
        if company_description:
            # Extract key points from description
            desc_snippet = company_description[:300] if len(company_description) > 300 else company_description
            specific_insights.append(f"What {company_name} does: {desc_snippet}")
        
        # Tech stack insights - make it specific
        if tech_stack and len(tech_stack) > 0:
            tech_insight = f"{company_name} uses {', '.join(tech_stack[:3])}"
            if len(tech_stack) > 3:
                tech_insight += f" and {len(tech_stack) - 3} other technologies"
            specific_insights.append(tech_insight)
        
        # Company maturity/size insights
        if founded_year:
            years_old = 2025 - int(founded_year) if isinstance(founded_year, (int, str)) and str(founded_year).isdigit() else None
            if years_old:
                specific_insights.append(f"Founded {founded_year} ({years_old} years in business)")
        
        if employee_count:
            if isinstance(employee_count, (int, float)):
                emp_count = int(employee_count)
                if emp_count < 50:
                    size_insight = f"Small team of {emp_count} employees"
                elif emp_count < 200:
                    size_insight = f"Mid-sized company with {emp_count} employees"
                elif emp_count < 1000:
                    size_insight = f"Growing company with {emp_count} employees"
                else:
                    size_insight = f"Enterprise-scale with {emp_count} employees"
                specific_insights.append(size_insight)
        
        # Role-specific insights
        role_insight = ""
        if role:
            role_insight = f"{first_name} is the {role}"
            if seniority:
                role_insight += f" ({seniority} level)"
            role_insight += " - they make decisions about operational efficiency and technology."
        
        # Industry-specific challenges (based on industry)
        industry_challenges = {
            'semiconductors': 'supply chain optimization, yield improvement, and manufacturing efficiency',
            'manufacturing': 'production line optimization, quality control, and reducing operational costs',
            'information technology': 'scaling operations, automating repetitive tasks, and improving system efficiency',
            'medical devices': 'regulatory compliance, quality assurance, and production efficiency',
            'environmental services': 'operational efficiency, resource optimization, and process automation'
        }
        
        industry_challenge = industry_challenges.get(industry.lower(), 'operational efficiency and process optimization')
        
        insights_text = "\n".join([f"- {insight}" for insight in specific_insights]) if specific_insights else "Limited company information available."
        
        # Get unique personalization angle for this lead
        lead_id = lead.get("lead_id", str(hash(company_name)))
        angle = self._get_personalization_angle(lead_id, context)
        
        # Build angle-specific value proposition
        value_props = {
            "tech-focused": f"how automation can integrate with {company_name}'s existing {tech_stack[0] if tech_stack else 'technology'} stack to enhance their current systems",
            "growth-focused": f"how operational efficiency can help {company_name} scale from {employee_count} employees without proportionally increasing costs",
            "efficiency-focused": f"how {company_name} can optimize their enterprise operations to reduce costs while maintaining quality",
            "quality-focused": f"how process automation can enhance {company_name}'s quality control and precision manufacturing capabilities",
            "innovation-focused": f"how modern automation can help {company_name} modernize their {founded_year if founded_year else 'established'} operations while maintaining their reputation",
            "production-focused": f"how production line optimization can help {company_name} increase throughput while reducing waste in {industry}",
            "automation-focused": f"how campaign automation can help {company_name} eliminate manual processes and focus on strategic initiatives",
            "value-focused": f"how operational efficiency can deliver measurable ROI for {company_name} in {industry}"
        }
        
        value_prop = value_props.get(angle, f"how operational efficiency can help {company_name} achieve their goals in {industry}")
        
        # Select different opening styles based on lead_id hash for variety
        import hashlib
        hash_val = int(hashlib.md5(str(lead_id).encode()).hexdigest(), 16)
        opening_styles = [
            f"Reference {first_name}'s role as {role} and their decision-making authority",
            f"Reference {company_name}'s specific focus (from company description)",
            f"Reference their tech stack ({', '.join(tech_stack[:2]) if tech_stack else 'technology investments'})",
            f"Reference {company_name}'s position in {industry} and industry-specific challenges",
            f"Reference their company size ({employee_count} employees) and growth stage"
        ]
        opening_style = opening_styles[hash_val % len(opening_styles)]
        
        # Add variety to paragraph structure
        paragraph_approaches = [
            "First paragraph: Company-specific insight. Second paragraph: Value proposition. Third paragraph: Soft ask.",
            "First paragraph: Industry challenge. Second paragraph: Company-specific solution. Third paragraph: Call to action.",
            "First paragraph: Role-based opening. Second paragraph: Tech/process opportunity. Third paragraph: Invitation to discuss.",
            "First paragraph: Company achievement/position. Second paragraph: Efficiency opportunity. Third paragraph: Low-pressure ask.",
            "First paragraph: Specific business challenge. Second paragraph: How automation addresses it. Third paragraph: Next steps."
        ]
        paragraph_approach = paragraph_approaches[hash_val % len(paragraph_approaches)]
        
        # Extract source company info
        source_company_name = source_company.get("name", "Analytos")
        source_company_desc = source_company.get("description", "We specialize in automation and AI agent building")
        source_company_value = source_company.get("value_proposition", "We help companies automate repetitive tasks, build intelligent agents, and scale operations efficiently")
        
        prompt = f"""You are a senior sales executive at {source_company_name} who has deeply researched {company_name} and is writing a HIGHLY PERSONALIZED email to {first_name}. This email MUST be completely unique - not a template.

YOUR COMPANY ({source_company_name}):
{source_company_desc}

HOW YOU HELP COMPANIES:
{source_company_value}

PROSPECT COMPANY RESEARCH:
{insights_text}
{role_insight}

INDUSTRY CONTEXT:
{company_name} operates in {industry}. Companies in this space typically face challenges with {industry_challenge}.

PERSONALIZATION ANGLE: {angle}
Focus on: {value_prop}

OPENING STYLE: {opening_style}

PARAGRAPH STRUCTURE: {paragraph_approach}

YOUR GOAL:
Write a short, human-sounding email (2-3 small paragraphs, ~100-120 words) that:
1. Opens with the specified opening style - make it natural and specific to {company_name}
2. Shows deep understanding - reference MULTIPLE specific details from the research (tech stack, company description, size, industry challenges, role)
3. Connects to unique value - explain how {source_company_name} can help them with {value_prop} using the {angle} angle
4. Include a brief, natural mention of what {source_company_name} does and how it's relevant to {company_name}'s situation
5. Ends with a low-pressure, personalized ask
6. Sounds like a real person wrote it - use natural language, vary sentence structure, avoid corporate jargon
7. Follows the paragraph structure: {paragraph_approach}

CRITICAL RULES FOR UNIQUENESS:
- DO NOT start with "I noticed" or "I saw" - be more creative and natural
- DO NOT use phrases like "companies like yours" or "similar companies" - be specific to {company_name}
- DO NOT use templates - every sentence must feel custom-written for THIS company
- DO reference MULTIPLE specific details from the research above (tech stack, description, size, industry, role)
- DO naturally mention how {source_company_name}'s expertise in {source_company_desc} can specifically help {company_name}
- DO use the {angle} angle to create a unique perspective different from other emails
- DO write conversationally, like you're emailing a colleague you've researched
- DO make each paragraph add unique value - no filler
- DO ensure this email is completely different from any other email you've written
- DO use the specified paragraph structure to ensure variety
- DO connect {source_company_name}'s capabilities to {company_name}'s specific situation

Write the email now. Make it sound human, personalized, and completely unique:"""
        
        # Use LLM to generate body (prioritizes Groq)
        try:
            response = self._reason_with_gemini(prompt, None)  # Don't pass context to avoid safety triggers
        except Exception as e:
            # If LLM call fails, use a personalized fallback body
            print(f"[{self.name}] ⚠️  LLM call failed for body generation: {e}")
            print(f"[{self.name}] Using fallback body")
            
            # Build a basic personalized fallback
            tech_mention = ""
            if tech_stack and len(tech_stack) > 0:
                tech_mention = f" I see {company_name} uses {tech_stack[0]}, which suggests you're focused on operational efficiency."
            
            body = f"""Hi {first_name},

{company_name} operates in {industry}, where operational efficiency can significantly impact bottom-line results.{tech_mention}

I'd appreciate 15 minutes to share how we've helped similar {industry} companies streamline their operations.

Would you be open to a brief conversation?

Best regards,
[Your Name]"""
            return body
        
        # Clean up and format
        body = response.strip()
        
        # Remove any markdown formatting
        body = body.replace("```", "").strip()
        
        # Ensure it's a reasonable length
        if not body or len(body) < 50:
            raise ValueError("Generated body too short")
        
        return body
    

