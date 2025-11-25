// Run Detail Page JavaScript
const API_BASE = window.location.origin;
let socket = null;
let currentRunId = null;
let currentTab = 'leads';
let leadsPage = 1;
let messagesPage = 1;
const pendingHumanPrompts = {};
let currentHumanPrompt = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentRunId = urlParams.get('id');
    
    if (!currentRunId) {
        window.location.href = 'index.html';
        return;
    }
    
    initializeSocket();
    loadRunDetails();
    setupEventListeners();
    setupTabs();
});

// WebSocket Connection
function initializeSocket() {
    socket = io(API_BASE);
    
    socket.on('connect', () => {
        console.log('Connected to server');
        if (currentRunId) {
            socket.emit('join_run', { run_id: currentRunId });
        }
    });
    
    socket.on('progress_update', (data) => {
        if (data.run_id === currentRunId) {
            updateProgress(data);
            renderAgentPipeline(data);
            if (data.human_in_loop) {
                handleHumanInLoop(data);
            }
            if (data.human_in_loop_ack) {
                handleHumanInputAck(data);
            }
        }
    });
}

// Load Run Details
async function loadRunDetails() {
    try {
        const response = await fetch(`${API_BASE}/api/runs/${currentRunId}`);
        const data = await response.json();
        
        if (!data || data.error) {
            throw new Error(data.error || 'Run not found');
        }
        
        renderRunInfo(data);
        loadTabData(currentTab);
    } catch (error) {
        showError('Failed to load run details');
        console.error(error);
    }
}

