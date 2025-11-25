// Main Dashboard JavaScript
// Version: 1.1.0 - Added campaign_name and progress tracking
const API_BASE = window.location.origin;
let socket = null;
const pendingHumanPrompts = {};
let currentHumanPrompt = null;
const joinedRuns = new Set();
let currentPage = 1;
const runsPerPage = 10;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeSocket();
    loadDashboard();
    setupEventListeners();
});

// WebSocket Connection
function initializeSocket() {
    socket = io(API_BASE);
    
    socket.on('connect', () => {
        console.log('Connected to server');
    });
    
    socket.on('progress_update', (data) => {
        updateRunProgress(data);
        renderAgentPipeline(data);
        if (data.human_in_loop) {
            handleHumanInLoop(data);
        }
        if (data.human_in_loop_ack) {
            handleHumanInputAck(data);
        }
        
        // Check for errors in progress update
        if (data.status === 'failed' || data.error) {
            showErrorDialog({
                title: 'Campaign Execution Failed',
                agent: data.current_agent || data.agent_name || 'Unknown',
                message: data.error?.message || data.message || 'An error occurred during campaign execution',
                error: data.error,
                run_id: data.run_id
            });
        }
    });
}

// Load Dashboard Data
async function loadDashboard() {
    try {
        await Promise.all([
            loadRuns(),
            loadStats()
        ]);
    } catch (error) {
        showError('Failed to load dashboard data');
        console.error(error);
    }
}

