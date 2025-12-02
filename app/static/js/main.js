// static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initializeFileUpload();
    initializeToggleButtons();
    initializeProcessing();
    initializeHighlightingSystem();
    
    // Initialize Feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
});

// Global state for current processing session
let currentSession = {
    features: null,
    highlightedText: null,
    originalText: null,
    trials: null,
    processingTime: null
};

// Configuration
const CONFIG = {
    maxFileSize: 16 * 1024 * 1024, // 16MB
    allowedFileTypes: ['application/pdf'],
    apiEndpoints: {
        process: '/api/process',
        trials: '/api/trials',
        validate: '/api/validate-features',
        health: '/api/health'
    }
};

function initializeFileUpload() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');
    
    if (!dropzone || !fileInput) return;

    // Dropzone click handler
    dropzone.addEventListener('click', () => {
        fileInput.click();
    });

    // Drag and drop handlers
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    // File input change handler
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });
}

function handleFileSelection(file) {
    // Validate file
    const validation = validateFile(file);
    if (!validation.valid) {
        showAlert('error', validation.error);
        return;
    }

    // Update UI to show selected file
    const dropzone = document.getElementById('dropzone');
    const dropzoneMessage = dropzone.querySelector('.dropzone-message');
    const dropzoneDescription = dropzone.querySelector('.dropzone-description');
    
    dropzoneMessage.textContent = `Selected: ${file.name}`;
    dropzoneDescription.textContent = `${formatFileSize(file.size)} - Ready to process`;
    
    // Store file reference
    currentSession.selectedFile = file;
    
    // Clear previous results
    clearResults();
}

function validateFile(file) {
    if (!file) {
        return { valid: false, error: 'No file selected' };
    }

    if (!CONFIG.allowedFileTypes.includes(file.type)) {
        return { valid: false, error: 'Please select a PDF file' };
    }

    if (file.size > CONFIG.maxFileSize) {
        return { 
            valid: false, 
            error: `File too large. Maximum size: ${formatFileSize(CONFIG.maxFileSize)}` 
        };
    }

    if (file.size === 0) {
        return { valid: false, error: 'File is empty' };
    }

    return { valid: true };
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function initializeToggleButtons() {
    const fileToggle = document.getElementById('file-input-toggle');
    const textToggle = document.getElementById('text-input-toggle');
    const fileSection = document.getElementById('file-input-section');
    const textSection = document.getElementById('text-input-section');

    if (!fileToggle || !textToggle || !fileSection || !textSection) return;

    fileToggle.addEventListener('click', () => {
        setActiveInputMethod('file');
    });

    textToggle.addEventListener('click', () => {
        setActiveInputMethod('text');
    });
}

function setActiveInputMethod(method) {
    const fileToggle = document.getElementById('file-input-toggle');
    const textToggle = document.getElementById('text-input-toggle');
    const fileSection = document.getElementById('file-input-section');
    const textSection = document.getElementById('text-input-section');

    // Update button states
    if (method === 'file') {
        fileToggle.classList.add('active', 'btn-primary');
        fileToggle.classList.remove('btn-outline-primary');
        textToggle.classList.remove('active', 'btn-primary');
        textToggle.classList.add('btn-outline-primary');
        
        fileSection.classList.remove('d-none');
        textSection.classList.add('d-none');
    } else {
        textToggle.classList.add('active', 'btn-primary');
        textToggle.classList.remove('btn-outline-primary');
        fileToggle.classList.remove('active', 'btn-primary');
        fileToggle.classList.add('btn-outline-primary');
        
        textSection.classList.remove('d-none');
        fileSection.classList.add('d-none');
    }

    currentSession.inputMethod = method;
    clearResults();
}

function initializeProcessing() {
    const processButton = document.getElementById('process-button');
    const clearButton = document.getElementById('clear-button');

    if (processButton) {
        processButton.addEventListener('click', processPatientData);
    }

    if (clearButton) {
        clearButton.addEventListener('click', clearAll);
    }
}

async function processPatientData() {
    try {
        showLoadingSpinner(true);
        
        const formData = new FormData();
        
        // Check for file
        const fileInput = document.getElementById('file-input');
        const textInput = document.getElementById('text-input');
        
        if (fileInput.files[0]) {
            formData.append('file', fileInput.files[0]);
            console.log('Uploading file:', fileInput.files[0].name);
        } else if (textInput.value.trim()) {
            formData.append('text_content', textInput.value.trim());
            console.log('Processing text input');
        } else {
            throw new Error('Please select a file or enter text');
        }

        // Call the correct endpoint
        const response = await fetch('/api/process', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Processing failed');
        }

        // Display results
        displayResults(result);
        
    } catch (error) {
        console.error('Processing error:', error);
        showAlert('error', error.message);
    } finally {
        showLoadingSpinner(false);
    }
}

function displayEnhancedResults(result) {
    // Show results section
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.classList.remove('d-none');
    }

    // Display clean features (without source text)
    displayCleanFeatures(result.features);
    
    // Display highlighted text with evidence
    displayHighlightedText(result.highlighted_text);
    
    // Display matched trials
    displayMatchedTrials(result.matched_trials);
    
    // Update processing metadata
    displayProcessingMetadata(result.processing_metadata);
}

