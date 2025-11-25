// Sequence Management JavaScript
const API_BASE = window.location.origin;

let selectedSequence = null;
let selectedContacts = [];
let allContacts = [];
let allSequences = [];
let filteredContacts = [];
let currentContactsPage = 1;
const contactsPerPage = 10;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSequences();
    loadAllContacts();
    setupEventListeners();
    setupTabs();
    setupAutomateTab();
});

// Setup Tabs
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Deactivate all tabs
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Activate clicked tab
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

// Setup Event Listeners
function setupEventListeners() {
    // Sequence search
    document.getElementById('sequenceSearch').addEventListener('input', (e) => {
        filterSequences(e.target.value);
    });
    
    // Contact search
    document.getElementById('contactSearch').addEventListener('input', (e) => {
        filterContacts(e.target.value);
    });
    
    // Select all checkbox
    document.getElementById('selectAllCheckbox').addEventListener('change', (e) => {
        toggleAllContacts(e.target.checked);
    });
    
    // Select/Deselect all buttons
    document.getElementById('selectAllBtn').addEventListener('click', () => {
        document.getElementById('selectAllCheckbox').checked = true;
        toggleAllContacts(true);
    });
    
    document.getElementById('deselectAllBtn').addEventListener('click', () => {
        document.getElementById('selectAllCheckbox').checked = false;
        toggleAllContacts(false);
    });
    
    // Add to sequence button
    document.getElementById('addToSequenceBtn').addEventListener('click', addContactsToSequence);
    
    // Refresh sequences button
    const refreshBtn = document.getElementById('refreshSequencesBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadSequences();
        });
    }
    
    // Automate tab event listeners
    const scoreConditionSelect = document.getElementById('scoreConditionSelect');
    if (scoreConditionSelect) {
        scoreConditionSelect.addEventListener('change', updateAutomatePreview);
    }
    
    const automateSequenceSelect = document.getElementById('automateSequenceSelect');
    if (automateSequenceSelect) {
        automateSequenceSelect.addEventListener('change', updateAutomateButtonState);
    }
    
    const previewContactsBtn = document.getElementById('previewContactsBtn');
    if (previewContactsBtn) {
        previewContactsBtn.addEventListener('click', previewAutomateContacts);
    }
    
    const automateAddBtn = document.getElementById('automateAddToSequenceBtn');
    if (automateAddBtn) {
        automateAddBtn.addEventListener('click', automateAddToSequence);
    }
}

// Load All Contacts
async function loadAllContacts() {
    try {
        const response = await fetch(`${API_BASE}/api/contacts/all-with-apollo-ids?limit=5000`);
        const data = await response.json();
        
        const rawContacts = data.contacts || [];
        
        // Deduplicate contacts based on apollo_contact_id and email
        allContacts = deduplicateContacts(rawContacts);
        
        console.log(`Loaded ${rawContacts.length} contacts, ${allContacts.length} unique contacts after deduplication`);
        
        if (rawContacts.length > allContacts.length) {
            console.log(`Removed ${rawContacts.length - allContacts.length} duplicate contacts`);
        }
        
        // Update automate preview after contacts are loaded
        updateAutomatePreview();
        
    } catch (error) {
        console.error('Failed to load contacts:', error);
        showError('Failed to load contacts from database');
    }
}

// Deduplicate Contacts
function deduplicateContacts(contacts) {
    const seen = new Map();
    const uniqueContacts = [];
    
    for (const contact of contacts) {
        // Create a unique key based on apollo_contact_id (primary) or email (fallback)
        const apolloId = contact.apollo_contact_id;
        const email = contact.contact_email?.toLowerCase().trim();
        
        // Skip contacts without apollo_contact_id or email
        if (!apolloId && !email) {
            console.warn('Skipping contact without ID or email:', contact.company_name);
            continue;
        }
        
        // Use apollo_contact_id as primary key
        const uniqueKey = apolloId || email;
        
        // Check if we've seen this contact before
        if (seen.has(uniqueKey)) {
            console.log(`Duplicate found: ${contact.company_name} (${email || apolloId})`);
            continue;
        }
        
        // Mark as seen and add to unique contacts
        seen.set(uniqueKey, true);
        uniqueContacts.push(contact);
    }
    
    return uniqueContacts;
}