// Render Run Information
function renderRunInfo(run) {
    // Set campaign name and run ID
    const campaignName = run.campaign_name || run.workflow_name || 'Unnamed Campaign';
    document.getElementById('campaignNameDisplay').textContent = campaignName;
    document.getElementById('runIdDisplay').textContent = `Run ID: ${run.run_id.substring(0, 8)}...`;
    
    // Format status text
    const statusText = run.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const statusClass = run.status.toLowerCase().replace('_', '-');
    document.getElementById('runStatus').textContent = statusText;
    document.getElementById('runStatus').className = `status-pill status-${statusClass}`;
    
    // Format dates
    const startedDate = new Date(run.started_at);
    const formattedStarted = startedDate.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric',
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true 
    });
    document.getElementById('startedAt').textContent = formattedStarted;
    
    if (run.completed_at) {
        const completedDate = new Date(run.completed_at);
        const formattedCompleted = completedDate.toLocaleString('en-US', { 
            month: 'short', 
            day: 'numeric', 
            year: 'numeric',
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
        document.getElementById('completedAt').textContent = formattedCompleted;
    } else {
        document.getElementById('completedAt').textContent = '-';
    }
    
    const progress = run.progress?.progress_percent || 0;
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${progress.toFixed(0)}%`;
    
    // Update counts
    if (run.metrics) {
        const metrics = typeof run.metrics === 'string' ? JSON.parse(run.metrics) : run.metrics;
        document.getElementById('leadsCount').textContent = metrics.total_leads || 0;
        document.getElementById('messagesCount').textContent = metrics.messages_sent || 0;
    }

    if (run.progress && run.progress.agent_statuses) {
        renderAgentPipeline({
            run_id: run.run_id,
            agent_statuses: run.progress.agent_statuses
        });
    }
}

// Update Progress (WebSocket)
function updateProgress(data) {
    const progress = data.progress || 0;
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${progress.toFixed(0)}%`;
    
    if (data.status) {
        const statusText = data.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const statusClass = data.status.toLowerCase().replace('_', '-');
        document.getElementById('runStatus').textContent = statusText;
        document.getElementById('runStatus').className = `status-pill status-${statusClass}`;
    }
    
    // Reload data if run completed
    if (data.status === 'completed' || data.status === 'failed') {
        loadRunDetails();
        if (pendingHumanPrompts[data.run_id]) {
            delete pendingHumanPrompts[data.run_id];
        }
        if (currentHumanPrompt && currentHumanPrompt.run_id === data.run_id) {
            hideHumanPrompt();
        }
    }
}

function renderAgentPipeline(progressData) {
    if (!progressData || !progressData.agent_statuses) {
        return;
    }

    const pipelineCard = document.getElementById('liveRunCard');
    const pipelineContainer = document.getElementById('agentPipeline');
    const runIdDisplay = document.getElementById('liveRunId');

    if (!pipelineCard || !pipelineContainer || !runIdDisplay) {
        return;
    }

    pipelineCard.style.display = 'block';
    const runId = progressData.run_id || '';
    runIdDisplay.textContent = runId ? `Run: ${runId.substring(0, 8)}...` : 'Run: -';
    pipelineContainer.innerHTML = '';

    const statuses = progressData.agent_statuses;
    const agents = Object.keys(statuses || {});

    if (agents.length === 0) {
        pipelineContainer.innerHTML = '<p class="empty-state">Awaiting agent updates...</p>';
        return;
    }

    agents.forEach(agentName => {
        const statusInfo = statuses[agentName] || {};
        pipelineContainer.appendChild(buildAgentNode(progressData.run_id, agentName, statusInfo));
    });

    attachReviewButtonHandlers(progressData.run_id);
}

function getAgentDescription(agentName) {
    const descriptions = {
        'prospect_search': 'Searches for B2B prospects matching your Ideal Customer Profile (ICP) criteria using Apollo API. Finds companies and contacts based on industry, location, revenue, employee count, and tech stack.',
        'data_enrichment': 'Enriches leads with additional firmographic and technographic data. Combines Apollo People and Organization enrichment to gather company details, tech stack, employee count, revenue, and contact information.',
        'scoring': 'Ranks leads using weighted scoring criteria including fit score, engagement signals, and intent indicators. Sorts leads by their likelihood to convert.',
        'apollo_contact_sync': 'Syncs scored leads to Apollo CRM as contacts. Ensures all enriched lead data is available in your Apollo account for further management and tracking.',
        'outreach_content': 'Generates personalized email subject lines and body content using AI (Groq). Creates customized outreach messages based on company context, role, industry, and tech stack.',
        'apollo_content_sync': 'Updates Apollo contacts with generated outreach message data. Links email content to contacts for tracking and follow-up management.',
        'outreach_executor': 'Sends outreach emails via SendGrid or Apollo. Handles email delivery and manages sending schedules. (Coming soon)',
        'response_tracker': 'Tracks email opens, clicks, replies, and meeting bookings. Monitors engagement metrics and response rates for outreach campaigns. (Coming soon)',
        'feedback_trainer': 'Analyzes outreach performance data and generates optimization recommendations. Uses AI to suggest improvements for better response rates. (Coming soon)'
    };
    return descriptions[agentName] || 'Agent description not available.';
}

function buildAgentNode(runId, agentName, statusInfo) {
    const node = document.createElement('div');
    const statusKey = (statusInfo.status || 'pending').replace(/_/g, '-');
    
    // List of inactive agents (not currently in use but will be available in future)
    const inactiveAgents = ['outreach_executor', 'response_tracker', 'feedback_trainer'];
    const isInactive = inactiveAgents.includes(agentName);
    
    node.className = `agent-node status-${statusKey}${isInactive ? ' inactive-agent' : ''}`;

    const statusLabel = formatStatus(statusInfo.status);
    const resultLabel = statusInfo.result_status ? formatStatus(statusInfo.result_status) : null;
    const duration = typeof statusInfo.duration_ms !== 'undefined' && statusInfo.duration_ms !== null
        ? Math.round(Number(statusInfo.duration_ms))
        : null;

    node.innerHTML = `
        <div class="agent-node-header">
            <div class="agent-node-name-wrapper">
                <span class="agent-node-name">${formatAgentName(agentName)}</span>
                <i class="fas fa-info-circle agent-info-icon" data-agent="${agentName}" title="Click for more info"></i>
            </div>
            <span class="agent-node-state">${statusLabel}</span>
        </div>
        <div class="agent-node-meta">
            ${resultLabel ? `<span class="agent-node-result">${resultLabel}</span>` : ''}
            ${duration !== null && !Number.isNaN(duration) ? `<span><i class="fas fa-clock"></i> ${duration} ms</span>` : ''}
        </div>
    `;

    if ((statusInfo.status || '').toLowerCase() === 'waiting_input') {
        const actions = document.createElement('div');
        actions.className = 'agent-node-actions';
        const btn = document.createElement('button');
        btn.className = 'agent-review-btn';
        btn.dataset.runId = runId;
        btn.dataset.agent = agentName;
        btn.innerHTML = '<i class="fas fa-user-check"></i> Review & Submit';
        actions.appendChild(btn);
        node.appendChild(actions);
    }

    // Add click handler for info icon
    const infoIcon = node.querySelector('.agent-info-icon');
    if (infoIcon) {
        infoIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            showAgentTooltip(e.target, agentName);
        });
    }

    return node;
}

