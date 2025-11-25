"""
Test script to compare Groq vs OpenAI for personalized outreach message generation.
Tests both APIs with the same enriched lead data to see which produces better results.
"""

import os
import sys
from groq import Groq
from openai import OpenAI
from configs.api_keys import GROQ_API_KEY, OPENAI_API_KEY

# Sample enriched lead data (based on real enrichment structure)
SAMPLE_LEAD = {
    "company_name": "Innovo Manufacturing",
    "contact_name": "James Cantrell",
    "contact_title": "CEO, Chief Technology Officer",
    "contact_email": "james@innovomfg.com",
    "industry": "electrical/electronic manufacturing",
    "employee_count": 150,
    "revenue": "$20M",
    "domain": "innovomfg.com",
    "enrichment": {
        "tech_stack": ["SAP", "Oracle", "Salesforce", "Tableau"],
        "firmographics": {
            "description": "Innovo Manufacturing specializes in precision electronic components and manufacturing solutions for the automotive and aerospace industries. They focus on quality control and operational efficiency.",
            "founded_year": 2010,
            "headquarters": "San Francisco, CA",
            "tags": ["precision manufacturing", "quality control", "automotive"]
        },
        "role_details": {
            "role": "CEO, Chief Technology Officer",
            "seniority": "C-Level"
        },
        "seniority": "C-Level",
        "linkedin_url": "http://www.linkedin.com/in/james-cantrell-022416151"
    }
}

def build_context(lead):
    """Build comprehensive context from enriched lead data."""
    context = {}
    enrichment = lead.get("enrichment", {})
    
    context["company_name"] = lead.get("company_name", "")
    context["contact_name"] = lead.get("contact_name", "")
    context["contact_title"] = lead.get("contact_title", "")
    context["industry"] = lead.get("industry", "")
    context["employee_count"] = lead.get("employee_count", "")
    context["revenue"] = lead.get("revenue", "")
    
    tech_stack = enrichment.get("tech_stack", [])
    context["tech_stack"] = tech_stack if isinstance(tech_stack, list) else []
    
    firmographics = enrichment.get("firmographics", {})
    context["company_description"] = firmographics.get("description", "")
    context["founded_year"] = firmographics.get("founded_year")
    context["headquarters"] = firmographics.get("headquarters", "")
    context["company_tags"] = firmographics.get("tags", [])
    
    role_details = enrichment.get("role_details", {})
    context["role"] = lead.get("contact_title") or role_details.get("role", "")
    context["seniority"] = enrichment.get("seniority", "")
    
    return context