// Load Runs
async function loadRuns(page = 1) {
    try {
        const statusFilter = document.getElementById('statusFilter').value;
        const params = new URLSearchParams();
        if (statusFilter) params.append('status', statusFilter);
        params.append('limit', runsPerPage);
        params.append('offset', (page - 1) * runsPerPage);
        
        const response = await fetch(`${API_BASE}/api/runs?${params}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Loaded runs:', data.runs?.length || 0, 'Total:', data.total); // Debug log
        
        currentPage = page;
        renderRunsTable(data.runs || []);
        
        // Render pagination
        const totalPages = Math.ceil((data.total || data.runs.length) / runsPerPage);
        renderPagination(totalPages);
    } catch (error) {
        console.error('Error loading runs:', error);
        document.getElementById('runsTableBody').innerHTML = 
            `<tr><td colspan="6" class="loading">Error loading runs: ${error.message}</td></tr>`;
    }
}

// Load Stats
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/runs`);
        const data = await response.json();
        const runs = data.runs || [];
        
        const totalRuns = data.total || runs.length;
        const completedRuns = runs.filter(r => r.status === 'completed').length;
        const successRate = totalRuns > 0 ? (completedRuns / totalRuns * 100).toFixed(1) : 0;
        
        // Calculate reply and meeting rates from completed runs
        let totalReplies = 0;
        let totalMeetings = 0;
        let totalSent = 0;
        
        for (const run of runs) {
            if (run.metrics) {
                const metrics = typeof run.metrics === 'string' ? JSON.parse(run.metrics) : run.metrics;
                totalReplies += metrics.replies || 0;
                totalMeetings += metrics.meetings || 0;
                totalSent += metrics.messages_sent || 0;
            }
        }
        
        const replyRate = totalSent > 0 ? (totalReplies / totalSent * 100).toFixed(1) : 0;
        const meetingRate = totalSent > 0 ? (totalMeetings / totalSent * 100).toFixed(1) : 0;
        
        document.getElementById('totalRuns').textContent = totalRuns;
        document.getElementById('successRate').textContent = `${successRate}%`;
        document.getElementById('replyRate').textContent = `${replyRate}%`;
        document.getElementById('meetingRate').textContent = `${meetingRate}%`;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Render Runs Table
function renderRunsTable(runs) {
    const tbody = document.getElementById('runsTableBody');
    
    if (!tbody) {
        console.error('runsTableBody element not found!');
        return;
    }
    
    if (!runs || runs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state-row">
                    <div class="empty-state-content">
                        <i class="fas fa-inbox"></i>
                        <p>No runs found</p>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    try {
        tbody.innerHTML = runs.map(run => {
        const startedDate = new Date(run.started_at);
        const today = new Date();
        const isToday = startedDate.toDateString() === today.toDateString();
        
        // Format time based on whether it's today or not
        let timeDisplay;
        if (isToday) {
            timeDisplay = startedDate.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
        } else {
            timeDisplay = startedDate.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: startedDate.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
            }) + ', ' + startedDate.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
        }
        
        const statusClass = run.status.toLowerCase().replace('_', '-');
        // Use progress from run object (if available from DB) or fallback to calculating it
        let progress = 0;
        if (run.progress) {
            if (typeof run.progress === 'object' && run.progress.progress_percent !== undefined) {
                progress = run.progress.progress_percent;
            } else if (typeof run.progress === 'number') {
                progress = run.progress;
            }
        }
        
        // Format status text
        const statusText = run.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        return `
            <tr class="table-row">
                <td class="run-id-cell">
                    <span class="run-id-badge">${run.run_id.substring(0, 8)}...</span>
                </td>
                <td class="campaign-cell">
                    <span class="campaign-name">${run.campaign_name || run.workflow_name}</span>
                </td>
                <td>
                    <span class="status-pill status-${statusClass}">${statusText}</span>
                </td>
                <td class="time-cell">${timeDisplay}</td>
                <td class="progress-cell">
                    <div class="progress-container">
                        <div class="progress-bar-modern">
                            <div class="progress-fill-modern" style="width: ${progress}%"></div>
                        </div>
                        <span class="progress-text">${progress.toFixed(0)}%</span>
                    </div>
                </td>
                <td class="actions-cell">
                    <a href="run-detail.html?id=${run.run_id}" class="btn-view" title="View Details">
                        <i class="fas fa-eye"></i> View
                    </a>
                </td>
            </tr>
        `;
        }).join('');

        runs.forEach(run => {
            const status = (run.status || '').toLowerCase();
            if (status === 'running' || status === 'waiting_input') {
                joinRunRoom(run.run_id);
            }
        });
    } catch (error) {
        console.error('Error rendering runs table:', error);
        tbody.innerHTML = `<tr><td colspan="6" class="loading">Error rendering table: ${error.message}</td></tr>`;
    }
}

// Update Run Progress (WebSocket)
function updateRunProgress(data) {
    const rows = document.querySelectorAll('#runsTableBody tr');
    rows.forEach(row => {
        const runIdCell = row.querySelector('td code');
        if (runIdCell && runIdCell.textContent.includes(data.run_id.substring(0, 8))) {
            // Update status
            const statusCell = row.querySelector('.status-badge');
            if (statusCell) {
                statusCell.textContent = data.status;
                statusCell.className = `status-badge ${data.status.toLowerCase().replace('_', '-')}`;
            }
            
            // Update progress
            const progress = data.progress || 0;
            const progressFill = row.querySelector('.progress-fill');
            const progressText = row.querySelector('small');
            if (progressFill) progressFill.style.width = `${progress}%`;
            if (progressText) progressText.textContent = `${progress.toFixed(0)}%`;
        }
    });
    
    // Reload stats if run completed
    if (data.status === 'completed' || data.status === 'failed') {
        loadStats();
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
                element.classList.add('input-error');
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

function joinRunRoom(runId) {
    if (!socket || !runId || joinedRuns.has(runId)) {
        return;
    }
    socket.emit('join_run', { run_id: runId });
    joinedRuns.add(runId);
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

    // Start Run Button
    document.getElementById('startRunBtn').addEventListener('click', async () => {
        document.getElementById('startRunModal').classList.add('active');
        initializeICPForm();
    });
    
    // Close Modal
    document.getElementById('closeModalBtn').addEventListener('click', () => {
        document.getElementById('startRunModal').classList.remove('active');
    });
    
    document.getElementById('cancelRunBtn').addEventListener('click', () => {
        document.getElementById('startRunModal').classList.remove('active');
    });
    
    // Use Overrides Checkbox
    document.getElementById('useOverrides').addEventListener('change', (e) => {
        document.getElementById('overridesSection').style.display = 
            e.target.checked ? 'block' : 'none';
    });
    
    // Confirm Run
    document.getElementById('confirmRunBtn').addEventListener('click', async () => {
        await startRun();
    });
    
    // Refresh Button
    document.getElementById('refreshBtn').addEventListener('click', () => {
        loadDashboard();
    });
    
    // Apply Filters
    document.getElementById('applyFiltersBtn').addEventListener('click', () => {
        currentPage = 1;
        loadRuns(1);
    });
    
    // Close modal on outside click
    document.getElementById('startRunModal').addEventListener('click', (e) => {
        if (e.target.id === 'startRunModal') {
            document.getElementById('startRunModal').classList.remove('active');
        }
    });
    
    // Advanced Settings Toggle
    const toggleAdvancedBtn = document.getElementById('toggleAdvanced');
    const advancedSettings = document.getElementById('advancedSettings');
    
    if (toggleAdvancedBtn && advancedSettings) {
        toggleAdvancedBtn.addEventListener('click', () => {
            const isVisible = advancedSettings.style.display !== 'none';
            advancedSettings.style.display = isVisible ? 'none' : 'block';
            toggleAdvancedBtn.classList.toggle('active');
        });
    }
    
    // Slider handlers for scoring weights
    setupScoringWeightSliders();
    
    // Setup tag inputs for custom signals
    setupTagInputs();
}

// Setup Scoring Weight Sliders with Auto-Adjustment
function setupScoringWeightSliders() {
    const sliders = [
        { id: 'hiringWeight', valueId: 'hiringWeightValue', name: 'hiring' },
        { id: 'technologyWeight', valueId: 'technologyWeightValue', name: 'technology' },
        { id: 'financialWeight', valueId: 'financialWeightValue', name: 'financial' },
        { id: 'behavioralWeight', valueId: 'behavioralWeightValue', name: 'behavioral' }
    ];
    
    sliders.forEach(({ id, valueId, name }) => {
        const slider = document.getElementById(id);
        const valueDisplay = document.getElementById(valueId);
        
        if (slider && valueDisplay) {
            // Update display and gradient on input
            slider.addEventListener('input', (e) => {
                const newValue = parseInt(e.target.value);
                valueDisplay.textContent = `${newValue}%`;
                
                // Update slider gradient
                e.target.style.setProperty('--value', `${newValue}%`);
                
                // Auto-adjust other sliders to maintain 100% total
                autoAdjustWeights(name, newValue);
            });
            
            // Initialize gradient
            const value = slider.value;
            slider.style.setProperty('--value', `${value}%`);
        }
    });
    
    // Initialize total
    updateTotalWeight();
}

// Auto-adjust weights to maintain 100% total
function autoAdjustWeights(changedSlider, newValue) {
    const sliderIds = {
        hiring: 'hiringWeight',
        technology: 'technologyWeight',
        financial: 'financialWeight',
        behavioral: 'behavioralWeight'
    };
    
    // Get current values
    const weights = {
        hiring: parseInt(document.getElementById('hiringWeight').value),
        technology: parseInt(document.getElementById('technologyWeight').value),
        financial: parseInt(document.getElementById('financialWeight').value),
        behavioral: parseInt(document.getElementById('behavioralWeight').value)
    };
    
    // Set the changed value
    weights[changedSlider] = newValue;
    
    // Calculate how much we need to redistribute
    const currentTotal = Object.values(weights).reduce((a, b) => a + b, 0);
    const difference = currentTotal - 100;
    
    if (difference === 0) {
        updateTotalWeight();
        return;
    }
    
    // Get other sliders (not the one being changed)
    const otherSliders = Object.keys(weights).filter(key => key !== changedSlider);
    
    // Calculate total of other sliders
    const otherTotal = otherSliders.reduce((sum, key) => sum + weights[key], 0);
    
    if (otherTotal === 0) {
        // If all others are 0, distribute evenly
        const evenShare = Math.floor((100 - newValue) / 3);
        const remainder = (100 - newValue) - (evenShare * 3);
        
        otherSliders.forEach((key, index) => {
            weights[key] = evenShare + (index === 0 ? remainder : 0);
        });
    } else {
        // Redistribute proportionally among other sliders
        otherSliders.forEach(key => {
            const proportion = weights[key] / otherTotal;
            weights[key] = Math.max(0, Math.round(weights[key] - (difference * proportion)));
        });
        
        // Fine-tune to exactly 100
        const newTotal = Object.values(weights).reduce((a, b) => a + b, 0);
        if (newTotal !== 100) {
            const adjustment = 100 - newTotal;
            // Add adjustment to the largest other slider
            const largestOther = otherSliders.reduce((max, key) => 
                weights[key] > weights[max] ? key : max, otherSliders[0]
            );
            weights[largestOther] += adjustment;
        }
    }
    
    // Update all sliders
    Object.entries(weights).forEach(([key, value]) => {
        const slider = document.getElementById(sliderIds[key]);
        const valueDisplay = document.getElementById(`${key}WeightValue`);
        
        if (slider && valueDisplay) {
            slider.value = value;
            valueDisplay.textContent = `${value}%`;
            slider.style.setProperty('--value', `${value}%`);
        }
    });
    
    updateTotalWeight();
}

// Update Total Weight Display
function updateTotalWeight() {
    const hiringWeight = parseInt(document.getElementById('hiringWeight')?.value || 0);
    const technologyWeight = parseInt(document.getElementById('technologyWeight')?.value || 0);
    const financialWeight = parseInt(document.getElementById('financialWeight')?.value || 0);
    const behavioralWeight = parseInt(document.getElementById('behavioralWeight')?.value || 0);
    
    const total = hiringWeight + technologyWeight + financialWeight + behavioralWeight;
    
    const totalDisplay = document.getElementById('totalWeight');
    const totalContainer = totalDisplay?.parentElement;
    
    if (totalDisplay) {
        totalDisplay.textContent = `${total}%`;
        
        // Visual feedback - should always be 100% now with auto-adjustment
        if (totalContainer) {
            if (total === 100) {
                totalContainer.classList.remove('invalid');
                totalContainer.classList.add('valid');
            } else {
                totalContainer.classList.add('invalid');
                totalContainer.classList.remove('valid');
            }
        }
    }
    
    return total;
}

// Initialize ICP Form with default values
async function initializeICPForm() {
    try {
        // Load default values from campaign config
        const response = await fetch(`${API_BASE}/api/config`);
        if (response.ok) {
            const campaign = await response.json();
            const prospectSearchAgent = campaign.agents.find(agent => agent.name === 'prospect_search');
            const scoringAgent = campaign.agents.find(agent => agent.name === 'scoring');
            
            if (prospectSearchAgent && prospectSearchAgent.inputs) {
                const icp = prospectSearchAgent.inputs.icp || {};
                const signals = prospectSearchAgent.inputs.signals || {};
                
                // Set default ICP values
                if (icp.industry) {
                    document.getElementById('icpIndustry').value = icp.industry;
                }
                if (icp.location) {
                    document.getElementById('icpLocation').value = icp.location;
                }
                if (icp.employee_count) {
                    document.getElementById('icpEmployeeMin').value = icp.employee_count.min || 100;
                    document.getElementById('icpEmployeeMax').value = icp.employee_count.max || 1000;
                }
                if (icp.revenue) {
                    document.getElementById('icpRevenueMin').value = icp.revenue.min || 20000000;
                    document.getElementById('icpRevenueMax').value = icp.revenue.max || 200000000;
                }
                
                // Set default signals (check checkboxes that match)
                if (signals.hiring && Array.isArray(signals.hiring)) {
                    signals.hiring.forEach(signal => {
                        const checkbox = document.querySelector(`input[name="hiring_signals"][value="${signal}"]`);
                        if (checkbox) checkbox.checked = true;
                    });
                }
                if (signals.technology && Array.isArray(signals.technology)) {
                    signals.technology.forEach(signal => {
                        const checkbox = document.querySelector(`input[name="technology_signals"][value="${signal}"]`);
                        if (checkbox) checkbox.checked = true;
                    });
                }
                if (signals.financial && Array.isArray(signals.financial)) {
                    signals.financial.forEach(signal => {
                        const checkbox = document.querySelector(`input[name="financial_signals"][value="${signal}"]`);
                        if (checkbox) checkbox.checked = true;
                    });
                }
                if (signals.behavioral && Array.isArray(signals.behavioral)) {
                    signals.behavioral.forEach(signal => {
                        const checkbox = document.querySelector(`input[name="behavioral_signals"][value="${signal}"]`);
                        if (checkbox) checkbox.checked = true;
                    });
                }
                
                // Set max results from tool_config
                if (prospectSearchAgent.tool_config && prospectSearchAgent.tool_config.max_results) {
                    document.getElementById('maxResults').value = prospectSearchAgent.tool_config.max_results;
                }
            }
            
            // Set default scoring weights
            if (scoringAgent && scoringAgent.tool_config && scoringAgent.tool_config.early_adopter_score) {
                const weights = scoringAgent.tool_config.early_adopter_score.criteria_weights || {};
                
                if (weights.hiring !== undefined) {
                    const slider = document.getElementById('hiringWeight');
                    if (slider) {
                        slider.value = weights.hiring;
                        document.getElementById('hiringWeightValue').textContent = `${weights.hiring}%`;
                        slider.style.setProperty('--value', `${weights.hiring}%`);
                    }
                }
                if (weights.technology !== undefined) {
                    const slider = document.getElementById('technologyWeight');
                    if (slider) {
                        slider.value = weights.technology;
                        document.getElementById('technologyWeightValue').textContent = `${weights.technology}%`;
                        slider.style.setProperty('--value', `${weights.technology}%`);
                    }
                }
                if (weights.financial !== undefined) {
                    const slider = document.getElementById('financialWeight');
                    if (slider) {
                        slider.value = weights.financial;
                        document.getElementById('financialWeightValue').textContent = `${weights.financial}%`;
                        slider.style.setProperty('--value', `${weights.financial}%`);
                    }
                }
                if (weights.behavioral !== undefined) {
                    const slider = document.getElementById('behavioralWeight');
                    if (slider) {
                        slider.value = weights.behavioral;
                        document.getElementById('behavioralWeightValue').textContent = `${weights.behavioral}%`;
                        slider.style.setProperty('--value', `${weights.behavioral}%`);
                    }
                }
                
                // Update total weight display
                updateTotalWeight();
            }
        }
    } catch (error) {
        console.error('Error initializing ICP form:', error);
        // Form will use default HTML values if config fails to load
    }
}

// Collect Source Company data from form
function collectSourceCompanyData() {
    const companyName = document.getElementById('sourceCompanyName').value.trim();
    const companyDescription = document.getElementById('sourceCompanyDescription').value.trim();
    const valueProp = document.getElementById('sourceCompanyValueProp').value.trim();
    
    // Validate required fields
    if (!companyName || !companyDescription || !valueProp) {
        throw new Error('Please fill in all Source Company fields (Company Name, Description, and Value Proposition)');
    }
    
    return {
        name: companyName,
        description: companyDescription,
        value_proposition: valueProp
    };
}

// Collect ICP data from form
function collectICPFormData() {
    const industry = document.getElementById('icpIndustry').value;
    const location = document.getElementById('icpLocation').value;
    const employeeMin = parseInt(document.getElementById('icpEmployeeMin').value);
    const employeeMax = parseInt(document.getElementById('icpEmployeeMax').value);
    const revenueMin = parseInt(document.getElementById('icpRevenueMin').value);
    const revenueMax = parseInt(document.getElementById('icpRevenueMax').value);
    const maxResults = parseInt(document.getElementById('maxResults').value) || 5;
    
    // Validate required fields
    if (!industry || !location) {
        throw new Error('Please fill in all required fields (Industry and Location)');
    }
    
    // Validate ranges
    if (employeeMin >= employeeMax) {
        throw new Error('Employee count minimum must be less than maximum');
    }
    
    if (revenueMin >= revenueMax) {
        throw new Error('Revenue minimum must be less than maximum');
    }
    
    // Collect signals
    const signals = collectSignals();
    
    // Collect scoring weights
    const scoringWeights = collectScoringWeights();
    
    // Validate total weight equals 100%
    const totalWeight = scoringWeights.hiring + scoringWeights.technology + 
                       scoringWeights.financial + scoringWeights.behavioral;
    
    if (totalWeight !== 100) {
        throw new Error(`Scoring weights must total 100% (current: ${totalWeight}%)`);
    }
    
    return {
        industry,
        location,
        employee_count: {
            min: employeeMin,
            max: employeeMax
        },
        revenue: {
            min: revenueMin,
            max: revenueMax
        },
        max_results: maxResults,
        signals: signals,
        scoring_weights: scoringWeights
    };
}

// Setup Tag Inputs for Custom Signals
function setupTagInputs() {
    const tagInputs = [
        { inputId: 'customHiringSignals', containerId: 'hiringTags' },
        { inputId: 'customTechSignals', containerId: 'technologyTags' },
        { inputId: 'customFinancialSignals', containerId: 'financialTags' },
        { inputId: 'customBehavioralSignals', containerId: 'behavioralTags' }
    ];
    
    tagInputs.forEach(({ inputId, containerId }) => {
        const input = document.getElementById(inputId);
        const container = document.getElementById(containerId);
        
        if (input && container) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const value = input.value.trim();
                    
                    if (value) {
                        addTag(container, value);
                        input.value = '';
                    }
                }
            });
        }
    });
}

