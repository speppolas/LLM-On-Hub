// document.addEventListener('DOMContentLoaded', function () {
//   const dropzone = document.getElementById('dropzone');
//   const fileInput = document.getElementById('file-input');
//   const textInput = document.getElementById('text-input');
//   const clearButton = document.getElementById('clear-button');
//   const processButton = document.getElementById('process-button');
//   const resultsSection = document.getElementById('results-section');
//   const featuresContainer = document.getElementById('features-container');
//   const loadingSpinner = document.getElementById('loading-spinner');
//   const alertContainer = document.getElementById('alert-container');

//   let selectedFiles = null;

//   if (fileInput) {
//     fileInput.addEventListener('change', () => {
//       if (fileInput.files.length) handleFiles(fileInput.files);
//     });
//   }

//   if (dropzone) {
//     ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName =>
//       dropzone.addEventListener(eventName, preventDefaults, false)
//     );
//     dropzone.addEventListener('drop', handleDrop, false);
//     dropzone.addEventListener('click', () => fileInput.click());
//   }

//   function preventDefaults(e) {
//     e.preventDefault();
//     e.stopPropagation();
//   }

//   function handleDrop(e) {
//     const files = e.dataTransfer.files;
//     if (files.length) handleFiles(files);
//   }

//   // VALE
//   // function handleFiles(files) {
//   //   if (files[0].type === 'application/pdf') {
//   //     selectedFile = files[0];
//   //     updateDropzoneUI(selectedFile.name);
//   //     if (processButton) processButton.disabled = false;
//   //   } else {
//   //     showAlert('Please upload a PDF file.', 'danger');
//   //   }
//   // }


//   //function handleFiles(files) {
//   //files = Array.from(files);
//   //console.log('files', files)
//   //if (files.every(file => file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')) {
//   //selectedFiles = files;
//   //updateDropzoneUI(files.map(file => file.name).join(', '));
//   //if (processButton) processButton.disabled = false;
//   //} else {
//   //showAlert('Please upload a file.', 'danger');
//   //}
//   // valentina csv}

//   function handleFiles(files) {
//     files = Array.from(files);
//     console.log('files', files);
//     if (files.every(file =>
//       file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
//       file.type === 'text/csv' ||
//       file.name.toLowerCase().endsWith('.csv')  // 👈 fallback per .csv con type mancante
//     )) {
//       selectedFiles = files;
//       updateDropzoneUI(files.map(file => file.name).join(', '));
//       if (processButton) processButton.disabled = false;
//     } else {
//       showAlert('Please upload an Excel (.xlsx) or CSV (.csv) file.', 'danger');
//     }
//   }

//   function updateDropzoneUI(filename) {
//     const message = dropzone.querySelector('.dropzone-message');
//     if (message) message.innerHTML = `<strong>${filename}</strong>`;
//   }

//   if (clearButton) clearButton.addEventListener('click', clearAll);

//   function clearAll() {
//     selectedFiles = null;
//     if (fileInput) fileInput.value = '';
//     if (textInput) textInput.value = '';
//     if (featuresContainer) featuresContainer.innerHTML = '';
//     if (resultsSection) resultsSection.classList.add('d-none');
//     if (processButton) processButton.disabled = true;
//     updateDropzoneUI('Drag & drop your file here')
//     showAlert('All inputs cleared.', 'info');
//   }

//   if (processButton) processButton.addEventListener('click', processDocument);

//   async function processDocument() {
//     if (!selectedFiles && (!textInput || !textInput.value.trim())) {
//       showAlert('Please upload a PDF file or enter text.', 'danger');
//       return;
//     }

//     if (loadingSpinner) loadingSpinner.classList.remove('d-none');
//     if (resultsSection) resultsSection.classList.add('d-none');
//     if (featuresContainer) featuresContainer.innerHTML = '';

