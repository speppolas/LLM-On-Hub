// ESTRAZIONE DA PIU’ DOCS: DATA E TESTO (e RECIST per TC), NO DETAIL (Excel → per-row streaming)
document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const clearButton = document.getElementById('clear-button');
  const processButton = document.getElementById('process-button');
  const resultsSection = document.getElementById('results-section');

  // Create a new host AFTER the "Risultati" card so each ID appears on the page background
  const islandsHost = document.createElement('div');
  islandsHost.id = 'features-islands';
  islandsHost.className = 'mt-3';
  resultsSection.insertAdjacentElement('afterend', islandsHost);

  // Hide the white card body so only the header bar is visible (no big white block)
  const resultsCardBody = resultsSection.querySelector('.card .card-body');
  if (resultsCardBody) resultsCardBody.style.display = 'none';

  // From here on, use this as the container for per-ID "islands"
  let featuresContainer = islandsHost;

  const spinnerHost = document.getElementById('loading-spinner'); // empty host in the layout
  const alertContainer = document.getElementById('alert-container');
  const downloadBtn = document.getElementById('download-results');

  // Button label fix
  if (processButton) processButton.textContent = 'Process Timeline';

  // Use the server-provided endpoint (avoids path issues with blueprints)
  const POST_URL = window.TIMELINE_TEXT_URL || '/process_timeline_text';

  // Only Excel
  if (fileInput) fileInput.setAttribute('accept', '.xlsx');

  // Prepare spinner host
  while (spinnerHost.firstChild) spinnerHost.removeChild(spinnerHost.firstChild);
  spinnerHost.classList.add('d-none');
  spinnerHost.style.display = 'none';
  spinnerHost.classList.add('d-flex', 'flex-column', 'align-items-center', 'mb-4', 'text-center');

  let selectedFiles = [];

  // Lazy-created spinner bits
  let spinnerIconEl = null;
  let statusLineEl = null;
  let timerLineEl = null;

  function createSpinnerUI() {
    if (!spinnerIconEl) {
      spinnerIconEl = document.createElement('div');
      spinnerIconEl.className = 'spinner-border text-primary';
      spinnerIconEl.setAttribute('role', 'status');
      spinnerHost.appendChild(spinnerIconEl);
    }
    if (!statusLineEl) {
      statusLineEl = document.createElement('p');
      statusLineEl.id = 'processing-status';
      statusLineEl.className = 'mt-2 font-weight-bold';
      spinnerHost.appendChild(statusLineEl);
    }
    if (!timerLineEl) {
      timerLineEl = document.createElement('p');
      timerLineEl.id = 'processing-timer';
      timerLineEl.className = 'mt-1 font-weight-bold';
      spinnerHost.appendChild(timerLineEl);
    }
  }

  // Timer
  let startTime, timerInterval;
  function startTimer() {
    createSpinnerUI();
    spinnerHost.classList.remove('d-none');
    spinnerHost.style.display = 'flex';
    spinnerIconEl.style.display = 'inline-block';
    statusLineEl.style.display = 'block';

    startTime = Date.now();
    timerLineEl.textContent = '⏱️ Total time: 00:00';
    timerInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const mins = Math.floor(elapsed / 60000);
      const secs = Math.floor((elapsed % 60000) / 1000);
      timerLineEl.textContent = `⏱️ Total time: ${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }, 500);
  }
  function stopProcessingUI() {
    if (spinnerIconEl) spinnerIconEl.style.display = 'none';
    if (statusLineEl) { statusLineEl.textContent = ''; statusLineEl.style.display = 'none'; }
    // keep timer visible
  }
  function stopTimer() { clearInterval(timerInterval); }
  function updateStatus(current, total) {
    if (statusLineEl) {
      statusLineEl.textContent = `📄 Processing document ${current} of ${total}`;
    }
  }

  // DnD
  if (fileInput) fileInput.addEventListener('change', () => handleFiles(fileInput.files));
  if (dropzone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt =>
      dropzone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false)
    );
    dropzone.addEventListener('drop', e => handleFiles(e.dataTransfer.files), false);
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.style.cursor = 'pointer';
  }

  function isXlsx(file) {
    const extOk = /\.xlsx$/i.test(file.name || '');
    const mimeOk = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    return extOk || mimeOk;
  }

  function handleFiles(filesList) {
    const files = Array.from(filesList);
    if (files.length && files.every(isXlsx)) {
      selectedFiles = files;
      updateDropzoneUI(files.map(f => f.name).join(', '));
      processButton.disabled = false;
    } else {
      showAlert('Please upload only Excel (.xlsx) files.', 'danger');
    }
  }
  function updateDropzoneUI(txt) {
    const msg = dropzone.querySelector('.dropzone-message');
    if (msg) msg.innerHTML = `<strong>${txt}</strong>`;
  }

  clearButton.addEventListener('click', () => {
    selectedFiles = [];
    if (fileInput) fileInput.value = '';
    featuresContainer.innerHTML = '';
    // keep the "Risultati" header visible; nothing else to toggle
    processButton.disabled = true;

    stopTimer();
    if (statusLineEl) { statusLineEl.textContent = ''; statusLineEl.style.display = 'none'; }
    if (timerLineEl) { timerLineEl.textContent = ''; }
    if (spinnerIconEl) spinnerIconEl.style.display = 'none';
    spinnerHost.classList.add('d-none');
    spinnerHost.style.display = 'none';

    showAlert('All inputs cleared.', 'info');
  });

  // --- helpers for RECIST rendering/export ---
  function isCTEvent(evt) {
    const label = (evt && evt.testo || '').trim().toLowerCase();
    return label === 'tc torace/total body';
  }
  function escapeAttr(s) {
    if (!s) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // --- Compute Best Response (frontend logic) ---
  function computeBestRecist(events) {
    //   const firstLine = events.find(e => e.testo && e.testo.toLowerCase().includes("inizio del trattamento di i linea"));
    //   const secondLine = events.find(e => e.testo && e.testo.toLowerCase().includes("inizio del trattamento di ii linea"));


    //   if (!firstLine) return null;

    //   const startDate = firstLine.data ? new Date(firstLine.data) : null;
    //   const endDate = secondLine && secondLine.data ? new Date(secondLine.data) : null;

    //   if (!startDate || isNaN(startDate)) return null;

    //   const ctEvents = events.filter(e => {
    //     if (!e.testo || !/tc torace|total body/i.test(e.testo)) return false;
    //     const d = e.data ? new Date(e.data) : null;
    //     return d && !isNaN(d) && d >= startDate && (!endDate || d < endDate);
    //   });

    //   if (!ctEvents.length) return null;

    //   // Ranking from best → worst
    //   const priority = { CR: 1, PR: 2, SD: 3, PD: 4, NE: 5 };
    //   const best = ctEvents
    //     .map(e => (e.risposta_recist || '').toUpperCase())
    //     .filter(r => priority[r])
    //     .sort((a, b) => priority[a] - priority[b])[0];

    //   return best ? `Best Response (I line): ${best}` : null;
    // }
    return null;
  }


  // --- render a block ONLY when a result is ready (each in its own "island" card) ---
  function renderResultBlock(label, htmlContent, events) {
    // Outer card as an "island" for this ID
    const outerCard = document.createElement('div');
    outerCard.className = 'card mb-3';

    const cardBody = document.createElement('div');
    cardBody.className = 'card-body';
    outerCard.appendChild(cardBody);

    const title = document.createElement('h5'); // bigger than events
    title.className = 'patient-title font-weight-bold';
    title.style.cursor = 'pointer';
    title.textContent = label || 'Record';

    // --- Compute and show Best Response (I line) ---
    const bestLabel = computeBestRecist(events);
    if (bestLabel) {
      const bestRespWrapper = document.createElement('div');
      bestRespWrapper.style.float = 'right';
      bestRespWrapper.style.display = 'inline-block';

      const bestResp = document.createElement('span');
      bestResp.className = 'badge badge-info align-middle';
      bestResp.textContent = bestLabel;

      bestRespWrapper.appendChild(bestResp);
      title.appendChild(bestRespWrapper);
    }

    const body = document.createElement('div');
    body.className = 'patient-body';
    body.style.display = 'none'; // collapsed by default
    body.innerHTML = htmlContent;
    cardBody.appendChild(title);
    cardBody.appendChild(body);
    featuresContainer.appendChild(outerCard);

    title.addEventListener('click', () => {
      body.style.display = body.style.display === 'block' ? 'none' : 'block';
    });
  }

  processButton.addEventListener('click', async () => {
    if (!selectedFiles.length) {
      showAlert('Please upload at least one Excel (.xlsx) file.', 'danger');
      return;
    }

    // Clear previous islands
    featuresContainer.innerHTML = '';

    // Parse each Excel locally, then stream rows to server
    startTimer();

    let allRows = [];
    for (const file of selectedFiles) {
      const rows = await parseExcelFile(file); // [{id, report}, ...]
      allRows = allRows.concat(rows);
    }

    // Filter out empty reports
    allRows = allRows.filter(r => (r.report || '').trim().length > 0);
    if (!allRows.length) {
      stopProcessingUI();
      stopTimer();
      showAlert('No valid rows found (need columns "id" and "report").', 'warning');
      return;
    }

    const total = allRows.length;
    let completed = 0;

    // STRICTLY SEQUENTIAL: process doc1 → render, then doc2 → render, ...
    // (Set concurrency to 1 by dropping the pool and awaiting each fetch in order)
    for (let i = 0; i < allRows.length; i++) {
      const row = allRows[i];
      const label = (row.id != null && row.id !== '') ? String(row.id) : `Row ${i + 1}`;
      updateStatus(completed + 1, total);

      try {
        const res = await fetch(POST_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: row.id, report: row.report })
        });
        const data = await res.json();

        if (res.ok) {
          const events = Array.isArray(data.features) ? data.features : [];
          if (!events.length) {
            renderResultBlock(label, `<div class="text-muted">No timeline events found.</div>`);
          } else {
            const container = document.createElement('div');
            events.forEach(evt => {
              const item = document.createElement('div');
              item.className = 'feature-item d-flex';

              const lbl = document.createElement('div');
              lbl.className = 'feature-label text-nowrap pr-3';
              lbl.style.width = '15%';
              lbl.textContent = (evt && evt.data) ? String(evt.data) : 'Unknown Date';

              const val = document.createElement('div');
              val.className = 'feature-value';

              const mainText = `<strong>${evt && evt.testo ? escapeAttr(evt.testo) : ''}</strong>`;

              // // 🔹 Add RECIST badge next to CT events
              // let recistBadge = '';
              // if (evt.testo && /tc torace|total body/i.test(evt.testo)) {
              //   const resp = (evt.risposta_recist || '').toUpperCase();
              //   if (resp) {
              //     const cls =
              //       resp === 'CR' ? 'badge badge-success ml-2' :
              //       resp === 'PR' ? 'badge badge-info ml-2' :
              //       resp === 'SD' ? 'badge badge-secondary ml-2' :
              //       resp === 'PD' ? 'badge badge-danger ml-2' :
              //       'badge badge-light ml-2';
              //     recistBadge = `<span class="${cls}">${resp}</span>`;
              //   }
              // }

              // val.innerHTML = `${mainText}${recistBadge}`;
              val.innerHTML = mainText;

              item.append(lbl, val);
              container.appendChild(item);
            });
            renderResultBlock(label, container.innerHTML, events);
          }
        } else {
          renderResultBlock(label, `<div class="text-danger">❌ ${data.error || 'Failed to process'}</div>`);
          showAlert(`${label}: ${data.error || 'Failed to process'}`, 'danger');
        }
      } catch (err) {
        console.error('Network/JS error', err);
        renderResultBlock(label, `<div class="text-danger">❌ Network error</div>`);
        showAlert(`${label}: Network error`, 'danger');
      } finally {
        completed += 1;
        updateStatus(completed, total);
      }
    }

    // Done: hide spinner + processing line, keep timer
    stopProcessingUI();
    stopTimer();
  });

  function showAlert(msg, type = 'info') {
    alertContainer.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
    setTimeout(() => { alertContainer.innerHTML = ''; }, 5000);
  }

  // Parse .xlsx → [{ id, report }]
  function parseExcelFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = e => {
        try {
          const data = new Uint8Array(e.target.result);
          const wb = XLSX.read(data, { type: 'array' });
          const sheet = wb.Sheets[wb.SheetNames[0]];
          if (!sheet) return resolve([]);

          // Convert to array of objects (keeps header names)
          const raw = XLSX.utils.sheet_to_json(sheet, { defval: '' });
          // If the first row is just a single cell (model name), remove it
          if (raw.length && Object.keys(raw[0]).length === 1) {
            console.log("🧩 Skipping first row (model name):", Object.values(raw[0])[0]);
            raw.shift();
          }

          const rows = raw.map((row, i) => {
            // Case-insensitive field access
            const lowerMap = {};
            Object.keys(row).forEach(k => lowerMap[k.toLowerCase().trim()] = row[k]);

            const id = (lowerMap['id'] ?? lowerMap['patient'] ?? lowerMap['#'] ?? `Row ${i + 1}`);
            const report = (lowerMap['report'] ?? lowerMap['text'] ?? '');

            return { id: String(id), report: String(report) };
          });

          resolve(rows);
        } catch (err) {
          reject(err);
        }
      };
      reader.readAsArrayBuffer(file);
    });
  }

  // --- Export to Excel (UPDATED: add RECIST fields for TC rows) ---
  function normalizeDateForExport(s) {
    // backend already returns YYYY-MM-DD; keep a gentle fallback
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    return s || '';
  }

  downloadBtn.addEventListener('click', async () => {
    // Collect all events from the rendered cards
    const data = [];
    islandsHost.querySelectorAll('.card').forEach(pb => {
      // Extract only the numeric ID (remove Best Response text if present)
      const titleText = pb.querySelector('.patient-title').textContent.trim();
      const pidMatch = titleText.match(/^\d+/);
      const pid = pidMatch ? pidMatch[0] : titleText;

      pb.querySelectorAll('.feature-item').forEach(fi => {
        const dateTxt = fi.querySelector('.feature-label').textContent.trim();
        const eventEl = fi.querySelector('.feature-value');
        const strongEl = eventEl.querySelector('strong');
        const eventTxt = strongEl ? strongEl.textContent.trim() : eventEl.textContent.trim();

        //const recistBadge = eventEl.querySelector('.badge');
        //const risposta_recist = recistBadge ? (recistBadge.textContent || '').trim().toUpperCase() : '';

        data.push({
          id: pid,
          data: normalizeDateForExport(dateTxt),
          testo: eventTxt,
          //risposta_recist: risposta_recist || ''
        });
      });
    });

    // --- Inject model name (first row) ---
    let modelName = 'unknown_model';
    try {
      // Ask the backend for the active model in config.json
      const res = await fetch('/api/settings', { cache: 'no-store' });
      if (res.ok) {
        const cfg = await res.json();
        if (cfg && cfg.LLM_MODEL) modelName = cfg.LLM_MODEL;
      }
    } catch (e) {
      console.warn('⚠️ Could not fetch model name from /api/settings:', e);
    }

    // --- Create workbook ---
    const wb = XLSX.utils.book_new();
    //const headers = ['id','data','testo','risposta_recist'];
    const headers = ['id', 'data', 'testo'];

    // Row 1: model name; Row 2: headers
    const ws = XLSX.utils.aoa_to_sheet([[modelName], headers]);

    // Data starts at A3; do NOT write headers again
    XLSX.utils.sheet_add_json(ws, data, {
      header: headers,
      skipHeader: true,
      origin: 'A3'
    });

    XLSX.utils.book_append_sheet(wb, ws, 'Timelines');
    XLSX.writeFile(wb, 'timelines.xlsx');
  });
});