function showAgentTooltip(iconElement, agentName) {
    // Remove existing tooltip if any
    const existingTooltip = document.querySelector('.agent-tooltip');
    if (existingTooltip) {
        existingTooltip.remove();
    }

    const description = getAgentDescription(agentName);
    const tooltip = document.createElement('div');
    tooltip.className = 'agent-tooltip';
    tooltip.innerHTML = `
        <div class="agent-tooltip-header">
            <span class="agent-tooltip-title">${formatAgentName(agentName)}</span>
            <button class="agent-tooltip-close" onclick="this.closest('.agent-tooltip').remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="agent-tooltip-content">
            ${description}
        </div>
    `;

    document.body.appendChild(tooltip);

    // Position tooltip near the icon
    const rect = iconElement.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    
    let top = rect.bottom + 10;
    let left = rect.left - (tooltipRect.width / 2) + (rect.width / 2);

    // Adjust if tooltip goes off screen
    if (left < 10) left = 10;
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }
    if (top + tooltipRect.height > window.innerHeight - 10) {
        top = rect.top - tooltipRect.height - 10;
    }

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;

    // Close tooltip when clicking outside
    setTimeout(() => {
        const closeOnClickOutside = (e) => {
            if (!tooltip.contains(e.target) && e.target !== iconElement) {
                tooltip.remove();
                document.removeEventListener('click', closeOnClickOutside);
            }
        };
        document.addEventListener('click', closeOnClickOutside);
    }, 100);
}

function attachReviewButtonHandlers(runId) {
    const pipelineContainer = document.getElementById('agentPipeline');
    if (!pipelineContainer) return;

    pipelineContainer.querySelectorAll('.agent-review-btn').forEach(button => {
        button.addEventListener('click', () => {
            const agent = button.dataset.agent;
            const prompt = pendingHumanPrompts[runId]?.[agent];
            if (prompt) {
                openHumanPrompt(prompt);
            }
        });
    });
}

function handleHumanInLoop(data) {
    if (!data || !data.human_in_loop) return;

    const prompt = {
        ...data.human_in_loop,
        run_id: data.run_id
    };

    if (!pendingHumanPrompts[data.run_id]) {
        pendingHumanPrompts[data.run_id] = {};
    }
    pendingHumanPrompts[data.run_id][prompt.agent] = prompt;

    openHumanPrompt(prompt);
}

function handleHumanInputAck(data) {
    const ack = data.human_in_loop_ack;
    if (!ack) return;

    const runPrompts = pendingHumanPrompts[data.run_id];
    if (runPrompts && runPrompts[ack.agent]) {
        delete runPrompts[ack.agent];
    }

    if (currentHumanPrompt && currentHumanPrompt.run_id === data.run_id && currentHumanPrompt.agent === ack.agent) {
        hideHumanPrompt();
    }
}

function openHumanPrompt(prompt) {
    const container = document.getElementById('humanPromptContainer');
    const fieldsContainer = document.getElementById('humanPromptFields');
    const agentLabel = document.getElementById('humanPromptAgent');
    const promptText = document.getElementById('humanPromptText');

    if (!container || !fieldsContainer || !agentLabel || !promptText) {
        return;
    }

    currentHumanPrompt = prompt;
    agentLabel.textContent = formatAgentName(prompt.agent);
    promptText.textContent = prompt.prompt || 'Manual input is required to continue the campaign.';

    fieldsContainer.innerHTML = '';
    const fields = Array.isArray(prompt.fields) && prompt.fields.length > 0
        ? prompt.fields
        : [{ name: 'approval', type: 'boolean', label: 'Approve campaign action', default: true }];

    fields.forEach(field => {
        fieldsContainer.appendChild(renderPromptField(field));
    });

    container.classList.remove('hidden');
}

function renderPromptField(field) {
    const wrapper = document.createElement('div');
    wrapper.className = 'prompt-field';
    const fieldId = `prompt_${field.name}`;
    const label = field.label || formatAgentName(field.name);

    if (field.type === 'boolean') {
        wrapper.innerHTML = `
            <label class="checkbox-field">
                <input type="checkbox" id="${fieldId}" name="${field.name}" ${field.default ? 'checked' : ''}>
                ${label}
            </label>
            ${field.description ? `<p class="field-hint">${field.description}</p>` : ''}
        `;
    } else {
        const inputType = field.type === 'number' ? 'number' : 'text';
        const elementTag = field.type === 'string' || field.type === 'text' ? 'textarea' : 'input';
        const defaultValue = field.default || '';

        if (elementTag === 'textarea') {
            wrapper.innerHTML = `
                <label for="${fieldId}">${label}${field.required ? ' *' : ''}</label>
                <textarea id="${fieldId}" name="${field.name}" rows="3" placeholder="${field.placeholder || ''}">${defaultValue}</textarea>
                ${field.description ? `<p class="field-hint">${field.description}</p>` : ''}
            `;
        } else {
            wrapper.innerHTML = `
                <label for="${fieldId}">${label}${field.required ? ' *' : ''}</label>
                <input type="${inputType}" id="${fieldId}" name="${field.name}" value="${defaultValue}" placeholder="${field.placeholder || ''}">
                ${field.description ? `<p class="field-hint">${field.description}</p>` : ''}
            `;
        }
    }

    return wrapper;
}