//     let showResults = false;
//     let alldata = [];
//     for (i = 0; i < selectedFiles.length; i++) {
//       let selectedFile = selectedFiles[i];
//       const formData = new FormData();
//       if (selectedFile) {
//         formData.append('file', selectedFile);
//       } else if (textInput.value.trim()) {
//         formData.append('text', textInput.value.trim());
//       }

//       try {
//         const response = await fetch('/process_medications', {
//           method: 'POST',
//           body: formData
//         });

//         const data = await response.json();
//         if (response.ok) {
//           // displayResults(selectedFile.name, data.features);
//           Object.keys(data.features).forEach(key => {
//             displayResults(key, data.features[key]);
//             if (data.features[key].medications) {
//               data.features[key].medications.forEach(med => {
//                 alldata.push({ ...med, 'id': key, 'comorbidity': data.features[key].comorbidity });
//               });
//             }
//           });
//           showResults = true;
//         } else {
//           showAlert(data.error || `An error occurred while processing document ${selectedFile.name}.`, 'danger');
//         }
//       } catch (error) {
//         showAlert('An error occurred while processin document.', 'danger');
//       }
//     }

//     if (showResults) {
//       resultsSection.classList.remove('d-none');
//       document.getElementById('download-results').onclick = function () {
//         downloadCSV(alldata);
//       }
//     }
//     if (loadingSpinner) loadingSpinner.classList.add('d-none');

//   }
//   function downloadCSV(data, filename = 'medications.csv') {
//     // Define the CSV header
//     const headers = [
//       'id',
//       'medication',
//       'dosage',
//       'frequency',
//       'period',
//       'mutation',
//       'exon',
//       'modality',
//       'collateral',
//       'comorbidity'
//     ];

//     // Create CSV content
//     const csvContent = [
//       headers.join(','), // header row
//       ...data.map(row =>
//         headers.map(field => `"${(row[field] || '').toString().replace(/"/g, '""')}"`).join(',')
//       )
//     ].join('\n');

//     // Create a Blob with CSV content
//     const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });

//     // Create a download link and trigger it
//     const link = document.createElement('a');
//     const url = URL.createObjectURL(blob);
//     link.setAttribute('href', url);
//     link.setAttribute('download', filename);
//     document.body.appendChild(link);
//     link.click();
//     document.body.removeChild(link);
//   }

//   function displayResults(documentName, medications) {
//     featuresContainer.innerHTML += `<h2>${documentName}<h2>`;

//     // ✅ Trasforma in array se è oggetto/dizionario
//     /*if (!Array.isArray(medications)) {
//       medications = Object.values(medications);
//     }*/
//     comorbidity = medications['comorbidity']
//     medications = medications['medications']

//     console.log('medications', medications)

//     if (!medications || medications.length === 0) {
//       featuresContainer.innerHTML += '<p>No medications found.</p>';
//       return;
//     }

//     // [EDIT VALENTINA 2025-05-31]
//     // medications.forEach(med => {
//     //   const item = document.createElement('div');
//     //   item.className = 'feature-item';

//     //   const label = document.createElement('div');
//     //   label.className = 'feature-label';
//     //   label.textContent = med.medication || 'Unnamed Medication';

//     //   const value = document.createElement('div');
//     //   value.className = 'feature-value';
//     //   value.innerHTML = `
//     //     <strong>Dosage:</strong> ${med.dosage || 'N/A'}<br>
//     //     <strong>Frequency:</strong> ${med.frequency || 'N/A'}<br>
//     //     <strong>Indication:</strong> ${med.indication || 'N/A'}
//     //   `;

//     //   item.appendChild(label);
//     //   item.appendChild(value);
//     //   featuresContainer.appendChild(item);
//     // });