function displayCleanFeatures(features) {
    const container = document.getElementById('features-container');
    if (!container) return;

    container.innerHTML = '';

    // Create feature display groups
    const featureGroups = {
        'Demographics': ['age', 'gender'],
        'Disease Characteristics': ['histology', 'current_stage'],
        'Performance Status': ['ecog_ps'],
        'Molecular Markers': ['biomarkers', 'pd_l1_tps'],
        'Disease Extent': ['brain_metastasis'],
        'Concomitant / Supportive Meds': ['line_of_therapy', 'concomitant_treatments'],
        'Treatment History': ['prior_systemic_therapies'],
        'Comorbidities': ['comorbidities'],
        'Vaccines & Drugs': ['vaccines_and_drugs']  
    };

    for (const [groupName, groupFeatures] of Object.entries(featureGroups)) {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'feature-group mb-3';
        
        const groupHeader = document.createElement('h6');
        groupHeader.className = 'feature-group-header text-primary';
        groupHeader.textContent = groupName;
        groupDiv.appendChild(groupHeader);

        const groupContent = document.createElement('div');
        groupContent.className = 'feature-group-content';

        let hasContent = false;
        for (const featureKey of groupFeatures) {
            if (features.hasOwnProperty(featureKey)) {
                const featureValue = features[featureKey];
                if (featureValue !== null && featureValue !== 'not mentioned' && 
                    !((Array.isArray(featureValue) && (featureValue.length === 0 || featureValue.includes('not mentioned'))))) {
                    
                    const featureItem = createFeatureDisplayItem(featureKey, featureValue);
                    groupContent.appendChild(featureItem);
                    hasContent = true;
                }
            }
        }

        if (hasContent) {
            groupDiv.appendChild(groupContent);
            container.appendChild(groupDiv);
        }
    }
}

function createFeatureDisplayItem(key, value) {
    const item = document.createElement('div');
    item.className = 'feature-item';
    
    const label = document.createElement('span');
    label.className = 'feature-label';
    label.textContent = formatFeatureLabel(key);
    
    const valueSpan = document.createElement('span');
    valueSpan.className = 'feature-value';
    valueSpan.textContent = formatFeatureValue(value);
    
    item.appendChild(label);
    item.appendChild(valueSpan);
    
    return item;
}