// Setup Automate Tab
function setupAutomateTab() {
    // Initial update
    updateAutomatePreview();
}

// Populate Automate Sequence Dropdown
function populateAutomateSequenceDropdown() {
    const select = document.getElementById('automateSequenceSelect');
    if (!select) return;
    
    if (allSequences.length === 0) {
        select.innerHTML = '<option value="">No sequences found</option>';
        return;
    }
    
    select.innerHTML = '<option value="">Select a sequence...</option>' + 
        allSequences.map(seq => 
            `<option value="${escapeHtml(seq.id)}">${escapeHtml(seq.name)} (${seq.num_contacts || 0} contacts)</option>`
        ).join('');
}

// Update Automate Preview
function updateAutomatePreview() {
    const scoreCondition = parseInt(document.getElementById('scoreConditionSelect')?.value || 0);
    
    // Count total contacts
    const totalContacts = allContacts.length;
    
    // Count matching contacts
    const matchingContacts = allContacts.filter(contact => 
        (contact.score || 0) >= scoreCondition
    );
    
    // Update UI
    document.getElementById('totalContactsCount').textContent = totalContacts;
    document.getElementById('matchingContactsCount').textContent = matchingContacts.length;
    
    // Update button state
    updateAutomateButtonState();
}

// Update Automate Button State
function updateAutomateButtonState() {
    const sequenceId = document.getElementById('automateSequenceSelect')?.value;
    const scoreCondition = parseInt(document.getElementById('scoreConditionSelect')?.value || 0);
    const matchingContacts = allContacts.filter(contact => 
        (contact.score || 0) >= scoreCondition
    );
    
    const btn = document.getElementById('automateAddToSequenceBtn');
    if (btn) {
        btn.disabled = !sequenceId || matchingContacts.length === 0;
    }
}

// Preview Automate Contacts
function previewAutomateContacts() {
    const scoreCondition = parseInt(document.getElementById('scoreConditionSelect')?.value || 0);
    
    // Filter contacts by score - ONLY SHOW MATCHING CONTACTS
    const matchingContacts = allContacts.filter(contact => 
        (contact.score || 0) >= scoreCondition
    );
    
    if (matchingContacts.length === 0) {
        showError('No contacts match the selected score condition');
        return;
    }
    
    // IMPORTANT: Set filteredContacts to ONLY matching contacts
    // This ensures the table only shows contacts that meet the condition
    filteredContacts = matchingContacts;
    currentContactsPage = 1;
    
    // AUTOMATICALLY SELECT ALL MATCHING CONTACTS
    selectedContacts = matchingContacts.map(contact => ({
        apollo_contact_id: contact.apollo_contact_id,
        lead_id: contact.lead_id
    }));
    
    // Render ONLY the filtered contacts
    renderContactsPage(1);
    
    // Wait for DOM to update, then check all checkboxes
    setTimeout(() => {
        document.querySelectorAll('.contact-checkbox').forEach(checkbox => {
            checkbox.checked = true;
        });
        document.getElementById('selectAllCheckbox').checked = true;
        updateSelectedContacts();
    }, 100);
    
    // Show the contacts card
    document.getElementById('contactSelectCard').style.display = 'block';
    
    // Scroll to it
    document.getElementById('contactSelectCard').scrollIntoView({behavior: 'smooth', block: 'start'});
    
    showSuccess(`Showing ${matchingContacts.length} contacts with score ≥ ${scoreCondition} (all selected)`);
}

