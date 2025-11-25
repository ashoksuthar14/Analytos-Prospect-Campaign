# Prospect-to-Lead LangGraph Campaign

An end-to-end, config-driven agent system that discovers B2B prospects, enriches & scores them, generates outreach, sends emails, tracks replies, and learns from results — all orchestrated by a single `workflow.json`.

## Features

- **Config-Driven Campaign**: Define your entire prospecting campaign in a single JSON file
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
│   ├── workflow.json       # Main campaign configuration
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

### 4. Google Sheets Setup

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one

2. **Enable Google Sheets API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

3. **Create Service Account**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in service account details
   - Click "Create and Continue"
   - Skip role assignment (optional)
   - Click "Done"

4. **Generate Service Account Key**:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Select "JSON" format
   - Download the JSON file
   - Save it as `configs/service_account.json`

5. **Share Google Sheet**:
   - Open or create your Google Sheet
   - Click "Share" button
   - Add the service account email (found in the JSON file, e.g., `your-service@project.iam.gserviceaccount.com`)
   - Give it "Editor" permissions
   - Copy the Sheet ID from the URL (the long string between `/d/` and `/edit`)
   - Add it to `.env` as `GOOGLE_SHEETS_ID`

### 5. Database Setup

The database will be automatically created on first run. The default path is `./database/prospect_workflow.db`.

### 6. Run the Application

```bash
# From project root
python -m app.app
```

Or if you have a run script:
```bash
python run.py
```

The application will be available at `http://localhost:5000`

## Configuration

### Campaign Configuration

Edit `configs/workflow.json` to customize:
- Agent order and dependencies
- ICP criteria (industry, location, revenue, etc.)
- Scoring weights
- Conditional branching rules
- Tool configurations per agent
- Gemini prompts and tone

### Rate Limits

Default limits (configurable in `workflow.json`):
- 50 leads per run
- 200 leads per day

## Usage

### Starting a Campaign Run

1. **Via API**:
   ```bash
   curl -X POST http://localhost:5000/api/run \
     -H "Content-Type: application/json" \
     -d '{"workflow_name": "prospect_to_lead_v1"}'
   ```

2. **Via Frontend**:
   - Navigate to the dashboard
   - Click "Start New Run"
   - Monitor progress in real-time

### Viewing Results

- **Dashboard**: `http://localhost:5000/` - Overview of all runs
- **Run Details**: `http://localhost:5000/runs/:id` - Detailed view of a specific run
- **Feedback**: `http://localhost:5000/feedback` - Review and approve recommendations

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings for all functions
- Classes: PascalCase
- Functions/variables: snake_case
- Files/folders: lowercase

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure all required keys are in `.env`
2. **Google Sheets Access**: Verify service account has Editor permissions
3. **Database Lock**: Check if another process is using the database
4. **Rate Limits**: Check API provider dashboards for usage

## License

[Add your license here]

## Support

[Add support contact information]