function hideHumanPrompt(event) {
    if (event) {
        event.preventDefault();
    }
    const container = document.getElementById('humanPromptContainer');
    const fieldsContainer = document.getElementById('humanPromptFields');
    if (container) {
        container.classList.add('hidden');
    }
    if (fieldsContainer) {
        fieldsContainer.innerHTML = '';
    }
    currentHumanPrompt = null;
}

async function handleHumanPromptSubmit(event) {
    event.preventDefault();
    if (!currentHumanPrompt) {
        return;
    }

    const form = event.target;
    const submitBtn = document.getElementById('humanPromptSubmitBtn');
    const fields = Array.isArray(currentHumanPrompt.fields) && currentHumanPrompt.fields.length > 0
        ? currentHumanPrompt.fields
        : [{ name: 'approval', type: 'boolean' }];

    const inputPayload = {};
    let hasValidationError = false;

    fields.forEach(field => {
        const element = form.elements[field.name];
        if (element && element.classList) {
            element.classList.remove('input-error');
        }
        if (field.type === 'boolean') {
            inputPayload[field.name] = element ? element.checked : false;
        } else {
            const value = element ? element.value.trim() : '';
            if (field.required && !value) {
                hasValidationError = true;
                if (element && element.classList) {
                    element.classList.add('input-error');
                }
            }
            inputPayload[field.name] = value;
        }
    });

    if (hasValidationError) {
        showError('Please complete all required fields.');
        return;
    }

    try {
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting';
        }

        const response = await fetch(`${API_BASE}/api/runs/${currentHumanPrompt.run_id}/agents/${currentHumanPrompt.agent}/human-input`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input: inputPayload,
                submitted_at: new Date().toISOString()
            })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || 'Failed to submit approval');
        }

        const runPrompts = pendingHumanPrompts[currentHumanPrompt.run_id];
        if (runPrompts) {
            delete runPrompts[currentHumanPrompt.agent];
        }

        showSuccess('Decision submitted. Campaign will resume.');
        hideHumanPrompt();

    } catch (error) {
        showError(error.message || 'Failed to submit approval');
        console.error(error);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit';
        }
    }
}

function formatAgentName(name) {
    // Custom display name mappings
    const displayNames = {
        'apollo_content_sync': 'Apollo Content Sync'
    };
    
    if (displayNames[name]) {
        return displayNames[name];
    }
    
    return name
        ? name.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase())
        : 'Unknown Agent';
}

function formatStatus(status) {
    if (!status) {
        return 'Pending';
    }
    return status.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}

// Setup Tabs
function setupTabs() {
    const tabButtons = document.querySelectorAll('.campaign-tab');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });
}

// Switch Tab
function switchTab(tab) {
    currentTab = tab;
    
    // Update active tab button
    document.querySelectorAll('.campaign-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    // Update active tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tab}Tab`);
    });
    
    // Load tab data
    loadTabData(tab);
}

// Load Tab Data
async function loadTabData(tab) {
    switch(tab) {
        case 'leads':
            await loadLeads();
            break;
        case 'messages':
            await loadMessages();
            break;
        case 'responses':
            await loadResponses();
            break;
    }
}

// Load Leads
async function loadLeads() {
    try {
        const response = await fetch(
            `${API_BASE}/api/runs/${currentRunId}/leads?limit=50&offset=${(leadsPage - 1) * 50}`
        );
        const data = await response.json();
        
        renderLeadsTable(data.leads || []);
        renderPagination('leadsPagination', leadsPage, Math.ceil(data.total / 50), (page) => {
            leadsPage = page;
            loadLeads();
        });
        
        // Update leads count in tab
        document.getElementById('leadsCount').textContent = data.total || 0;
    } catch (error) {
        document.getElementById('leadsTableBody').innerHTML = 
            '<tr><td colspan="6" class="loading">Error loading leads</td></tr>';
        console.error(error);
    }
}

// Global map to store leads data (accessible across function calls)
const leadsDataMap = new Map();

