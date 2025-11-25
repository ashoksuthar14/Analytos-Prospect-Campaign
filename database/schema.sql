-- Prospect-to-Lead Campaign Database Schema
-- SQLite Database

-- Runs table: Stores campaign execution runs
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, waiting_approval
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    config_snapshot TEXT,  -- JSON string of campaign config used
    error_message TEXT,
    metrics TEXT,  -- JSON string with metrics (total_leads, sent, replies, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leads table: Stores discovered and enriched leads
CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    domain TEXT,
    contact_email TEXT,
    contact_name TEXT,
    contact_title TEXT,
    revenue INTEGER,
    employee_count INTEGER,
    industry TEXT,
    location TEXT,
    enrichment_data TEXT,  -- JSON string with enrichment info
    score REAL,
    fit_score REAL,
    engagement_score REAL,
    intent_score REAL,
    apollo_contact_id TEXT,  -- Apollo contact ID after sync
    apollo_synced_at TIMESTAMP,  -- When contact was synced to Apollo
    apollo_sync_status TEXT,  -- Sync status: success, failed, skipped
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

-- Messages table: Stores generated and sent outreach messages
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    personalization_used TEXT,  -- JSON array of fields used
    provider TEXT,  -- sendgrid, apollo
    provider_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, sent, failed, bounced
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

-- Responses table: Tracks email engagement (opens, clicks, replies, meetings)
CREATE TABLE IF NOT EXISTS responses (
    response_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    opened BOOLEAN DEFAULT 0,
    opened_at TIMESTAMP,
    clicked BOOLEAN DEFAULT 0,
    clicked_at TIMESTAMP,
    replied BOOLEAN DEFAULT 0,
    replied_at TIMESTAMP,
    meeting_scheduled BOOLEAN DEFAULT 0,
    meeting_at TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);

-- Recommendations table: Stores feedback trainer recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    rec_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    field TEXT NOT NULL,  -- e.g., 'scoring.weights.fit_score', 'outreach_content.tone'
    old_value TEXT,  -- JSON string
    new_value TEXT,  -- JSON string
    reason TEXT,
    approved BOOLEAN DEFAULT 0,
    applied_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

-- Run logs table: Stores execution logs for each agent step
CREATE TABLE IF NOT EXISTS run_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    step TEXT NOT NULL,  -- start, tool_call, output, error
    input_data TEXT,  -- JSON string
    output_data TEXT,  -- JSON string
    error_data TEXT,  -- JSON string
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,  -- Duration in milliseconds
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_workflow_name ON runs(workflow_name);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_leads_run_id ON leads(run_id);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);
CREATE INDEX IF NOT EXISTS idx_leads_apollo_contact_id ON leads(apollo_contact_id);
CREATE INDEX IF NOT EXISTS idx_leads_apollo_sync_status ON leads(apollo_sync_status);
CREATE INDEX IF NOT EXISTS idx_messages_run_id ON messages(run_id);
CREATE INDEX IF NOT EXISTS idx_messages_lead_id ON messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_responses_message_id ON responses(message_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_run_id ON recommendations(run_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_approved ON recommendations(approved);
CREATE INDEX IF NOT EXISTS idx_run_logs_run_id ON run_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_run_logs_agent_name ON run_logs(agent_name);
CREATE INDEX IF NOT EXISTS idx_run_logs_timestamp ON run_logs(timestamp);

