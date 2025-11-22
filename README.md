# Prospect-to-Lead LangGraph Workflow

An end-to-end, config-driven agent system that discovers B2B prospects, enriches & scores them, generates outreach, sends emails, tracks replies, and learns from results — all orchestrated by a single `workflow.json`.

## Features

- **Config-Driven Workflow**: Define your entire prospecting workflow in a single JSON file
- **Multi-Agent System**: 7 specialized agents working in sequence
- **Real-Time Updates**: WebSocket-based progress tracking
- **Rate Limiting**: Built-in protection against API abuse (50 leads/run, 200/day)
- **Error Handling**: Robust error categorization and retry logic
- **Metrics & Observability**: Comprehensive performance tracking
- **Human-in-the-Loop**: Feedback-based optimization via Google Sheets
- **A/B Testing**: Subject line variant testing and tracking
- **Security**: PII redaction, input validation, SQL injection prevention

## Overview

This system automates the complete outbound prospecting loop:
1. **ProspectSearchAgent** - Discovers companies/contacts matching ICP
2. **DataEnrichmentAgent** - Enriches leads with firmographic data
3. **ScoringAgent** - Ranks leads by configurable criteria
4. **OutreachContentAgent** - Generates personalized messages (Gemini-powered)
5. **OutreachExecutorAgent** - Sends emails via SendGrid/Apollo
6. **ResponseTrackerAgent** - Monitors opens/clicks/replies/meetings
7. **FeedbackTrainerAgent** - Analyzes performance and proposes optimizations

## Tech Stack

- **LLM**: Google Gemini 1.5/2.x (via Google AI Studio API)
- **Orchestration**: LangGraph + LangChain Core
- **Backend**: Flask + Flask-SocketIO
- **Frontend**: HTML + CSS + JavaScript (vanilla)
- **Database**: SQLite
- **APIs**: Clay, Apollo (prospecting + enrichment), SendGrid, Google Sheets

## Project Structure

```
.
├── app/                    # Flask application
├── agents/                 # Agent implementations (7 agents)
├── tools/                  # API integration tools
├── configs/                # Configuration files
│   ├── workflow.json       # Main workflow configuration
│   ├── overrides.json      # Feedback-based overrides
│   └── service_account.json # Google Sheets credentials (add your own)
├── database/               # Database schema and migrations
├── frontend/               # HTML/CSS/JS files
├── logs/                   # Run logs and archives
├── tests/                  # Unit and integration tests
├── requirements.txt        # Python dependencies
├── env.example             # Environment variables template
└── README.md               # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- Virtual environment (recommended)
- API keys for:
  - Google Gemini (Google AI Studio)
  - Clay API
  - Apollo API
  - Clearbit API (or PDL API)
  - SendGrid API
  - Google Sheets API (service account)

### 2. Installation

1. **Clone or navigate to the project directory**

2. **Create and activate virtual environment** (if not already done):
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Environment Configuration

1. **Copy the environment template**:
   ```bash
   # On Windows
   copy env.example .env
   
   # On macOS/Linux
   cp env.example .env
   ```

2. **Edit `.env` file** and add your API keys:
   ```env
   GEMINI_API_KEY=your_actual_key_here
   CLAY_API_KEY=your_actual_key_here
   APOLLO_API_KEY=your_actual_key_here
   CLEARBIT_API_KEY=your_actual_key_here
   PDL_API_KEY=your_actual_key_here
   SENDGRID_API_KEY=your_actual_key_here
   SENDGRID_FROM_EMAIL=your-email@domain.com
   SENDGRID_FROM_NAME=Your Name
   GOOGLE_SHEETS_CREDS=./configs/service_account.json
   GOOGLE_SHEETS_ID=your_google_sheet_id_here
   ```

## License

[Add your license here]

## Support

[Add support contact information]