function formatFeatureLabel(key) {
    const labels = {
        'age': 'Age',
        'gender': 'Gender', 
        'histology': 'Histology',
        'stage_at_diagnosis': 'Stage at Diagnosis',
        'current_stage': 'Current Stage',
        'ecog_ps': 'ECOG Performance Status',
        'line_of_therapy': 'Line of Therapy',
        'mutations': 'Genetic Mutations',
        'pd_l1_tps': 'PD-L1 Expression',
        'biomarkers': 'Biomarkers',
        'brain_metastasis': 'Brain Metastasis',
        'prior_systemic_therapies': 'Prior Systemic Therapies',
        'organ_function_and_labs': 'Organ Function & Labs',
        'comorbidities_and_status': 'Comorbidities & Status',
        'vaccines_and_drugs': 'Vaccines & Drugs',
    };
    return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatFeatureValue(value) {
    if (Array.isArray(value)) {
        return value.filter(v => v !== 'not mentioned').join(', ') || 'Not mentioned';
    }
    if (typeof value === 'object' && value !== null) {
        return JSON.stringify(value, null, 2);
    }
    return String(value);
}

function displayHighlightedText(highlightedText) {
    const evidenceContainer = document.getElementById('evidence');
    const plainTextContainer = document.getElementById('plain-text');
    
    if (evidenceContainer && highlightedText) {
        evidenceContainer.innerHTML = highlightedText;
        
        // Store original text for toggle functionality
        if (plainTextContainer) {
            plainTextContainer.textContent = stripHtmlTags(highlightedText);
        }
        
        // Initialize highlight toggle functionality
        initializeHighlightToggle();
    }
}


function stripHtmlTags(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return doc.body.textContent || '';
}

function displayResults(result) {
  console.log('Displaying results:', result);

  const resultsSection = document.getElementById('results-section');
  if (resultsSection) resultsSection.classList.remove('d-none');

  // left column is gone; we still show features & trials
  displayCleanFeatures(result.features);
  displayMatchedTrials(result.matched_trials);

  // Inline annotated PDF (preferred) or fallback to highlighted text if no PDF
  wireAnnotatedPdfUI(result.annotated_pdf_url, result.highlighted_text);

  displayProcessingMetadata(result.processing_metadata);

  if (typeof feather !== 'undefined') feather.replace();
}


function displayFeatures(features) {
    const container = document.getElementById('features-container');
    if (!container) return;

    container.innerHTML = '';
    
    for (const [key, value] of Object.entries(features)) {
        // Skip empty/null values
        if (value !== null && value !== 'not mentioned' && value !== [] && 
            !((Array.isArray(value) && (value.length === 0 || value.includes('not mentioned'))))) {
            
            const featureDiv = document.createElement('div');
            featureDiv.className = 'feature-item';
            
            const label = document.createElement('span');
            label.className = 'feature-label';
            label.textContent = formatFeatureLabel(key);
            
            const valueSpan = document.createElement('span');
            valueSpan.className = 'feature-value';
            valueSpan.textContent = formatFeatureValue(value);
            
            featureDiv.appendChild(label);
            featureDiv.appendChild(valueSpan);
            container.appendChild(featureDiv);
        }
    }
}

function displayHighlightedText(highlightedText) {
  const evidenceContainer = document.getElementById('evidence');
  if (evidenceContainer && highlightedText) {
    evidenceContainer.innerHTML = highlightedText;
  }
}

function wirePdfButtons(pdfUrl) {
  const btnAnnotated = document.getElementById('btn-annotated-pdf');
  const btnDownload  = document.getElementById('btn-download-pdf');

  if (btnAnnotated && btnDownload) {
    if (pdfUrl) {
      btnAnnotated.classList.remove('d-none');
      btnDownload.classList.remove('d-none');

      btnAnnotated.href = pdfUrl;  // apre in nuova tab
      btnDownload.href  = pdfUrl;  // forza download grazie all’attributo 'download' in HTML
    } else {
      // Nessun PDF annotato: nascondi i bottoni
      btnAnnotated.classList.add('d-none');
      btnDownload.classList.add('d-none');
    }
  }
}

function wireAnnotatedPdfUI(pdfUrl, highlightedText) {
  const frame = document.getElementById('annotated-pdf-frame');
  const openBtn = document.getElementById('btn-annotated-pdf');
  const dlBtn   = document.getElementById('btn-download-pdf');

  if (pdfUrl) {
    if (frame) frame.src = pdfUrl;
    if (openBtn) {
      openBtn.href = pdfUrl;
      openBtn.classList.remove('d-none');
    }
    if (dlBtn) {
      dlBtn.href = pdfUrl;
      dlBtn.classList.remove('d-none');
    }
  } else {
    // No annotated PDF available: keep buttons hidden and (optionally) show highlighted text
    if (frame) frame.removeAttribute('src');

    // If you still want a textual fallback, uncomment this:
    // const evidence = document.getElementById('evidence');
    // if (evidence && highlightedText) {
    //   evidence.classList.remove('d-none');
    //   evidence.innerHTML = highlightedText;
    // }
  }
}


function displayMatchedTrials(trials) {
    const container = document.getElementById('matches-container');
    if (!container) return;

    container.innerHTML = '';

    if (!trials || trials.length === 0) {
        container.innerHTML = '<p class="text-muted">No matching trials found.</p>';
        return;
    }

    // Sort trials by match score
    const sortedTrials = trials.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));
    
    for (const trial of sortedTrials) {
        const trialCard = createTrialCard(trial);
        container.appendChild(trialCard);
    }
}