//     featuresTbl = document.createElement('table');
//     featuresTbl.classList.add('table');
//     header = '<tr><th>Medication</th><th>Dosage</th><th>Frequency</th><th>Period</th><th>Mutation</th><th>Exon</th><th>Modality</th><th>Collateral Effects</th></tr>'
//     featuresTbl.innerHTML = header
//     medications.forEach(med => {
//       row = `<tr>
//       <td> ${med.medication || 'Unnamed Medication'}</td>
//       <td> ${med.dosage || 'N/A'}</td>
//       <td>${med.frequency || 'N/A'}</td>
//       <td>${med.period || 'N/A'}</td>
//       <td>${med.mutation || 'N/A'}</td>
//       <td>${med.exon || 'N/A'}</td>
//       <td>${med.modality || 'N/A'}</td> 
//       <td>${med.collateral || 'N/A'}</td> 
//       </tr>
//     `;
//       featuresTbl.innerHTML += row;
//     });
//     featuresContainer.appendChild(featuresTbl)
//     featuresContainer.innerHTML += `<br><div><strong>Comorbidity:</strong>${comorbidity}</div><br><br><br>`
//   }

//   function showAlert(message, type = 'info') {
//     if (!alertContainer) return;
//     alertContainer.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
//     setTimeout(() => (alertContainer.innerHTML = ''), 5000);
//   }
// });