def generate_with_groq(context):
    """Generate outreach message using Groq API."""
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        
        contact_name = context.get("contact_name", "there")
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
        
        # Build comprehensive context
        specific_insights = []
        if company_description:
            desc_snippet = company_description[:300] if len(company_description) > 300 else company_description
            specific_insights.append(f"What {company_name} does: {desc_snippet}")
        if tech_stack and len(tech_stack) > 0:
            tech_insight = f"{company_name} uses {', '.join(tech_stack[:3])}"
            if len(tech_stack) > 3:
                tech_insight += f" and {len(tech_stack) - 3} other technologies"
            specific_insights.append(tech_insight)
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
        
        role_insight = ""
        if role:
            role_insight = f"{first_name} is the {role}"
            if seniority:
                role_insight += f" ({seniority} level)"
            role_insight += " - they make decisions about operational efficiency and technology."
        
        industry_challenges = {
            'semiconductors': 'supply chain optimization, yield improvement, and manufacturing efficiency',
            'manufacturing': 'production line optimization, quality control, and reducing operational costs',
            'electrical/electronic manufacturing': 'precision manufacturing, quality control, supply chain efficiency, and reducing production costs',
            'information technology': 'scaling operations, automating repetitive tasks, and improving system efficiency',
            'medical devices': 'regulatory compliance, quality assurance, and production efficiency',
            'environmental services': 'operational efficiency, resource optimization, and process automation'
        }
        
        industry_challenge = industry_challenges.get(industry.lower(), 'operational efficiency and process optimization')
        
        insights_text = "\n".join([f"- {insight}" for insight in specific_insights]) if specific_insights else "Limited company information available."
        
        prompt = f"""You are a senior sales executive who has researched {company_name} and is writing a personalized email to {first_name}. This is NOT a template - write it like a human who genuinely understands their business.

COMPANY RESEARCH:
{insights_text}
{role_insight}

INDUSTRY CONTEXT:
{company_name} operates in {industry}. Companies in this space typically face challenges with {industry_challenge}.

YOUR GOAL:
Write a short, human-sounding email (2-3 paragraphs, ~100 words) that:
1. Opens naturally - reference something specific about {company_name} or {first_name}'s role (NOT "I noticed your company")
2. Shows you understand their business - mention a specific challenge or opportunity relevant to {company_name}'s situation
3. Connects to value - briefly explain how operational efficiency/automation helps companies like {company_name} in {industry}
4. Ends with a low-pressure ask - suggest a brief conversation, not a hard sell
5. Sounds like a real person wrote it - use natural language, vary sentence structure, avoid corporate jargon

CRITICAL RULES:
- DO NOT start with "I noticed" or "I saw" - be more natural
- DO NOT use phrases like "companies like yours" - be specific to {company_name}
- DO NOT use templates - every sentence should feel custom-written
- DO reference specific details from the research above
- DO write conversationally, like you're emailing a colleague
- DO make it feel like you actually researched {company_name} before writing

Write the email now. Make it sound human, not AI-generated:"""
        
        # Try different Groq models (llama-3.1-70b-versatile is deprecated)
        models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        response = None
        last_error = None
        
        for model in models_to_try:
            try:
                response = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert B2B sales email writer who creates highly personalized, human-sounding outreach messages."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=500
                )
                groq_model_used = model
                break
            except Exception as e:
                last_error = str(e)
                continue
        
        if not response:
            raise Exception(f"All Groq models failed. Last error: {last_error}")
        
        body = response.choices[0].message.content.strip()
        
        # Generate subject line
        subject_prompt = f"""Create a compelling, personalized email subject line for {first_name if first_name else 'the contact'} at {company_name}.

COMPANY DETAILS:
- Company: {company_name}
- Industry: {industry}
- Role: {role}
{f'- Tech: {", ".join(tech_stack[:2])}' if tech_stack and len(tech_stack) > 0 else ''}

REQUIREMENTS:
- Maximum 60 characters
- Must be SPECIFIC to {company_name} - not generic
- Reference something unique: their industry, tech stack, role, or company size
- Create curiosity or value - what's in it for them?
- Avoid: "Quick question", "Following up", "I noticed", or other overused phrases
- Sound natural and human, not salesy

Write ONLY the subject line (no quotes, no "Subject:" prefix):"""
        
        # Use the same model that worked for body
        subject_response = groq_client.chat.completions.create(
            model=groq_model_used,
            messages=[
                {"role": "system", "content": "You are an expert at creating compelling, personalized email subject lines."},
                {"role": "user", "content": subject_prompt}
            ],
            temperature=0.8,
            max_tokens=100
        )
        
        subject = subject_response.choices[0].message.content.strip()
        subject = subject.strip('"').strip("'").strip('`')
        subject = subject.replace("Subject:", "").replace("Subject Line:", "").strip()
        
        return {
            "provider": f"Groq ({groq_model_used})",
            "subject": subject[:60],
            "body": body
        }
    except Exception as e:
        return {
            "provider": "Groq",
            "error": str(e),
            "subject": None,
            "body": None
        }

