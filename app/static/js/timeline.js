document.addEventListener('DOMContentLoaded', function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const textInput = document.getElementById('text-input');
  const clearButton = document.getElementById('clear-button');
  const processButton = document.getElementById('process-button');
  const resultsSection = document.getElementById('results-section');
  const featuresContainer = document.getElementById('features-container');
  const loadingSpinner = document.getElementById('loading-spinner');
  const alertContainer = document.getElementById('alert-container');

  let selectedFile = null;

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) handleFiles(fileInput.files);
    });
  }

  if (dropzone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName =>
      dropzone.addEventListener(eventName, preventDefaults, false)
    );
    dropzone.addEventListener('drop', handleDrop, false);
    dropzone.addEventListener('click', () => fileInput.click());
  }

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  function handleDrop(e) {
    const files = e.dataTransfer.files;
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
    const message = dropzone.querySelector('.dropzone-message');
    if (message) message.innerHTML = `<strong>${filename}</strong>`;
  }

  if (clearButton) clearButton.addEventListener('click', clearAll);

  function clearAll() {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    if (textInput) textInput.value = '';
    if (featuresContainer) featuresContainer.innerHTML = '';
    if (resultsSection) resultsSection.classList.add('d-none');
    if (processButton) processButton.disabled = true;
    showAlert('All inputs cleared.', 'info');
  }

  if (processButton) processButton.addEventListener('click', processDocument);

  async function processDocument() {
    if (!selectedFile && (!textInput || !textInput.value.trim())) {
      showAlert('Please upload a PDF file or enter text.', 'danger');
      return;
    }

    if (loadingSpinner) loadingSpinner.classList.remove('d-none');
    if (resultsSection) resultsSection.classList.add('d-none');
    if (featuresContainer) featuresContainer.innerHTML = '';

    const formData = new FormData();
    if (selectedFile) {
      formData.append('file', selectedFile);
    } else if (textInput.value.trim()) {
      formData.append('text', textInput.value.trim());
    }

    try {
      const response = await fetch('/process_timeline', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      if (response.ok) {
        displayResults(data.features);
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

  function displayResults(events) {
    featuresContainer.innerHTML = '';

    if (!Array.isArray(events) || events.length === 0) {
      featuresContainer.innerHTML = '<p>No timeline events found.</p>';
      return;
    }

    events.forEach(event => {
      const item = document.createElement('div');
      item.className = 'feature-item';

      const label = document.createElement('div');
      label.className = 'feature-label';
      label.textContent = event.date || 'Unknown Date';

      const value = document.createElement('div');
      value.className = 'feature-value';
      value.innerHTML = `<strong>${event.event}</strong><br>${event.details || ''}`;

      item.appendChild(label);
      item.appendChild(value);
      featuresContainer.appendChild(item);
    });
  }

  function showAlert(message, type = 'info') {
    if (!alertContainer) return;
    alertContainer.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    setTimeout(() => (alertContainer.innerHTML = ''), 5000);
  }
});
