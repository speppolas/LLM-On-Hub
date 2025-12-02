/**
 * LLM-On-Hub Frontend (MedMatchINT Style)
 * Simplified, clean, Bootstrap-based client logic
 * Maintains the original UX of MedMatchINT with added PDF & Evidence support
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
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
    const annotatedFrame = document.getElementById('annotated-pdf-frame');
    const btnAnnotatedPDF = document.getElementById('btn-annotated-pdf');
    const btnDownloadPDF = document.getElementById('btn-download-pdf');

    let selectedFile = null;

    /** ----------------------------
     * File Upload & Dropzone
     * ---------------------------- */
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length) {
                handleFiles(fileInput.files);
            }
        });
    }

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
        const file = files[0];
        if (file && file.type === 'application/pdf') {
            selectedFile = file;
            updateDropzoneUI(file.name);
            processButton.disabled = false;
        } else {
            showAlert('Please upload a valid PDF file.', 'danger');
        }
    }

    function updateDropzoneUI(filename) {
        const msg = dropzone.querySelector('.dropzone-message');
        msg.innerHTML = `<strong>${filename}</strong>`;
    }

    /** ----------------------------
     * Clear Inputs
     * ---------------------------- */
    if (clearButton) {
        clearButton.addEventListener('click', clearAll);
    }

    function clearAll() {
        selectedFile = null;
        if (fileInput) fileInput.value = '';
        if (textInput) textInput.value = '';
        if (featuresContainer) featuresContainer.innerHTML = '';
        if (matchesContainer) matchesContainer.innerHTML = '';
        if (annotatedFrame) annotatedFrame.removeAttribute('src');
        if (btnAnnotatedPDF) btnAnnotatedPDF.classList.add('d-none');
        if (btnDownloadPDF) btnDownloadPDF.classList.add('d-none');
        if (resultsSection) resultsSection.classList.add('d-none');
        processButton.disabled = true;
        showAlert('All inputs cleared.', 'info');
    }

    /** ----------------------------
     * Processing Logic
     * ---------------------------- */
    if (processButton) {
        processButton.addEventListener('click', processDocument);
    }

    async function processDocument() {
        if (!selectedFile && (!textInput || !textInput.value.trim())) {
            showAlert('Please upload a PDF file or enter text.', 'danger');
            return;
        }

        loadingSpinner.classList.remove('d-none');
        resultsSection.classList.add('d-none');
        featuresContainer.innerHTML = '';
        matchesContainer.innerHTML = '';

        const formData = new FormData();
        if (selectedFile) formData.append('file', selectedFile);
        else formData.append('text', textInput.value.trim());

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                displayResults(data);
                resultsSection.classList.remove('d-none');
            } else {
                showAlert(data.error || 'Error while processing document.', 'danger');
            }
        } catch (error) {
            console.error(error);
            showAlert('Error while processing the document.', 'danger');
        } finally {
            loadingSpinner.classList.add('d-none');
        }
    }

    /** ----------------------------
     * Display Logic
     * ---------------------------- */
    function displayResults(data) {
        displayFeatures(data.features || {});
        displayMatches(data.matched_trials || []);
        handleAnnotatedPDF(data.annotated_pdf_url);
    }

    function displayFeatures(features) {
        featuresContainer.innerHTML = '';
        for (const [key, value] of Object.entries(features)) {
            const item = document.createElement('div');
            item.className = 'feature-item';

            const label = document.createElement('div');
            label.className = 'feature-label';
            label.textContent = key.replace(/_/g, ' ').toUpperCase();

            const val = document.createElement('div');
            val.className = 'feature-value';
            val.textContent = formatValue(value);

            item.appendChild(label);
            item.appendChild(val);
            featuresContainer.appendChild(item);
        }
    }

    // Display matched clinical trials (old MedMatchINT style)
function displayMatches(matches) {
    if (!matchesContainer) return;
    matchesContainer.innerHTML = '';

    if (!matches || matches.length === 0) {
        matchesContainer.innerHTML = '<p>No matched trials found.</p>';
        return;
    }

    matches.forEach(match => {
        const matchCard = document.createElement('div');
        matchCard.className = 'match-card';

        // Basic trial info
        matchCard.innerHTML = `
            <h4>Trial ID: ${match.trial_id || 'N/A'}</h4>
            <p><strong>Confidence:</strong> ${match.confidence || match.match_score || 0}%</p>
            <p><strong>Recommendation:</strong> ${match.recommendation || 'N/A'}</p>
            <p><strong>Summary:</strong> ${match.summary || 'No summary provided.'}</p>
        `;

        // Criteria analysis (optional)
        if (match.analysis && Object.keys(match.analysis).length > 0) {
            const analysisDiv = document.createElement('div');
            analysisDiv.className = 'match-analysis';
            analysisDiv.innerHTML = '<h5>Criteria Analysis:</h5>';

            for (const [criterion, details] of Object.entries(match.analysis)) {
                const criterionDiv = document.createElement('div');
                criterionDiv.className = 'analysis-item';
                criterionDiv.innerHTML = `
                    <strong>${criterion}:</strong> ${JSON.stringify(details, null, 2)}
                `;
                analysisDiv.appendChild(criterionDiv);
            }

            matchCard.appendChild(analysisDiv);
        }

        matchesContainer.appendChild(matchCard);
    });
}


    function handleAnnotatedPDF(pdfUrl) {
        if (pdfUrl) {
            if (annotatedFrame) annotatedFrame.src = pdfUrl;
            if (btnAnnotatedPDF) {
                btnAnnotatedPDF.href = pdfUrl;
                btnAnnotatedPDF.classList.remove('d-none');
            }
            if (btnDownloadPDF) {
                btnDownloadPDF.href = pdfUrl;
                btnDownloadPDF.classList.remove('d-none');
            }
        } else {
            if (annotatedFrame) annotatedFrame.removeAttribute('src');
            if (btnAnnotatedPDF) btnAnnotatedPDF.classList.add('d-none');
            if (btnDownloadPDF) btnDownloadPDF.classList.add('d-none');
        }
    }

    /** ----------------------------
     * Utilities
     * ---------------------------- */
    function formatValue(value) {
        if (Array.isArray(value)) return value.join(', ');
        if (typeof value === 'object' && value !== null) return JSON.stringify(value, null, 2);
        return value;
    }

    function showAlert(message, type = 'info') {
        alertContainer.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
        setTimeout(() => (alertContainer.innerHTML = ''), 4000);
    }
});
