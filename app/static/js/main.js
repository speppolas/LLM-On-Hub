/**
 * MedMatchINT - Main JavaScript
 * Handles all client-side functionality for the clinical trial matching application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');
    const clearButton = document.getElementById('clear-button');
    const processButton = document.getElementById('process-button');
    const resultsSection = document.getElementById('results-section');
    const featuresContainer = document.getElementById('features-container');
    const matchesContainer = document.getElementById('matches-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const alertContainer = document.getElementById('alert-container');

    let selectedFile = null;

    // Handle file selection
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length) {
                handleFiles(fileInput.files);
            }
        });
    }

    // Dropzone for drag-and-drop file upload
    if (dropzone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });

        dropzone.addEventListener('drop', handleDrop, false);
        dropzone.addEventListener('click', () => fileInput.click());
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length) handleFiles(files);
    }

    function handleFiles(files) {
        if (files[0].type === 'application/pdf') {
            selectedFile = files[0];
            updateDropzoneUI(selectedFile.name);
            if (processButton) processButton.disabled = false;
        } else {
            showAlert('Please upload a PDF file.', 'danger');
        }
    }

    function updateDropzoneUI(filename) {
        const dropzoneMessage = dropzone.querySelector('.dropzone-message');
        dropzoneMessage.innerHTML = `<strong>${filename}</strong>`;
    }

    // Clear button functionality
    if (clearButton) {
        clearButton.addEventListener('click', clearAll);
    }

    function clearAll() {
        selectedFile = null;
        if (fileInput) fileInput.value = '';
        if (textInput) textInput.value = '';
        if (featuresContainer) featuresContainer.innerHTML = '';
        if (matchesContainer) matchesContainer.innerHTML = '';
        if (resultsSection) resultsSection.classList.add('d-none');
        if (processButton) processButton.disabled = true;
        showAlert('All inputs cleared.', 'info');
    }

    // Process document and find matches
    if (processButton) {
        processButton.addEventListener('click', processDocument);
    }

    async function processDocument() {
        if (!selectedFile && (!textInput || !textInput.value.trim())) {
            showAlert('Please upload a PDF file or enter text.', 'danger');
            return;
        }

        // Show loading spinner
        if (loadingSpinner) loadingSpinner.classList.remove('d-none');
        if (resultsSection) resultsSection.classList.add('d-none');
        if (featuresContainer) featuresContainer.innerHTML = '';
        if (matchesContainer) matchesContainer.innerHTML = '';

        const formData = new FormData();
        if (selectedFile) {
            formData.append('file', selectedFile);
        } else if (textInput.value.trim()) {
            formData.append('text', textInput.value.trim());
        }

        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                displayResults(data);
                resultsSection.classList.remove('d-none');
            } else {
                showAlert(data.error || 'An error occurred while processing the document.', 'danger');
            }
        } catch (error) {
            showAlert('An error occurred while processing the document.', 'danger');
        } finally {
            if (loadingSpinner) loadingSpinner.classList.add('d-none');
        }
    }

    // Display the extracted features and matched trials
    function displayResults(data) {
    displayFeatures(data.features);
    displayMatches(data.matched_trials);

    if (data.screening_time) {
  renderScreeningSummary(data.screening_time);
}

}


    // Display extracted features
    function displayFeatures(features) {
        if (!featuresContainer) return;
        featuresContainer.innerHTML = '';

        for (const [key, value] of Object.entries(features)) {
            const featureDiv = document.createElement('div');
            featureDiv.className = 'feature-item';

            const featureLabel = document.createElement('div');
            featureLabel.className = 'feature-label';
            featureLabel.textContent = key.toUpperCase();

            const featureValue = document.createElement('div');
            featureValue.className = 'feature-value';
            if (Array.isArray(value)) {
                featureValue.textContent = value.join(', ');
            } else {
                featureValue.textContent = value;
            }


            featureDiv.appendChild(featureLabel);
            featureDiv.appendChild(featureValue);
            featuresContainer.appendChild(featureDiv);
        }
    }

    // Display matched clinical trials


function renderScreeningSummary(screening_time) {
  document.getElementById("t-feat").textContent =
    formatTime(screening_time.feature_extraction_ms);

  document.getElementById("t-match").textContent =
    formatTime(screening_time.trial_matching_ms);

  document.getElementById("t-total").textContent =
    formatTime(screening_time.total_ms);

  document.getElementById("screening-summary").classList.remove("d-none");
}


function formatTime(ms) {
  if (ms < 1000) {
    return `${ms.toFixed(2)} ms`;
  } else if (ms < 60000) {
    return `${(ms / 1000).toFixed(2)} s`;
  } else {
    const min = Math.floor(ms / 60000);
    const sec = ((ms % 60000) / 1000).toFixed(1);
    return `${min} min ${sec} s`;
  }
}



function displayMatches(matches) {
    const matchesContainer = document.getElementById('matches-container');
    if (!matchesContainer) return;

    matchesContainer.innerHTML = '';

    if (!matches || matches.length === 0) {
        matchesContainer.innerHTML = '<p>No matched trials found.</p>';
        return;
    }

    matches.forEach(match => {
        const matchCard = document.createElement('div');
        matchCard.className = 'match-card p-3 mb-3 border rounded';

        // Badge per eligibility
        let badgeHtml = '';
        if (match.overall === 'eligible') {
            badgeHtml = '<span class="badge bg-success">Eligible</span>';
        } else if (match.overall === 'not_eligible') {
            badgeHtml = '<span class="badge bg-danger">Not eligible</span>';
        } else {
            badgeHtml = '<span class="badge bg-warning text-dark">Unknown</span>';
        }

        // Costruzione trace (XAI)
        let inclusionHtml = '';
        if (match.trace && match.trace.inclusion) {
            inclusionHtml = match.trace.inclusion.map(c => `
                <li>
                    <strong>${c.id}</strong> — ${c.status}
                    <br/>
                    <small>${c.text || ''}</small>
                </li>
            `).join('');
        }

        let exclusionHtml = '';
        if (match.trace && match.trace.exclusion) {
            exclusionHtml = match.trace.exclusion.map(c => `
                <li>
                    <strong>${c.id}</strong> — ${c.status}
                    <br/>
                    <small>${c.text || ''}</small>
                </li>
            `).join('');
        }

        matchCard.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <h4>${match.title || 'Unknown Trial'}</h4>
                ${badgeHtml}
            </div>

            <p><strong>Trial ID:</strong> ${match.trial_id}</p>

            <details class="mt-2">
                <summary><strong>Inclusion Criteria Evaluation</strong></summary>
                <ul>${inclusionHtml || '<li>No inclusion criteria evaluated.</li>'}</ul>
            </details>

            <details class="mt-2">
                <summary><strong>Exclusion Criteria Evaluation</strong></summary>
                <ul>${exclusionHtml || '<li>No exclusion criteria evaluated.</li>'}</ul>
            </details>
        `;

        matchesContainer.appendChild(matchCard);
    });
}


    // Show alert message
    function showAlert(message, type = 'info') {
        if (!alertContainer) return;
        alertContainer.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
        setTimeout(() => alertContainer.innerHTML = '', 5000);
    }
});