// Render Leads Table
function renderLeadsTable(leads) {
    const tbody = document.getElementById('leadsTableBody');
    
    if (leads.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state-row">
                    <div class="empty-state-content">
                        <i class="fas fa-inbox"></i>
                        <p>No leads found</p>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    // Clear previous data
    leadsDataMap.clear();
    
    tbody.innerHTML = leads.map((lead, index) => {
        const score = lead.score ? lead.score.toFixed(1) : '-';
        const leadId = lead.lead_id || lead.id || `lead_${index}`;
        
        // Normalize enrichment data for display
        const normalizedLead = { ...lead };
        if (lead.enrichment_data && !lead.enrichment) {
            normalizedLead.enrichment = lead.enrichment_data;
        }
        
        // Store lead data in global map
        leadsDataMap.set(leadId, normalizedLead);
        
        return `
            <tr class="table-row">
                <td class="company-cell"><strong>${escapeHtml(lead.company_name || '-')}</strong></td>
                <td>${escapeHtml(lead.contact_name || '-')}</td>
                <td>${escapeHtml(lead.contact_email || '-')}</td>
                <td><span class="score-badge">${score}</span></td>
                <td>${escapeHtml(lead.industry || '-')}</td>
                <td class="actions-cell">
                    <button class="btn-enrichment enrichment-btn" 
                            data-lead-id="${leadId}"
                            title="View Enrichment Data">
                        <i class="fas fa-database"></i> Enrichment
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    
    // Attach event listeners to enrichment buttons
    tbody.querySelectorAll('.enrichment-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            try {
                const leadId = this.getAttribute('data-lead-id');
                const leadData = leadsDataMap.get(leadId);
                
                if (!leadData) {
                    console.error('Lead data not found for ID:', leadId);
                    alert('Error: Lead data not found. Please refresh the page.');
                    return;
                }
                
                showEnrichmentModal(leadData);
            } catch (e) {
                console.error('Error loading enrichment data:', e);
                console.error('Error details:', e.stack);
                alert('Error loading enrichment data: ' + e.message);
            }
        });
    });
}

// Load Messages
async function loadMessages() {
    try {
        const response = await fetch(
            `${API_BASE}/api/runs/${currentRunId}/messages?limit=50&offset=${(messagesPage - 1) * 50}`
        );
        const data = await response.json();
        
        renderMessagesTable(data.messages || []);
        renderPagination('messagesPagination', messagesPage, Math.ceil(data.total / 50), (page) => {
            messagesPage = page;
            loadMessages();
        });
        
        // Update messages count in tab
        document.getElementById('messagesCount').textContent = data.total || 0;
    } catch (error) {
        document.getElementById('messagesTableBody').innerHTML = 
            '<tr><td colspan="5" class="loading">Error loading messages</td></tr>';
        console.error(error);
    }
}

// Render Messages Table
function renderMessagesTable(messages) {
    const tbody = document.getElementById('messagesTableBody');
    
    if (messages.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="empty-state-row">
                    <div class="empty-state-content">
                        <i class="fas fa-inbox"></i>
                        <p>No messages found</p>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = messages.map((msg, index) => {
        const statusText = msg.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const statusClass = msg.status.toLowerCase().replace('_', '-');
        const bodyPreviewRaw = msg.body || '';
        const bodyPreview = bodyPreviewRaw.length > 120 ? `${bodyPreviewRaw.slice(0, 117)}...` : bodyPreviewRaw || '-';
        const encodedSubject = encodeURIComponent(msg.subject || '');
        const encodedBody = encodeURIComponent(msg.body || '');
        const safeSubject = escapeHtml(msg.subject || '-');
        const subjectIsTruncated = (msg.subject || '').length > 60;
        const bodyIsTruncated = (msg.body || '').length > 120;
        return `
            <tr class="table-row" data-message-id="${msg.message_id}" data-msg-index="${index}">
                <td>
                    <strong class="clickable-text ${subjectIsTruncated ? 'truncated' : ''}" 
                            data-action="view-message"
                            title="${subjectIsTruncated ? 'Click to view full subject' : ''}">
                        ${safeSubject}
                    </strong>
                </td>
                <td>
                    <span class="clickable-text ${bodyIsTruncated ? 'truncated' : ''}" 
                          data-action="view-message"
                          title="${bodyIsTruncated ? 'Click to view full message' : ''}">
                        ${escapeHtml(bodyPreview)}
                    </span>
                </td>
                <td><span class="status-pill status-${statusClass}">${statusText}</span></td>
                <td class="actions-cell">
                    <button class="btn-message-action view-message-btn" data-message-id="${msg.message_id}" data-subject="${encodedSubject}" data-body="${encodedBody}" title="View Message">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-message-action copy-message-btn" data-subject="${encodedSubject}" data-body="${encodedBody}" title="Copy Message">
                        <i class="fas fa-copy"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    
    // Attach event listeners to clickable elements
    tbody.querySelectorAll('[data-action="view-message"]').forEach(element => {
        element.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const row = this.closest('tr');
            const messageId = row.getAttribute('data-message-id');
            const viewBtn = row.querySelector('.view-message-btn');
            if (viewBtn) {
                const subject = viewBtn.getAttribute('data-subject');
                const body = viewBtn.getAttribute('data-body');
                viewMessage(messageId, subject, body);
            }
        });
    });
    
    // Attach event listeners to action buttons
    tbody.querySelectorAll('.view-message-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const messageId = this.getAttribute('data-message-id');
            const subject = this.getAttribute('data-subject');
            const body = this.getAttribute('data-body');
            viewMessage(messageId, subject, body);
        });
    });
    
    tbody.querySelectorAll('.copy-message-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const subject = this.getAttribute('data-subject');
            const body = this.getAttribute('data-body');
            copyMessage(subject, body);
        });
    });
}