// Add a tag chip
function addTag(container, value) {
    const tag = document.createElement('div');
    tag.className = 'tag-chip';
    tag.innerHTML = `
        <span>${escapeHtml(value)}</span>
        <button type="button" class="tag-chip-remove" title="Remove">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Add remove handler
    tag.querySelector('.tag-chip-remove').addEventListener('click', () => {
        tag.style.animation = 'tagDisappear 0.2s ease-out';
        setTimeout(() => tag.remove(), 200);
    });
    
    container.appendChild(tag);
}

// Get all tags from a container
function getTagsFromContainer(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return [];
    
    const tags = [];
    container.querySelectorAll('.tag-chip span').forEach(span => {
        tags.push(span.textContent);
    });
    return tags;
}

// Collect Signals from Checkboxes and Tags
function collectSignals() {
    const signals = {
        hiring: [],
        technology: [],
        financial: [],
        behavioral: []
    };
    
    // Collect hiring signals
    document.querySelectorAll('input[name="hiring_signals"]:checked').forEach(checkbox => {
        signals.hiring.push(checkbox.value);
    });
    
    // Add custom hiring signals from tags
    const customHiringTags = getTagsFromContainer('hiringTags');
    signals.hiring.push(...customHiringTags);
    
    // Collect technology signals
    document.querySelectorAll('input[name="technology_signals"]:checked').forEach(checkbox => {
        signals.technology.push(checkbox.value);
    });
    
    // Add custom technology signals from tags
    const customTechTags = getTagsFromContainer('technologyTags');
    signals.technology.push(...customTechTags);
    
    // Collect financial signals
    document.querySelectorAll('input[name="financial_signals"]:checked').forEach(checkbox => {
        signals.financial.push(checkbox.value);
    });
    
    // Add custom financial signals from tags
    const customFinancialTags = getTagsFromContainer('financialTags');
    signals.financial.push(...customFinancialTags);
    
    // Collect behavioral signals
    document.querySelectorAll('input[name="behavioral_signals"]:checked').forEach(checkbox => {
        signals.behavioral.push(checkbox.value);
    });
    
    // Add custom behavioral signals from tags
    const customBehavioralTags = getTagsFromContainer('behavioralTags');
    signals.behavioral.push(...customBehavioralTags);
    
    return signals;
}

// Collect Scoring Weights
function collectScoringWeights() {
    return {
        hiring: parseInt(document.getElementById('hiringWeight')?.value || 20),
        technology: parseInt(document.getElementById('technologyWeight')?.value || 30),
        financial: parseInt(document.getElementById('financialWeight')?.value || 25),
        behavioral: parseInt(document.getElementById('behavioralWeight')?.value || 25)
    };
}

function formatRevenue(amount) {
    if (amount >= 1000000) {
        return `$${(amount / 1000000).toFixed(1)}M`;
    } else if (amount >= 1000) {
        return `$${(amount / 1000).toFixed(0)}K`;
    }
    return `$${amount}`;
}

function formatSignalName(signal) {
    return signal.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Start Run
async function startRun() {
    const btn = document.getElementById('confirmRunBtn');
    const originalText = btn.innerHTML;
    
    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        
        const workflowName = document.getElementById('workflowSelect').value;
        const campaignName = document.getElementById('campaignName').value || workflowName;
        const useOverrides = document.getElementById('useOverrides').checked;
        
        // Collect Source Company data
        let sourceCompanyData;
        try {
            sourceCompanyData = collectSourceCompanyData();
        } catch (validationError) {
            throw validationError;
        }
        
        // Collect ICP form data
        let icpData;
        try {
            icpData = collectICPFormData();
        } catch (validationError) {
            throw validationError;
        }
        
        // Build config overrides with ICP and Source Company data
        let configOverrides = {
            agents: {
                prospect_search: {
                    inputs: {
                        icp: {
                            industry: icpData.industry,
                            location: icpData.location,
                            employee_count: icpData.employee_count,
                            revenue: icpData.revenue
                        },
                        signals: icpData.signals
                    },
                    tool_config: {
                        max_results: icpData.max_results
                    }
                },
                scoring: {
                    tool_config: {
                        early_adopter_score: {
                            criteria_weights: icpData.scoring_weights
                        }
                    }
                },
                outreach_content: {
                    inputs: {
                        source_company: sourceCompanyData
                    }
                }
            }
        };
        
        // If user has custom overrides, merge them
        if (useOverrides) {
            try {
                const customOverrides = JSON.parse(document.getElementById('configOverrides').value);
                // Deep merge custom overrides with ICP overrides
                configOverrides = deepMerge(configOverrides, customOverrides);
            } catch (e) {
                throw new Error('Invalid JSON in custom overrides: ' + e.message);
            }
        }
        
        const response = await fetch(`${API_BASE}/api/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workflow_name: workflowName,
                campaign_name: campaignName,
                config_overrides: configOverrides
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to start run');
        }
        
        const data = await response.json();
        
        // Join run room for progress updates
        joinRunRoom(data.run_id);
        
        // Close modal and reload
        document.getElementById('startRunModal').classList.remove('active');
        showSuccess('Campaign started successfully!');
        loadDashboard();
        
    } catch (error) {
        showError(error.message || 'Failed to start campaign');
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Deep merge utility function
function deepMerge(target, source) {
    const output = Object.assign({}, target);
    if (isObject(target) && isObject(source)) {
        Object.keys(source).forEach(key => {
            if (isObject(source[key])) {
                if (!(key in target)) {
                    Object.assign(output, { [key]: source[key] });
                } else {
                    output[key] = deepMerge(target[key], source[key]);
                }
            } else {
                Object.assign(output, { [key]: source[key] });
            }
        });
    }
    return output;
}

function isObject(item) {
    return item && typeof item === 'object' && !Array.isArray(item);
}

// Utility Functions
function showError(message) {
    // Simple error notification
    showErrorDialog({
        title: 'Error',
        message: message
    });
}

function showSuccess(message) {
    // Simple success notification (can be enhanced with a toast library)
    alert(`Success: ${message}`);
}

// Show Error Dialog
function showErrorDialog(errorData) {
    const {
        title = 'Error',
        agent = 'Unknown',
        message = 'An error occurred',
        error = null,
        run_id = null
    } = errorData;
    
    // Create dialog HTML
    const dialogHTML = `
        <div id="errorDialog" class="error-dialog-overlay">
            <div class="error-dialog">
                <div class="error-dialog-header">
                    <h2>${title}</h2>
                    <button class="error-dialog-close" onclick="closeErrorDialog()">&times;</button>
                </div>
                <div class="error-dialog-body">
                    <div class="error-info">
                        <div class="error-field">
                            <strong>Agent:</strong>
                            <span class="error-value">${agent}</span>
                        </div>
                        ${run_id ? `
                        <div class="error-field">
                            <strong>Run ID:</strong>
                            <span class="error-value">${run_id}</span>
                        </div>
                        ` : ''}
                        <div class="error-field">
                            <strong>Error Message:</strong>
                            <div class="error-message">${escapeHtml(message)}</div>
                        </div>
                        ${error ? `
                        <div class="error-field">
                            <strong>Error Type:</strong>
                            <span class="error-value">${error.type || 'Unknown'}</span>
                        </div>
                        ${error.category ? `
                        <div class="error-field">
                            <strong>Category:</strong>
                            <span class="error-value error-category-${error.category}">${error.category}</span>
                        </div>
                        ` : ''}
                        ` : ''}
                    </div>
                    ${error && error.traceback ? `
                    <details class="error-details">
                        <summary>Stack Trace</summary>
                        <pre class="error-traceback">${escapeHtml(error.traceback)}</pre>
                    </details>
                    ` : ''}
                </div>
                <div class="error-dialog-footer">
                    <button class="btn btn-primary" onclick="closeErrorDialog()">Close</button>
                    ${run_id ? `
                    <button class="btn btn-secondary" onclick="viewRunDetails('${run_id}')">View Run Details</button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
    
    // Remove existing dialog if any
    const existingDialog = document.getElementById('errorDialog');
    if (existingDialog) {
        existingDialog.remove();
    }
    
    // Add dialog to body
    document.body.insertAdjacentHTML('beforeend', dialogHTML);
    
    // Auto-close on overlay click
    document.getElementById('errorDialog').addEventListener('click', (e) => {
        if (e.target.id === 'errorDialog') {
            closeErrorDialog();
        }
    });
}

// Close Error Dialog
function closeErrorDialog() {
    const dialog = document.getElementById('errorDialog');
    if (dialog) {
        dialog.remove();
    }
}

// View Run Details
function viewRunDetails(runId) {
    closeErrorDialog();
    window.location.href = `run-detail.html?id=${runId}`;
}

// Render Pagination
function renderPagination(totalPages) {
    const container = document.getElementById('runsPagination');
    if (!container) return;
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    const maxButtons = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }
    
    let html = '<div class="pagination-controls">';
    
    // Previous button
    html += `
        <button class="pagination-btn ${currentPage === 1 ? 'disabled' : ''}" 
                ${currentPage === 1 ? 'disabled' : ''} 
                onclick="loadRuns(${currentPage - 1})">
            <i class="fas fa-chevron-left"></i>
        </button>
    `;
    
    // First page
    if (startPage > 1) {
        html += `<button class="pagination-btn" onclick="loadRuns(1)">1</button>`;
        if (startPage > 2) {
            html += `<span class="pagination-ellipsis">...</span>`;
        }
    }
    
    // Page buttons
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <button class="pagination-btn ${i === currentPage ? 'active' : ''}" 
                    onclick="loadRuns(${i})">
                ${i}
            </button>
        `;
    }
    
    // Last page
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<span class="pagination-ellipsis">...</span>`;
        }
        html += `<button class="pagination-btn" onclick="loadRuns(${totalPages})">${totalPages}</button>`;
    }
    
    // Next button
    html += `
        <button class="pagination-btn ${currentPage === totalPages ? 'disabled' : ''}" 
                ${currentPage === totalPages ? 'disabled' : ''} 
                onclick="loadRuns(${currentPage + 1})">
            <i class="fas fa-chevron-right"></i>
        </button>
    `;
    
    html += '</div>';
    container.innerHTML = html;
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