// Automate Add to Sequence
async function automateAddToSequence() {
    const sequenceId = document.getElementById('automateSequenceSelect')?.value;
    const scoreCondition = parseInt(document.getElementById('scoreConditionSelect')?.value || 0);
    
    if (!sequenceId) {
        showError('Please select a sequence');
        return;
    }
    
    // Filter contacts by score
    const matchingContacts = allContacts.filter(contact => 
        (contact.score || 0) >= scoreCondition
    );
    
    if (matchingContacts.length === 0) {
        showError('No contacts match the selected score condition');
        return;
    }
    
    // Find the selected sequence
    const sequence = allSequences.find(s => s.id === sequenceId);
    if (!sequence) {
        showError('Selected sequence not found');
        return;
    }
    
    const btn = document.getElementById('automateAddToSequenceBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding Contacts...';
    
    try {
        const contactIds = matchingContacts.map(c => c.apollo_contact_id);
        
        const response = await fetch(`${API_BASE}/api/sequences/${sequenceId}/add-contacts`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                contact_ids: contactIds,
                settings: {
                    allow_active_in_other: false,
                    allow_finished_in_other: false
                }
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Show results
            document.getElementById('resultsCard').style.display = 'block';
            document.getElementById('resultsContent').innerHTML = `
                <div class="success-box">
                    <h3><i class="fas fa-check-circle"></i> Automation Complete!</h3>
                    <p class="automation-summary">
                        <i class="fas fa-magic"></i>
                        Automatically added contacts with score ≥ ${scoreCondition} to sequence
                    </p>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${result.added_count || 0}</div>
                            <div class="stat-label">Added</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${result.failed_count || 0}</div>
                            <div class="stat-label">Failed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${matchingContacts.length}</div>
                            <div class="stat-label">Total Processed</div>
                        </div>
                    </div>
                    <p><strong>Sequence:</strong> ${escapeHtml(result.sequence_name || sequence.name)}</p>
                    <p><strong>Score Condition:</strong> ≥ ${scoreCondition}</p>
                    <a href="https://app.apollo.io/#/sequences/${encodeURIComponent(result.sequence_id)}" target="_blank" class="btn btn-primary" rel="noopener noreferrer">
                        <i class="fas fa-external-link-alt"></i>
                        <span>View in Apollo</span>
                    </a>
                </div>
            `;
            
            // Scroll to results
            document.getElementById('resultsCard').scrollIntoView({behavior: 'smooth'});
            
            showSuccess(`Successfully added ${result.added_count} contacts to sequence!`);
            
        } else {
            throw new Error(result.error || 'Failed to add contacts');
        }
        
    } catch (error) {
        showError('Failed to add contacts to sequence: ' + error.message);
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-magic"></i> Add Matching Contacts to Sequence';
    }
}

// Load Sequences
async function loadSequences() {
    const container = document.getElementById('sequencesList');
    container.innerHTML = `
        <p class="loading-state">
            <i class="fas fa-spinner fa-spin"></i>
            Loading sequences...
        </p>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/api/sequences/search`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({per_page: 100})
        });
        
        const data = await response.json();
        allSequences = data.sequences || [];
        
        renderSequences(allSequences);
        populateAutomateSequenceDropdown();
        
    } catch (error) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load sequences. Check your Apollo API key.</p>
            </div>
        `;
        console.error(error);
    }
}

// Render Sequences
function renderSequences(sequences) {
    const container = document.getElementById('sequencesList');
    
    if (sequences.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>No sequences found. Create one in Apollo first or enter ID manually above.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = '';
    sequences.forEach(seq => {
        const card = document.createElement('div');
        card.className = 'sequence-card';
        if (selectedSequence && selectedSequence.id === seq.id) {
            card.classList.add('selected');
        }
        
        // Determine status badge
        const statusClass = seq.active ? 'status-completed' : 'status-pending';
        const statusText = seq.active ? 'Active' : 'Inactive';
        
        card.innerHTML = `
            <div class="sequence-header">
                <h4>${escapeHtml(seq.name)}</h4>
                <span class="status-badge ${statusClass}">${statusText}</span>
            </div>
            <div class="sequence-stats">
                <div class="stat-item">
                    <i class="fas fa-users"></i>
                    <span>${seq.num_contacts || 0} contacts</span>
                </div>
                <div class="stat-item">
                    <i class="fas fa-tasks"></i>
                    <span>${seq.num_steps || 0} steps</span>
                </div>
            </div>
            <div class="sequence-id">
                <small>ID: ${escapeHtml(seq.id)}</small>
            </div>
            <button class="btn btn-primary btn-sm select-sequence-btn" data-sequence-id="${escapeHtml(seq.id)}">
                Select Sequence
            </button>
        `;
        
        card.querySelector('.select-sequence-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            selectSequence(seq);
        });
        
        // Allow clicking card to select
        card.addEventListener('click', () => {
            selectSequence(seq);
        });
        
        container.appendChild(card);
    });
}

// Filter Sequences
function filterSequences(searchTerm) {
    const filtered = allSequences.filter(seq => 
        seq.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        seq.id.toLowerCase().includes(searchTerm.toLowerCase())
    );
    renderSequences(filtered);
}

// Select Sequence (for Search Sequences tab)
function selectSequence(sequence) {
    selectedSequence = sequence;
    
    // Update UI
    document.querySelectorAll('.sequence-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Show contact selection
    document.getElementById('contactSelectCard').style.display = 'block';
    
    // Reset pagination and show ALL contacts (for manual selection)
    currentContactsPage = 1;
    filteredContacts = allContacts;
    selectedContacts = []; // Clear selection
    
    // Load contacts
    renderContactsPage(1);
    
    // Scroll to contacts
    document.getElementById('contactSelectCard').scrollIntoView({behavior: 'smooth', block: 'start'});
    
    showSuccess(`Selected sequence: ${sequence.name}`);
}

// Render Contacts Page
function renderContactsPage(page) {
    currentContactsPage = page;
    const tbody = document.getElementById('contactsTableBody');
    
    if (filteredContacts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state-cell">
                    <i class="fas fa-inbox"></i>
                    <p>No contacts with Apollo IDs found. Run a campaign first!</p>
                </td>
            </tr>
        `;
        document.getElementById('contactsPagination').innerHTML = '';
        return;
    }
    
    // Calculate pagination
    const startIdx = (page - 1) * contactsPerPage;
    const endIdx = startIdx + contactsPerPage;
    const pageContacts = filteredContacts.slice(startIdx, endIdx);
    
    tbody.innerHTML = pageContacts.map(contact => {
        // Check if this contact is already selected
        const isSelected = selectedContacts.some(sc => 
            sc.apollo_contact_id === contact.apollo_contact_id
        );
        return `
            <tr>
                <td class="checkbox-col">
                    <input type="checkbox" class="contact-checkbox" 
                           data-contact-id="${escapeHtml(contact.apollo_contact_id)}" 
                           data-lead-id="${escapeHtml(contact.lead_id)}"
                           ${isSelected ? 'checked' : ''}>
                </td>
                <td><strong>${escapeHtml(contact.company_name || '-')}</strong></td>
                <td>${escapeHtml(contact.contact_name || '-')}</td>
                <td>${escapeHtml(contact.contact_email || '-')}</td>
                <td>${escapeHtml(contact.contact_title || '-')}</td>
                <td>
                    <span class="status-badge status-completed">
                        ${contact.score ? contact.score.toFixed(1) : '-'}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
    
    // Add event listeners to checkboxes
    tbody.querySelectorAll('.contact-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedContacts);
    });
    
    // Update selected contacts count
    updateSelectedContacts();
    
    // Render pagination
    const totalPages = Math.ceil(filteredContacts.length / contactsPerPage);
    renderContactsPagination(totalPages);
}

// Render Contacts (for backward compatibility)
function renderContacts(contacts) {
    filteredContacts = contacts;
    currentContactsPage = 1;
    renderContactsPage(1);
}

// Filter Contacts (for search box)
function filterContacts(searchTerm) {
    const term = searchTerm.toLowerCase();
    
    // Apply search filter on top of current filteredContacts
    // This preserves any score-based filtering from automation
    const baseContacts = filteredContacts.length > 0 ? filteredContacts : allContacts;
    
    if (!term) {
        // If search is empty, restore to base contacts
        // Don't reset to allContacts if we're in automation mode
        currentContactsPage = 1;
        renderContactsPage(1);
        return;
    }
    
    const searchFiltered = baseContacts.filter(contact => 
        (contact.company_name || '').toLowerCase().includes(term) ||
        (contact.contact_name || '').toLowerCase().includes(term) ||
        (contact.contact_email || '').toLowerCase().includes(term) ||
        (contact.contact_title || '').toLowerCase().includes(term)
    );
    
    // Temporarily update for search
    const previousFiltered = filteredContacts;
    filteredContacts = searchFiltered;
    currentContactsPage = 1;
    renderContactsPage(1);
    
    // If search is cleared, restore previous filter
    if (!term) {
        filteredContacts = previousFiltered;
    }
}

// Toggle All Contacts
function toggleAllContacts(checked) {
    document.querySelectorAll('.contact-checkbox').forEach(checkbox => {
        checkbox.checked = checked;
    });
    updateSelectedContacts();
}

// Update Selected Contacts
function updateSelectedContacts() {
    // Get all contacts from all pages
    const allCheckboxes = document.querySelectorAll('.contact-checkbox');
    
    // Update selectedContacts based on current page checkboxes
    allCheckboxes.forEach(checkbox => {
        const contactId = checkbox.dataset.contactId;
        const leadId = checkbox.dataset.leadId;
        const existingIndex = selectedContacts.findIndex(sc => sc.apollo_contact_id === contactId);
        
        if (checkbox.checked && existingIndex === -1) {
            // Add to selected
            selectedContacts.push({
                apollo_contact_id: contactId,
                lead_id: leadId
            });
        } else if (!checkbox.checked && existingIndex !== -1) {
            // Remove from selected
            selectedContacts.splice(existingIndex, 1);
        }
    });
    
    // Update counts
    const count = selectedContacts.length;
    document.getElementById('selectedCountBadge').textContent = `${count} selected`;
    const selectedCountEl = document.getElementById('selectedContactCount');
    if (selectedCountEl) {
        selectedCountEl.textContent = count;
    }
    
    // Enable/disable button
    document.getElementById('addToSequenceBtn').disabled = count === 0;
    
    // Update select all checkbox for current page
    const totalCheckboxes = allCheckboxes.length;
    const checkedCheckboxes = document.querySelectorAll('.contact-checkbox:checked').length;
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = totalCheckboxes > 0 && checkedCheckboxes === totalCheckboxes;
    }
}

// Add Contacts to Sequence
async function addContactsToSequence() {
    if (!selectedSequence || selectedContacts.length === 0) {
        showError('Please select a sequence and at least one contact');
        return;
    }
    
    const btn = document.getElementById('addToSequenceBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    
    try {
        const contactIds = selectedContacts.map(c => c.apollo_contact_id);
        
        // Get settings if checkboxes exist, otherwise use defaults
        const allowActiveInOther = document.getElementById('allowActiveInOther');
        const allowFinishedInOther = document.getElementById('allowFinishedInOther');
        
        const response = await fetch(`${API_BASE}/api/sequences/${selectedSequence.id}/add-contacts`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                contact_ids: contactIds,
                settings: {
                    allow_active_in_other: allowActiveInOther ? allowActiveInOther.checked : false,
                    allow_finished_in_other: allowFinishedInOther ? allowFinishedInOther.checked : false
                }
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Show results
            document.getElementById('resultsCard').style.display = 'block';
            document.getElementById('resultsContent').innerHTML = `
                <div class="success-box">
                    <h3><i class="fas fa-check-circle"></i> Successfully Added to Sequence!</h3>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${result.added_count || 0}</div>
                            <div class="stat-label">Added</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${result.failed_count || 0}</div>
                            <div class="stat-label">Failed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${result.total_contacts || 0}</div>
                            <div class="stat-label">Total</div>
                        </div>
                    </div>
                    <p><strong>Sequence:</strong> ${escapeHtml(result.sequence_name || selectedSequence.name)}</p>
                    <p><strong>Sequence ID:</strong> <code>${escapeHtml(result.sequence_id)}</code></p>
                    <a href="https://app.apollo.io/#/sequences/${encodeURIComponent(result.sequence_id)}" target="_blank" class="btn btn-primary" rel="noopener noreferrer">
                        <i class="fas fa-external-link-alt"></i>
                        <span>View in Apollo</span>
                    </a>
                </div>
            `;
            
            // Scroll to results
            document.getElementById('resultsCard').scrollIntoView({behavior: 'smooth'});
            
            showSuccess(`Added ${result.added_count} contacts to sequence!`);
            
            // Reset selection
            selectedContacts = [];
            document.querySelectorAll('.contact-checkbox').forEach(cb => cb.checked = false);
            updateSelectedContacts();
            
        } else {
            throw new Error(result.error || 'Failed to add contacts');
        }
        
    } catch (error) {
        showError('Failed to add contacts to sequence: ' + error.message);
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus-circle"></i> Add to Sequence';
    }
}

// Render Contacts Pagination
function renderContactsPagination(totalPages) {
    const container = document.getElementById('contactsPagination');
    if (!container) return;
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    const maxButtons = 5;
    let startPage = Math.max(1, currentContactsPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }
    
    let html = '<div class="pagination-controls">';
    
    // Previous button
    html += `
        <button class="pagination-btn ${currentContactsPage === 1 ? 'disabled' : ''}" 
                ${currentContactsPage === 1 ? 'disabled' : ''} 
                onclick="renderContactsPage(${currentContactsPage - 1})">
            <i class="fas fa-chevron-left"></i>
        </button>
    `;
    
    // First page
    if (startPage > 1) {
        html += `<button class="pagination-btn" onclick="renderContactsPage(1)">1</button>`;
        if (startPage > 2) {
            html += `<span class="pagination-ellipsis">...</span>`;
        }
    }
    
    // Page buttons
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <button class="pagination-btn ${i === currentContactsPage ? 'active' : ''}" 
                    onclick="renderContactsPage(${i})">
                ${i}
            </button>
        `;
    }
    
    // Last page
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<span class="pagination-ellipsis">...</span>`;
        }
        html += `<button class="pagination-btn" onclick="renderContactsPage(${totalPages})">${totalPages}</button>`;
    }
    
    // Next button
    html += `
        <button class="pagination-btn ${currentContactsPage === totalPages ? 'disabled' : ''}" 
                ${currentContactsPage === totalPages ? 'disabled' : ''} 
                onclick="renderContactsPage(${currentContactsPage + 1})">
            <i class="fas fa-chevron-right"></i>
        </button>
    `;
    
    html += '</div>';
    container.innerHTML = html;
}

// Utility Functions
function showError(message) {
    // Create a styled notification instead of alert
    const notification = document.createElement('div');
    notification.className = 'notification notification-error';
    notification.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${escapeHtml(message)}</span>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

function showSuccess(message) {
    // Create a styled notification instead of alert
    const notification = document.createElement('div');
    notification.className = 'notification notification-success';
    notification.innerHTML = `
        <i class="fas fa-check-circle"></i>
        <span>${escapeHtml(message)}</span>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}