// Load Responses
async function loadResponses() {
    try {
        const response = await fetch(`${API_BASE}/api/runs/${currentRunId}/responses`);
        const data = await response.json();
        
        renderResponsesTable(data.responses || []);
    } catch (error) {
        document.getElementById('responsesTableBody').innerHTML = 
            '<tr><td colspan="6" class="loading">Error loading responses</td></tr>';
        console.error(error);
    }
}

// Render Responses Table
function renderResponsesTable(responses) {
    const tbody = document.getElementById('responsesTableBody');
    
    if (responses.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state-row">
                    <div class="empty-state-content">
                        <i class="fas fa-inbox"></i>
                        <p>No responses found</p>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = responses.map(resp => {
        return `
            <tr class="table-row">
                <td class="message-id-cell">
                    <span class="message-id-badge">${resp.message_id.substring(0, 8)}...</span>
                </td>
                <td class="response-indicator">
                    ${resp.opened ? '<i class="fas fa-check-circle text-success"></i>' : '<i class="fas fa-minus-circle text-tertiary"></i>'}
                </td>
                <td class="response-indicator">
                    ${resp.clicked ? '<i class="fas fa-check-circle text-success"></i>' : '<i class="fas fa-minus-circle text-tertiary"></i>'}
                </td>
                <td class="response-indicator">
                    ${resp.replied ? '<i class="fas fa-check-circle text-success"></i>' : '<i class="fas fa-minus-circle text-tertiary"></i>'}
                </td>
                <td class="response-indicator">
                    ${resp.meeting_scheduled ? '<i class="fas fa-check-circle text-success"></i>' : '<i class="fas fa-minus-circle text-tertiary"></i>'}
                </td>
                <td class="actions-cell">-</td>
            </tr>
        `;
    }).join('');
}

// View Message Preview
function viewMessage(messageId, encodedSubject, encodedBody) {
    const subject = decodeURIComponent(encodedSubject || '');
    const body = decodeURIComponent(encodedBody || '');
    document.getElementById('previewSubject').textContent = subject;
    // Format body with line breaks preserved
    const formattedBody = body.replace(/\n/g, '<br>');
    document.getElementById('previewBody').innerHTML = formattedBody;
    document.getElementById('messageModal').classList.add('active');
}

// Show Enrichment Modal
function showEnrichmentModal(lead) {
    try {
        const modal = document.getElementById('enrichmentModal');
        const content = document.getElementById('enrichmentContent');
        
        if (!modal || !content) {
            console.error('Enrichment modal elements not found');
            alert('Error: Modal elements not found. Please refresh the page.');
            return;
        }
        
        // Normalize enrichment data (could be 'enrichment' or 'enrichment_data')
        let enrichment = {};
        if (lead.enrichment) {
            enrichment = typeof lead.enrichment === 'string' ? JSON.parse(lead.enrichment) : lead.enrichment;
        } else if (lead.enrichment_data) {
            enrichment = typeof lead.enrichment_data === 'string' ? JSON.parse(lead.enrichment_data) : lead.enrichment_data;
        }
        
        const firmographics = enrichment.firmographics || {};
        const roleDetails = enrichment.role_details || {};
    
    let html = `
        <div class="enrichment-section">
            <h3 class="enrichment-section-title">Basic Information</h3>
            <div class="enrichment-grid">
                <div class="enrichment-item">
                    <label>Company Name:</label>
                    <span>${escapeHtml(lead.company_name || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Contact Name:</label>
                    <span>${escapeHtml(lead.contact_name || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Contact Email:</label>
                    <span>${escapeHtml(lead.contact_email || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Contact Title:</label>
                    <span>${escapeHtml(lead.contact_title || enrichment.title || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Industry:</label>
                    <span>${escapeHtml(lead.industry || enrichment.industry || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Domain:</label>
                    <span>${escapeHtml(lead.domain || enrichment.domain || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Location:</label>
                    <span>${escapeHtml(lead.location || '-')}</span>
                </div>
                <div class="enrichment-item">
                    <label>Score:</label>
                    <span class="badge">${lead.score ? lead.score.toFixed(1) : lead.fit_score ? lead.fit_score.toFixed(1) : '-'}</span>
                </div>
            </div>
        </div>
    `;
    
    // Company Size & Revenue
    if (lead.employee_count || lead.revenue || enrichment.employee_count || enrichment.revenue) {
        html += `
            <div class="enrichment-section">
                <h3 class="enrichment-section-title">Company Size & Revenue</h3>
                <div class="enrichment-grid">
                    ${lead.employee_count || enrichment.employee_count ? `
                        <div class="enrichment-item">
                            <label>Employee Count:</label>
                            <span>${escapeHtml(String(lead.employee_count || enrichment.employee_count))}</span>
                        </div>
                    ` : ''}
                    ${lead.revenue || enrichment.revenue ? `
                        <div class="enrichment-item">
                            <label>Revenue:</label>
                            <span>${escapeHtml(String(lead.revenue || enrichment.revenue || '-'))}</span>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    // Firmographics
    if (firmographics.description || firmographics.founded_year || firmographics.headquarters || firmographics.tags) {
        html += `
            <div class="enrichment-section">
                <h3 class="enrichment-section-title">Firmographics</h3>
                <div class="enrichment-details">
                    ${firmographics.description ? `
                        <div class="enrichment-item-full">
                            <label>Company Description:</label>
                            <p>${escapeHtml(firmographics.description)}</p>
                        </div>
                    ` : ''}
                    <div class="enrichment-grid">
                        ${firmographics.founded_year ? `
                            <div class="enrichment-item">
                                <label>Founded Year:</label>
                                <span>${escapeHtml(String(firmographics.founded_year))}</span>
                            </div>
                        ` : ''}
                        ${firmographics.headquarters ? `
                            <div class="enrichment-item">
                                <label>Headquarters:</label>
                                <span>${escapeHtml(firmographics.headquarters)}</span>
                            </div>
                        ` : ''}
                        ${firmographics.tags && firmographics.tags.length > 0 ? `
                            <div class="enrichment-item-full">
                                <label>Tags:</label>
                                <div class="tags-list">
                                    ${firmographics.tags.map(tag => `<span class="tag">${escapeHtml(String(tag))}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    // Tech Stack
    const techStack = enrichment.tech_stack || lead.tech_stack || [];
    if (techStack.length > 0) {
        html += `
            <div class="enrichment-section">
                <h3 class="enrichment-section-title">Technology Stack</h3>
                <div class="tech-stack-list">
                    ${techStack.map(tech => `<span class="tech-badge">${escapeHtml(String(tech))}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    // Role Details
    if (enrichment.seniority || roleDetails.role || roleDetails.seniority) {
        html += `
            <div class="enrichment-section">
                <h3 class="enrichment-section-title">Role & Seniority</h3>
                <div class="enrichment-grid">
                    ${enrichment.seniority || roleDetails.seniority ? `
                        <div class="enrichment-item">
                            <label>Seniority:</label>
                            <span>${escapeHtml(enrichment.seniority || roleDetails.seniority || '-')}</span>
                        </div>
                    ` : ''}
                    ${roleDetails.role ? `
                        <div class="enrichment-item">
                            <label>Role:</label>
                            <span>${escapeHtml(roleDetails.role)}</span>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    // LinkedIn
    if (enrichment.linkedin_url || lead.linkedin_url) {
        html += `
            <div class="enrichment-section">
                <h3 class="enrichment-section-title">Social & Links</h3>
                <div class="enrichment-grid">
                    <div class="enrichment-item">
                        <label>LinkedIn:</label>
                        <span>
                            ${enrichment.linkedin_url || lead.linkedin_url ? 
                                `<a href="${enrichment.linkedin_url || lead.linkedin_url}" target="_blank" rel="noopener noreferrer">
                                    ${escapeHtml(enrichment.linkedin_url || lead.linkedin_url)}
                                </a>` : '-'}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Enrichment Source
    if (lead.enrichment_source || enrichment.enrichment_source) {
        html += `
            <div class="enrichment-section">
                <h3 class="enrichment-section-title">Enrichment Metadata</h3>
                <div class="enrichment-grid">
                    <div class="enrichment-item">
                        <label>Enrichment Source:</label>
                        <span class="badge badge-info">${escapeHtml(lead.enrichment_source || enrichment.enrichment_source || 'unknown')}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Raw JSON (collapsible)
    html += `
        <div class="enrichment-section">
            <h3 class="enrichment-section-title">
                <span>Raw Data (JSON)</span>
                <button class="btn-toggle-json" id="toggleJsonBtn">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </h3>
            <div id="jsonView" class="json-view" style="display: none;">
                <pre>${escapeHtml(JSON.stringify(lead, null, 2))}</pre>
            </div>
        </div>
    `;
    
    content.innerHTML = html;
    modal.classList.add('active');
    
    // Attach event listener for JSON toggle
    const toggleBtn = document.getElementById('toggleJsonBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            const jsonView = document.getElementById('jsonView');
            const icon = this.querySelector('i');
            if (jsonView) {
                if (jsonView.style.display === 'none' || !jsonView.style.display) {
                    jsonView.style.display = 'block';
                    if (icon) {
                        icon.classList.remove('fa-chevron-down');
                        icon.classList.add('fa-chevron-up');
                    }
                } else {
                    jsonView.style.display = 'none';
                    if (icon) {
                        icon.classList.remove('fa-chevron-up');
                        icon.classList.add('fa-chevron-down');
                    }
                }
            }
        });
    }
    } catch (error) {
        console.error('Error showing enrichment modal:', error);
        console.error('Error details:', error.stack);
        alert('Error displaying enrichment data: ' + error.message);
    }
}

// Copy Message
function copyMessage(encodedSubject, encodedBody) {
    const subject = decodeURIComponent(encodedSubject || '');
    const body = decodeURIComponent(encodedBody || '');
    const text = `Subject: ${subject}\n\n${body}`;
    navigator.clipboard.writeText(text).then(() => {
        showSuccess('Message copied to clipboard!');
    }).catch(err => {
        showError('Failed to copy message');
    });
}

// View Lead Details
function viewLeadDetails(leadId) {
    // Could open a modal with lead details
    console.log('View lead:', leadId);
}

// Render Pagination
function renderPagination(containerId, currentPage, totalPages, onPageChange) {
    const container = document.getElementById(containerId);
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = '';
    if (currentPage > 1) {
        html += `<button onclick="changePage(${currentPage - 1})">Previous</button>`;
    }
    
    html += `<span>Page ${currentPage} of ${totalPages}</span>`;
    
    if (currentPage < totalPages) {
        html += `<button onclick="changePage(${currentPage + 1})">Next</button>`;
    }
    
    container.innerHTML = html;
    
    // Store callback
    window.changePage = onPageChange;
}

// Event Listeners
function setupEventListeners() {
    const humanPromptForm = document.getElementById('humanPromptForm');
    if (humanPromptForm) {
        humanPromptForm.addEventListener('submit', handleHumanPromptSubmit);
    }

    const humanPromptDismissBtn = document.getElementById('humanPromptDismissBtn');
    if (humanPromptDismissBtn) {
        humanPromptDismissBtn.addEventListener('click', hideHumanPrompt);
    }

    // Export buttons
    document.getElementById('exportCsvBtn').addEventListener('click', () => {
        window.location.href = `${API_BASE}/api/export/runs/${currentRunId}/csv`;
    });
    
    document.getElementById('exportJsonBtn').addEventListener('click', async () => {
        const response = await fetch(`${API_BASE}/api/export/runs/${currentRunId}/json`);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `run_${currentRunId}.json`;
        a.click();
    });
    
    // Message Modal
    document.getElementById('closeMessageModal').addEventListener('click', () => {
        document.getElementById('messageModal').classList.remove('active');
    });
    
    document.getElementById('closePreviewBtn').addEventListener('click', () => {
        document.getElementById('messageModal').classList.remove('active');
    });
    
    // Enrichment Modal
    const closeEnrichmentModal = document.getElementById('closeEnrichmentModal');
    const closeEnrichmentBtn = document.getElementById('closeEnrichmentBtn');
    if (closeEnrichmentModal) {
        closeEnrichmentModal.addEventListener('click', () => {
            document.getElementById('enrichmentModal').classList.remove('active');
        });
    }
    if (closeEnrichmentBtn) {
        closeEnrichmentBtn.addEventListener('click', () => {
            document.getElementById('enrichmentModal').classList.remove('active');
        });
    }
    
    document.getElementById('copyMessageBtn').addEventListener('click', () => {
        const subject = document.getElementById('previewSubject').textContent;
        const body = document.getElementById('previewBody').textContent;
        copyMessage(subject, body);
    });
    
    // Search
    document.getElementById('leadsSearch').addEventListener('input', (e) => {
        filterTable('leadsTableBody', e.target.value);
    });
    
    document.getElementById('messagesSearch').addEventListener('input', (e) => {
        filterTable('messagesTableBody', e.target.value);
    });
}

// Filter Table
function filterTable(tableId, searchTerm) {
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tr');
    const term = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
    });
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    // Convert to string first, handling numbers, objects, arrays, etc.
    if (typeof text !== 'string') {
        if (typeof text === 'number') {
            text = String(text);
        } else if (typeof text === 'object') {
            // For objects/arrays, stringify them
            try {
                text = JSON.stringify(text);
            } catch (e) {
                text = String(text);
            }
        } else {
            text = String(text);
        }
    }
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Utility Functions
function showError(message) {
    alert(`Error: ${message}`);
}

function showSuccess(message) {
    alert(`Success: ${message}`);
}