// //  EVALUATION VALE
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

  let selectedFiles = null;
  let model_name = 'unknown_model';

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
    files = Array.from(files);
    console.log('files', files);
    if (files.every(file =>
      file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
      file.type === 'text/csv' ||
      file.name.toLowerCase().endsWith('.csv')
    )) {
      selectedFiles = files;
      updateDropzoneUI(files.map(file => file.name).join(', '));
      if (processButton) processButton.disabled = false;
    } else {
      showAlert('Please upload an Excel (.xlsx) or CSV (.csv) file.', 'danger');
    }
  }

  function updateDropzoneUI(filename) {
    const message = dropzone.querySelector('.dropzone-message');
    if (message) message.innerHTML = `<strong>${filename}</strong>`;
  }

  if (clearButton) clearButton.addEventListener('click', clearAll);

  function clearAll() {
    selectedFiles = null;
    if (fileInput) fileInput.value = '';
    if (textInput) textInput.value = '';
    if (featuresContainer) featuresContainer.innerHTML = '';
    if (resultsSection) resultsSection.classList.add('d-none');
    if (processButton) processButton.disabled = true;
    updateDropzoneUI('Drag & drop your file here');
    showAlert('All inputs cleared.', 'info');
  }

  if (processButton) processButton.addEventListener('click', processDocument);

  async function processDocument() {
    if (!selectedFiles && (!textInput || !textInput.value.trim())) {
      showAlert('Please upload a PDF file or enter text.', 'danger');
      return;
    }

    if (loadingSpinner) loadingSpinner.classList.remove('d-none');
    if (resultsSection) resultsSection.classList.add('d-none');
    if (featuresContainer) featuresContainer.innerHTML = '';

    let showResults = false;
    let alldata = [];
    for (let i = 0; i < selectedFiles.length; i++) {
      let selectedFile = selectedFiles[i];
      const formData = new FormData();
      if (selectedFile) {
        formData.append('file', selectedFile);
      } else if (textInput.value.trim()) {
        formData.append('text', textInput.value.trim());
      }

      try {
        const response = await fetch('/process_medications', {
          method: 'POST',
          body: formData
        });
        const data = await response.json();
        if (response.ok) {
          model_name = data.model || 'unknown_model';
          Object.keys(data.features).forEach(key => {
            displayResults(key, data.features[key]);
            if (data.features[key].medications) {
              data.features[key].medications.forEach(med => {
                alldata.push({ ...med, 'id': key, 'comorbidity': data.features[key].comorbidity });
              });
            }
          });
          showResults = true;
        } else {
          showAlert(data.error || `An error occurred while processing document ${selectedFile.name}.`, 'danger');
        }
      } catch (error) {
        showAlert('An error occurred while processing document.', 'danger');
      }
    }

    if (showResults) {
      resultsSection.classList.remove('d-none');
      document.getElementById('download-results').onclick = function () {
        downloadCSV(alldata, filename = model_name + '.csv');
      };
    }
    if (loadingSpinner) loadingSpinner.classList.add('d-none');
  }

  function downloadCSV(data, filename = 'medications.csv') {
    const headers = [
      'id',
      'medication',
      'dosage',
      'frequency',
      'period',
      'mutation',
      'exon',
      'modality',
      'collateral',
      'comorbidity'
    ];
    const csvContent = [
      headers.join(','),
      ...data.map(row =>
        headers.map(field => `"${(row[field] || '').toString().replace(/"/g, '""')}"`).join(',')
      )
    ].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function showAlert(message, type = 'info') {
    if (!alertContainer) return;
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerText = message;
    alertContainer.appendChild(alertDiv);
    setTimeout(() => {
      alertDiv.remove();
    }, 3000);
  }

  // function displayResults(id, features) {
  //   const card = document.createElement('div');
  //   card.className = 'card mb-3';
  //   const cardHeader = document.createElement('div');
  //   cardHeader.className = 'card-header';
  //   cardHeader.innerHTML = `<h5 class="mb-0">Patient ID: ${id}</h5>`;
  //   const cardBody = document.createElement('div');
  //   cardBody.className = 'card-body';
  //   const pre = document.createElement('pre');
  //   pre.textContent = JSON.stringify(features, null, 2);
  //   cardBody.appendChild(pre);
  //   card.appendChild(cardHeader);
  //   card.appendChild(cardBody);
  //   featuresContainer.appendChild(card);
  // }

  function displayResults(documentName, medications) {
    featuresContainer.innerHTML += `<h2>${documentName}<h2>`;

    // ✅ Trasforma in array se è oggetto/dizionario
    /*if (!Array.isArray(medications)) {
      medications = Object.values(medications);
    }*/
    comorbidity = medications['comorbidity']
    medications = medications['medications']

    console.log('medications', medications)

    // if (!medications || medications.length === 0) {
    //   featuresContainer.innerHTML += '<p>No medications found.</p>';
    //   // return;
    // }

    // [EDIT VALENTINA 2025-05-31]
    // medications.forEach(med => {
    //   const item = document.createElement('div');
    //   item.className = 'feature-item';

    //   const label = document.createElement('div');
    //   label.className = 'feature-label';
    //   label.textContent = med.medication || 'Unnamed Medication';

    //   const value = document.createElement('div');
    //   value.className = 'feature-value';
    //   value.innerHTML = `
    //     <strong>Dosage:</strong> ${med.dosage || 'N/A'}<br>
    //     <strong>Frequency:</strong> ${med.frequency || 'N/A'}<br>
    //     <strong>Indication:</strong> ${med.indication || 'N/A'}
    //   `;

    //   item.appendChild(label);
    //   item.appendChild(value);
    //   featuresContainer.appendChild(item);
    // });

    featuresTbl = document.createElement('table');
    featuresTbl.classList.add('table');
    header = '<tr><th>Medication</th><th>Dosage</th><th>Frequency</th><th>Period</th><th>Mutation</th><th>Exon</th><th>Modality</th><th>Collateral Effects</th></tr>'
    featuresTbl.innerHTML = header
    medications.forEach(med => {
      row = `<tr>
      <td> ${med.medication || 'Unnamed Medication'}</td>
      <td> ${med.dosage || 'N/A'}</td>
      <td>${med.frequency || 'N/A'}</td>
      <td>${med.period || 'N/A'}</td>
      <td>${med.mutation || 'N/A'}</td>
      <td>${med.exon || 'N/A'}</td>
      <td>${med.modality || 'N/A'}</td> 
      <td>${med.collateral || 'N/A'}</td> 
      </tr>
    `;
      featuresTbl.innerHTML += row;
    });
    featuresContainer.appendChild(featuresTbl)
    featuresContainer.innerHTML += `<br><div><strong>Comorbidity:</strong>${comorbidity}</div><br><br><br>`
  }

});