function createTrialCard(trial) {
    const card = document.createElement('div');
    card.className = 'trial-match-card mb-3';
    
    const matchScore = trial.match_score || 0;
    const scoreClass = matchScore >= 70 ? 'success' : matchScore >= 50 ? 'warning' : 'danger';
    
    card.innerHTML = `
        <div class="trial-header d-flex justify-content-between align-items-center">
            <div class="trial-title-group">
                <h6 class="trial-title mb-1">${escapeHtml(trial.title || 'Unknown Trial')}</h6>
                <small class="text-muted">ID: ${escapeHtml(trial.trial_id || 'Unknown')}</small>
            </div>
            <div class="trial-score">
                <span class="badge badge-${scoreClass} score-badge">${matchScore}%</span>
            </div>
        </div>
        
        <div class="trial-content mt-2">
            <div class="trial-recommendation mb-2">
                <strong>Recommendation:</strong> 
                <span class="recommendation-${getRecommendationClass(trial.recommendation)}">
                    ${escapeHtml(trial.recommendation || 'Unknown')}
                </span>
            </div>
            
            <div class="trial-summary mb-2">
                <strong>Summary:</strong>
                <p class="trial-summary-text">${escapeHtml(trial.summary || 'No summary available')}</p>
            </div>
            
            <div class="trial-analysis">
                <button class="btn btn-sm btn-outline-info" type="button" 
                        onclick="toggleTrialDetails('${trial.trial_id}')">
                    Show Criteria Analysis
                </button>
                <div id="details-${trial.trial_id}" class="trial-details mt-2 d-none">
                    <strong>Detailed Analysis:</strong>
                    <div class="criteria-analysis">
                        ${escapeHtml(trial.criteria_analysis || 'No detailed analysis available')}
                    </div>
                    ${trial.safety_flags && trial.safety_flags.length > 0 ? 
                        `<div class="safety-flags mt-2">
                            <strong class="text-warning">Safety Flags:</strong>
                            <ul class="safety-flag-list">
                                ${trial.safety_flags.map(flag => `<li class="text-warning">${escapeHtml(flag)}</li>`).join('')}
                            </ul>
                        </div>` : ''}
                </div>
            </div>
        </div>
    `;
    
    return card;
}

function getRecommendationClass(recommendation) {
    switch(recommendation?.toLowerCase()) {
        case 'eligible': return 'success';
        case 'not eligible': return 'danger';
        case 'insufficient information': return 'warning';
        default: return 'secondary';
    }
}

function toggleTrialDetails(trialId) {
    const details = document.getElementById(`details-${trialId}`);
    if (details) {
        details.classList.toggle('d-none');
        
        const button = details.previousElementSibling;
        if (button) {
            button.textContent = details.classList.contains('d-none') ? 
                'Show Criteria Analysis' : 'Hide Criteria Analysis';
        }
    }
}

function displayProcessingMetadata(metadata) {
    if (!metadata) return;
    
    // You can display processing time, feature count, etc. in the UI
    console.log('Processing metadata:', metadata);
}

