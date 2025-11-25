// Feedback Page JavaScript
const API_BASE = window.location.origin;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadRecommendations();
    setupEventListeners();
});

// Load Recommendations
async function loadRecommendations() {
    try {
        const response = await fetch(`${API_BASE}/api/feedback/pending`);
        const data = await response.json();
        
        renderRecommendations(data.recommendations || []);
        document.getElementById('pendingCount').textContent = data.recommendations.length;
    } catch (error) {
        document.getElementById('recommendationsList').innerHTML = 
            '<div class="loading">Error loading recommendations</div>';
        console.error(error);
    }
}

// Render Recommendations
function renderRecommendations(recommendations) {
    const container = document.getElementById('recommendationsList');
    
    if (recommendations.length === 0) {
        container.innerHTML = '<div class="empty-state">No pending recommendations</div>';
        return;
    }
    
    container.innerHTML = recommendations.map(rec => {
        const oldValue = typeof rec.old_value === 'string' ? 
            JSON.parse(rec.old_value) : rec.old_value;
        const newValue = typeof rec.new_value === 'string' ? 
            JSON.parse(rec.new_value) : rec.new_value;
        
        return `
            <div class="recommendation-card">
                <div class="recommendation-header">
                    <div class="recommendation-field">${rec.field}</div>
                </div>
                <div class="recommendation-body">
                    <div class="recommendation-reason">
                        <i class="fas fa-lightbulb"></i> ${rec.reason}
                    </div>
                    <div class="recommendation-values">
                        <div class="value-item">
                            <label>Current Value</label>
                            <div class="value">${formatValue(oldValue)}</div>
                        </div>
                        <div class="value-item highlight">
                            <label>Proposed Value</label>
                            <div class="value">${formatValue(newValue)}</div>
                        </div>
                    </div>
                </div>
                <div class="recommendation-actions">
                    <button class="btn btn-secondary" onclick="viewRecommendation('${rec.rec_id}')">
                        <i class="fas fa-eye"></i> View Details
                    </button>
                    <button class="btn btn-primary" onclick="approveRecommendation('${rec.rec_id}')">
                        <i class="fas fa-check"></i> Approve
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// Format Value for Display
function formatValue(value) {
    if (typeof value === 'object') {
        return JSON.stringify(value, null, 2);
    }
    return String(value);
}

// View Recommendation Details
async function viewRecommendation(recId) {
    try {
        const response = await fetch(`${API_BASE}/api/feedback/pending`);
        const data = await response.json();
        const rec = data.recommendations.find(r => r.rec_id === recId);
        
        if (!rec) {
            showError('Recommendation not found');
            return;
        }
        
        const oldValue = typeof rec.old_value === 'string' ? 
            JSON.parse(rec.old_value) : rec.old_value;
        const newValue = typeof rec.new_value === 'string' ? 
            JSON.parse(rec.new_value) : rec.new_value;
        
        document.getElementById('detailField').textContent = rec.field;
        document.getElementById('detailOldValue').textContent = formatValue(oldValue);
        document.getElementById('detailNewValue').textContent = formatValue(newValue);
        document.getElementById('detailReason').textContent = rec.reason;
        
        // Store rec_id for approval
        document.getElementById('confirmApprovalBtn').dataset.recId = recId;
        
        document.getElementById('recommendationModal').classList.add('active');
    } catch (error) {
        showError('Failed to load recommendation details');
        console.error(error);
    }
}

// Approve Recommendation
async function approveRecommendation(recId) {
    if (!confirm('Are you sure you want to approve this recommendation? It will update the workflow configuration.')) {
        return;
    }
    
    const btn = document.getElementById('confirmApprovalBtn');
    const originalText = btn.innerHTML;
    
    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Approving...';
        
        const response = await fetch(`${API_BASE}/api/feedback/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rec_id: recId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to approve recommendation');
        }
        
        showSuccess('Recommendation approved successfully!');
        document.getElementById('recommendationModal').classList.remove('active');
        loadRecommendations();
        
    } catch (error) {
        showError(error.message || 'Failed to approve recommendation');
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Event Listeners
function setupEventListeners() {
    // Refresh Button
    document.getElementById('refreshFeedbackBtn').addEventListener('click', () => {
        loadRecommendations();
    });
    
    // Modal Close
    document.getElementById('closeRecModal').addEventListener('click', () => {
        document.getElementById('recommendationModal').classList.remove('active');
    });
    
    document.getElementById('cancelApprovalBtn').addEventListener('click', () => {
        document.getElementById('recommendationModal').classList.remove('active');
    });
    
    // Confirm Approval
    document.getElementById('confirmApprovalBtn').addEventListener('click', () => {
        const recId = document.getElementById('confirmApprovalBtn').dataset.recId;
        if (recId) {
            approveRecommendation(recId);
        }
    });
    
    // Close modal on outside click
    document.getElementById('recommendationModal').addEventListener('click', (e) => {
        if (e.target.id === 'recommendationModal') {
            document.getElementById('recommendationModal').classList.remove('active');
        }
    });
}

// Utility Functions
function showError(message) {
    alert(`Error: ${message}`);
}

function showSuccess(message) {
    alert(`Success: ${message}`);
}

