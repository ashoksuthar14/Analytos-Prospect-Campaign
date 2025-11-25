// Configuration Page JavaScript
const API_BASE = window.location.origin;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    setupEventListeners();
});

// Load Configuration
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const data = await response.json();
        
        document.getElementById('configDisplay').textContent = 
            JSON.stringify(data, null, 2);
    } catch (error) {
        document.getElementById('configDisplay').textContent = 
            'Error loading configuration';
        console.error(error);
    }
}

// Event Listeners
function setupEventListeners() {
    // Refresh Button
    document.getElementById('refreshConfigBtn').addEventListener('click', () => {
        loadConfig();
    });
    
    // Copy Button
    document.getElementById('copyConfigBtn').addEventListener('click', () => {
        const configText = document.getElementById('configDisplay').textContent;
        navigator.clipboard.writeText(configText).then(() => {
            showSuccess('Configuration copied to clipboard!');
        }).catch(err => {
            showError('Failed to copy configuration');
        });
    });
}

// Utility Functions
function showError(message) {
    alert(`Error: ${message}`);
}

function showSuccess(message) {
    alert(`Success: ${message}`);
}