def generate_with_openai(context):
    """Generate outreach message using OpenAI API."""
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        contact_name = context.get("contact_name", "there")
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
        
        # Build comprehensive context (same as Groq)
        specific_insights = []
        if company_description:
            desc_snippet = company_description[:300] if len(company_description) > 300 else company_description
            specific_insights.append(f"What {company_name} does: {desc_snippet}")
        if tech_stack and len(tech_stack) > 0:
            tech_insight = f"{company_name} uses {', '.join(tech_stack[:3])}"
            if len(tech_stack) > 3:
                tech_insight += f" and {len(tech_stack) - 3} other technologies"
            specific_insights.append(tech_insight)
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
        
        role_insight = ""
        if role:
            role_insight = f"{first_name} is the {role}"
            if seniority:
                role_insight += f" ({seniority} level)"
            role_insight += " - they make decisions about operational efficiency and technology."
        
        industry_challenges = {
            'semiconductors': 'supply chain optimization, yield improvement, and manufacturing efficiency',
            'manufacturing': 'production line optimization, quality control, and reducing operational costs',
            'electrical/electronic manufacturing': 'precision manufacturing, quality control, supply chain efficiency, and reducing production costs',
            'information technology': 'scaling operations, automating repetitive tasks, and improving system efficiency',
            'medical devices': 'regulatory compliance, quality assurance, and production efficiency',
            'environmental services': 'operational efficiency, resource optimization, and process automation'
        }
        
        industry_challenge = industry_challenges.get(industry.lower(), 'operational efficiency and process optimization')
        
        insights_text = "\n".join([f"- {insight}" for insight in specific_insights]) if specific_insights else "Limited company information available."
        
        prompt = f"""You are a senior sales executive who has researched {company_name} and is writing a personalized email to {first_name}. This is NOT a template - write it like a human who genuinely understands their business.

COMPANY RESEARCH:
{insights_text}
{role_insight}

INDUSTRY CONTEXT:
{company_name} operates in {industry}. Companies in this space typically face challenges with {industry_challenge}.

YOUR GOAL:
Write a short, human-sounding email (2-3 paragraphs, ~100 words) that:
1. Opens naturally - reference something specific about {company_name} or {first_name}'s role (NOT "I noticed your company")
2. Shows you understand their business - mention a specific challenge or opportunity relevant to {company_name}'s situation
3. Connects to value - briefly explain how operational efficiency/automation helps companies like {company_name} in {industry}
4. Ends with a low-pressure ask - suggest a brief conversation, not a hard sell
5. Sounds like a real person wrote it - use natural language, vary sentence structure, avoid corporate jargon

CRITICAL RULES:
- DO NOT start with "I noticed" or "I saw" - be more natural
- DO NOT use phrases like "companies like yours" - be specific to {company_name}
- DO NOT use templates - every sentence should feel custom-written
- DO reference specific details from the research above
- DO write conversationally, like you're emailing a colleague
- DO make it feel like you actually researched {company_name} before writing

Write the email now. Make it sound human, not AI-generated:"""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert B2B sales email writer who creates highly personalized, human-sounding outreach messages."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        body = response.choices[0].message.content.strip()
        
        # Generate subject line
        subject_prompt = f"""Create a compelling, personalized email subject line for {first_name if first_name else 'the contact'} at {company_name}.

COMPANY DETAILS:
- Company: {company_name}
- Industry: {industry}
- Role: {role}
{f'- Tech: {", ".join(tech_stack[:2])}' if tech_stack and len(tech_stack) > 0 else ''}

REQUIREMENTS:
- Maximum 60 characters
- Must be SPECIFIC to {company_name} - not generic
- Reference something unique: their industry, tech stack, role, or company size
- Create curiosity or value - what's in it for them?
- Avoid: "Quick question", "Following up", "I noticed", or other overused phrases
- Sound natural and human, not salesy

Write ONLY the subject line (no quotes, no "Subject:" prefix):"""
        
        subject_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at creating compelling, personalized email subject lines."},
                {"role": "user", "content": subject_prompt}
            ],
            temperature=0.8,
            max_tokens=100
        )
        
        subject = subject_response.choices[0].message.content.strip()
        subject = subject.strip('"').strip("'").strip('`')
        subject = subject.replace("Subject:", "").replace("Subject Line:", "").strip()
        
        return {
            "provider": "OpenAI (gpt-4o-mini)",
            "subject": subject[:60],
            "body": body
        }
    except Exception as e:
        return {
            "provider": "OpenAI",
            "error": str(e),
            "subject": None,
            "body": None
        }

def main():
    """Main test function."""
    print("=" * 80)
    print("LLM COMPARISON TEST: Groq vs OpenAI for Outreach Message Generation")
    print("=" * 80)
    print()
    
    # Build context from sample lead
    context = build_context(SAMPLE_LEAD)
    
    print("TEST LEAD DATA:")
    print(f"  Company: {context['company_name']}")
    print(f"  Contact: {context['contact_name']} ({context['role']})")
    print(f"  Industry: {context['industry']}")
    print(f"  Tech Stack: {', '.join(context['tech_stack'][:4])}")
    print(f"  Company Description: {context['company_description'][:100]}...")
    print(f"  Employees: {context['employee_count']}")
    print()
    print("=" * 80)
    print()
    
    # Test Groq
    print("🔄 Testing GROQ API...")
    print("-" * 80)
    groq_result = generate_with_groq(context)
    
    if groq_result.get("error"):
        print(f"❌ Groq Error: {groq_result['error']}")
    else:
        print(f"✅ {groq_result['provider']}")
        print()
        print("SUBJECT:")
        print(f"  {groq_result['subject']}")
        print()
        print("BODY:")
        print(f"  {groq_result['body']}")
        print()
    
    print("=" * 80)
    print()
    
    # Test OpenAI
    print("🔄 Testing OPENAI API...")
    print("-" * 80)
    openai_result = generate_with_openai(context)
    
    if openai_result.get("error"):
        print(f"❌ OpenAI Error: {openai_result['error']}")
    else:
        print(f"✅ {openai_result['provider']}")
        print()
        print("SUBJECT:")
        print(f"  {openai_result['subject']}")
        print()
        print("BODY:")
        print(f"  {openai_result['body']}")
        print()
    
    print("=" * 80)
    print()
    print("COMPARISON SUMMARY:")
    print("-" * 80)
    
    if groq_result.get("error") and openai_result.get("error"):
        print("❌ Both APIs failed")
    elif groq_result.get("error"):
        print("✅ OpenAI succeeded, Groq failed")
        print("   Recommendation: Use OpenAI")
    elif openai_result.get("error"):
        print("✅ Groq succeeded, OpenAI failed")
        print("   Recommendation: Use Groq")
    else:
        print("✅ Both APIs succeeded")
        print()
        print("ANALYSIS:")
        print("  Compare the messages above to see which:")
        print("  1. References more specific company details")
        print("  2. Sounds more human and less templated")
        print("  3. Shows better understanding of the business")
        print("  4. Creates more personalized, unique content")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()