function initializeHighlightingSystem() {
    // Add CSS for highlighting if not already present
    if (!document.getElementById('highlight-styles')) {
        const style = document.createElement('style');
        style.id = 'highlight-styles';
        style.textContent = `
            .feature-highlight {
                background-color: rgba(255, 235, 59, 0.3);
                border-radius: 2px;
                padding: 1px 2px;
                cursor: help;
            }
            
            .feature-highlight:hover {
                background-color: rgba(255, 235, 59, 0.6);
            }
            
            .feature-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }
            
            .feature-item:last-child {
                border-bottom: none;
            }
            
            .feature-label {
                font-weight: 500;
                color: #555;
                flex: 1;
            }
            
            .feature-value {
                font-weight: 400;
                color: #333;
                text-align: right;
                max-width: 200px;
                word-wrap: break-word;
            }
            
            .feature-group-header {
                border-bottom: 2px solid #007bff;
                padding-bottom: 4px;
                margin-bottom: 8px;
            }
            
            .trial-match-card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 16px;
                background-color: #fff;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            
            .trial-header {
                border-bottom: 1px solid #eee;
                padding-bottom: 8px;
            }
            
            .score-badge {
                font-size: 14px;
                font-weight: bold;
            }
            
            .recommendation-success {
                color: #28a745;
                font-weight: bold;
            }
            
            .recommendation-danger {
                color: #dc3545;
                font-weight: bold;
            }
            
            .recommendation-warning {
                color: #ffc107;
                font-weight: bold;
            }
            
            .recommendation-secondary {
                color: #6c757d;
                font-weight: bold;
            }
            
            .safety-flag-list {
                margin: 0;
                padding-left: 20px;
            }
            
            .safety-flag-list li {
                font-size: 0.9em;
                margin-bottom: 4px;
            }
            
            .trial-summary-text {
                font-size: 0.9em;
                color: #666;
                margin: 0;
            }
        `;
        document.head.appendChild(style);
    }
}

function showLoadingSpinner(show) {
    const spinner = document.getElementById('loading-spinner');
    const processButton = document.getElementById('process-button');
    
    if (spinner) {
        if (show) {
            spinner.classList.remove('d-none');
        } else {
            spinner.classList.add('d-none');
        }
    }
    
    if (processButton) {
        processButton.disabled = show;
        processButton.textContent = show ? 'Processing...' : 'Process & Find Matches';
    }
}

function clearResults() {
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.classList.add('d-none');
    }
    
    // Clear containers
    const containers = ['features-container', 'matches-container', 'evidence'];
    containers.forEach(id => {
        const container = document.getElementById(id);
        if (container) {
            container.innerHTML = '';
        }
    });
    
    // Reset session
    currentSession = {
        features: null,
        highlightedText: null,
        originalText: null,
        trials: null,
        processingTime: null
    };
}

function clearAll() {
    // Clear file input
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.value = '';
    }
    
    // Clear text input
    const textInput = document.getElementById('text-input');
    if (textInput) {
        textInput.value = '';
    }
    
    // Reset dropzone
    const dropzone = document.getElementById('dropzone');
    if (dropzone) {
        const dropzoneMessage = dropzone.querySelector('.dropzone-message');
        const dropzoneDescription = dropzone.querySelector('.dropzone-description');
        
        if (dropzoneMessage) dropzoneMessage.textContent = 'Drag & drop your file here';
        if (dropzoneDescription) dropzoneDescription.textContent = 'or click to browse files';
    }
    
    // Clear results
    clearResults();
    
    // Clear alerts
    clearAlerts();
    
    // Reset to file input method
    setActiveInputMethod('file');
}

function showAlert(type, message) {
    const container = document.getElementById('alert-container');
    if (!container) return;

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
            <span aria-hidden="true">&times;</span>
        </button>
    `;
    
    container.appendChild(alertDiv);
    
    // Auto-remove success alerts after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

function clearAlerts() {
    const container = document.getElementById('alert-container');
    if (container) {
        container.innerHTML = '';
    }
}

function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return String(unsafe);
    
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Health check functionality
async function checkSystemHealth() {
    try {
        const response = await fetch(CONFIG.apiEndpoints.health);
        const result = await response.json();
        
        if (result.status === 'healthy') {
            console.log('System health: OK');
        } else {
            console.warn('System health issues detected:', result);
        }
        
        return result;
    } catch (error) {
        console.error('Health check failed:', error);
        return { status: 'error', error: error.message };
    }
}

// Feature validation utility
async function validateFeatures(features) {
    try {
        const response = await fetch(CONFIG.apiEndpoints.validate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ features })
        });
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('Feature validation failed:', error);
        return { success: false, error: error.message };
    }
}

// Export functions for potential external use
window.MedMatchINT = {
    processPatientData,
    clearAll,
    showAlert,
    checkSystemHealth,
    validateFeatures,
    currentSession: () => ({ ...currentSession }) // Return copy to prevent external modification
};
function displayTrials(trials) {
    // Just call your existing function with a different name
    displayMatchedTrials(trials);
}

function displayFeatures(features) {
    // Just call your existing function with a different name  
    displayCleanFeatures(features);
}