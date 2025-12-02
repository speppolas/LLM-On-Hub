// TIMELINE EVALUATION (frontend-only)
document.addEventListener("DOMContentLoaded", function () {
  // ---- Elements (uploads) ----
  const predDropzone = document.getElementById("dropzone-pred");
  const predInput = document.getElementById("pred-input");
  const gtDropzone = document.getElementById("dropzone-gt");
  const gtInput = document.getElementById("gt-input");

  // ---- Controls / containers ----
  const evalBtn = document.getElementById("evaluate-button");
  const evalSpinner = document.getElementById("eval-loading-spinner");
  const resultsWrap = document.getElementById("eval-results-section");
  const overallBox = document.getElementById("overall-metrics");
  const overallAvgTbody = document.getElementById("overall-avg-tbody");
  const tableElem = document.getElementById("per-event-table").querySelector("tbody");
  const metricSelect = document.getElementById("metric-select");
  const dlEvalBtn = document.getElementById("download-eval");
  const alertContainer = document.getElementById("alert-container");

  // ---- Download mode state ----
  let currentMode = "predictions";   // "predictions" | "models"
  let lastModelsData = [];           // cache for the heatmap
  let modelName = "";                // filled from /api/settings
  let modelNamePred = "";            // extracted from uploaded predictions file

  // ---- RECIST helpers (NEW) ----
  const RECIST_LABELS = ["CR", "PR", "SD", "PD", "NE"];
  let recistMatches = []; // { gt: "CR|PR|SD|PD|NE", pred: "CR|PR|SD|PD|NE" }

  function computeRecistMetrics(matches) {
    const cm = {}; RECIST_LABELS.forEach(gt => { cm[gt] = {}; RECIST_LABELS.forEach(pr => cm[gt][pr] = 0); });
    matches.forEach(m => {
      const gt = RECIST_LABELS.includes(m.gt) ? m.gt : "NE";
      const pr = RECIST_LABELS.includes(m.pred) ? m.pred : "NE";
      cm[gt][pr] += 1;
    });
    const perClass = RECIST_LABELS.map(lbl => {
      const tp = cm[lbl][lbl];
      const fp = RECIST_LABELS.reduce((a, x) => a + cm[x][lbl], 0) - tp;
      const fn = RECIST_LABELS.reduce((a, x) => a + cm[lbl][x], 0) - tp;
      const m = computeMetrics(tp, fp, fn);
      return { label: lbl, tp, fp, fn, precision: m.precision, recall: m.recall, accuracy: m.accuracy, f1: m.f1, support: tp + fn };
    });

    const valid = perClass.filter(r => r.support > 0);
    const tot = valid.reduce((a, r) => a + r.support, 0);

    const macro = {
      precision: valid.length ? valid.reduce((a, r) => a + r.precision, 0) / valid.length : 0,
      recall: valid.length ? valid.reduce((a, r) => a + r.recall, 0) / valid.length : 0,
      accuracy: valid.length ? valid.reduce((a, r) => a + r.accuracy, 0) / valid.length : 0,
      f1: valid.length ? valid.reduce((a, r) => a + r.f1, 0) / valid.length : 0
    };

    const microTP = valid.reduce((a, r) => a + r.tp, 0);
    const microFP = valid.reduce((a, r) => a + r.fp, 0);
    const microFN = valid.reduce((a, r) => a + r.fn, 0);
    const microM = computeMetrics(microTP, microFP, microFN);

    const weighted = {
      precision: tot ? valid.reduce((a, r) => a + r.precision * r.support, 0) / tot : 0,
      recall: tot ? valid.reduce((a, r) => a + r.recall * r.support, 0) / tot : 0,
      accuracy: tot ? valid.reduce((a, r) => a + r.accuracy * r.support, 0) / tot : 0,
      f1: tot ? valid.reduce((a, r) => a + r.f1 * r.support, 0) / tot : 0
    };

    return { confusion: cm, perClass, macro, micro: microM, weighted };
  }

  function renderRecistResults(metrics) {
    // clear previous
    const summaryHost = document.getElementById("recist-summary");
    const matrixHost = document.getElementById("recist-matrix");
    const perclassHost = document.getElementById("recist-perclass");
    if (!summaryHost || !matrixHost || !perclassHost) return;

    summaryHost.innerHTML = "";
    matrixHost.innerHTML = "";
    perclassHost.innerHTML = "";

    const confMatrix = metrics.confusion;
    const perClass = metrics.perClass;

    // === Overall averages (macro/micro/weighted) ===
    const valid = perClass.filter(r => r.support > 0);
    const tot = valid.reduce((a, r) => a + r.support, 0);

    const macro = {
      precision: valid.length ? valid.reduce((a, r) => a + r.precision, 0) / valid.length : 0,
      recall: valid.length ? valid.reduce((a, r) => a + r.recall, 0) / valid.length : 0,
      accuracy: valid.length ? valid.reduce((a, r) => a + r.accuracy, 0) / valid.length : 0,
      f1: valid.length ? valid.reduce((a, r) => a + r.f1, 0) / valid.length : 0
    };
    const micro = {
      precision: perClass.reduce((a, r) => a + r.tp, 0) / Math.max(1, perClass.reduce((a, r) => a + r.tp + r.fp, 0)),
      recall: perClass.reduce((a, r) => a + r.tp, 0) / Math.max(1, perClass.reduce((a, r) => a + r.tp + r.fn, 0)),
      accuracy: perClass.reduce((a, r) => a + r.tp, 0) / Math.max(1, perClass.reduce((a, r) => a + r.tp + r.fp + r.fn, 0)),
      f1: 0
    };
    micro.f1 = (micro.precision + micro.recall) ? (2 * micro.precision * micro.recall / (micro.precision + micro.recall)) : 0;

    const weighted = {
      precision: tot ? valid.reduce((a, r) => a + r.precision * r.support, 0) / tot : 0,
      recall: tot ? valid.reduce((a, r) => a + r.recall * r.support, 0) / tot : 0,
      accuracy: tot ? valid.reduce((a, r) => a + r.accuracy * r.support, 0) / tot : 0,
      f1: tot ? valid.reduce((a, r) => a + r.f1 * r.support, 0) / tot : 0
    };

    const rows = [
      ["Macro avg", dec(macro.accuracy), dec(macro.precision), dec(macro.recall), dec(macro.f1)],
      ["Micro avg", dec(micro.accuracy), dec(micro.precision), dec(micro.recall), dec(micro.f1)],
      ["Weighted avg", dec(weighted.accuracy), dec(weighted.precision), dec(weighted.recall), dec(weighted.f1)]
    ];
    summaryHost.innerHTML = rows.map(r =>
      `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td>${r[4]}</td></tr>`
    ).join("");


    // === Confusion Matrix as square heatmap ===
    const labels = Object.keys(confMatrix);
    const xLabels = [...labels].reverse();
    const data = [];
    const maxVal = Math.max(...labels.flatMap(gt => labels.map(pred => confMatrix[gt][pred] || 0)));

    labels.forEach(gt => {
      labels.forEach(pred => {
        data.push({ x: pred, y: gt, v: confMatrix[gt][pred] || 0 });
      });
    });

    const canvas = document.createElement("canvas");
    canvas.style.maxWidth = "400px";   // 👈 shrink canvas width
    canvas.style.maxHeight = "400px";  // 👈 shrink canvas height
    matrixHost.appendChild(canvas);

    new Chart(canvas, {
      type: 'matrix',
      data: {
        datasets: [{
          label: "Confusion Matrix",
          data,
          backgroundColor(ctx) {
            const raw = ctx.raw || {};
            const v = raw.v ?? 0;
            const intensity = maxVal > 0 ? v / maxVal : 0;
            return `hsl(200, 70%, ${100 - intensity * 50}%)`;
          },
          borderWidth: 1,
          borderColor: "#999",
          width(ctx) {
            const area = ctx.chart.chartArea;
            if (!area) return 20;
            const cell = Math.floor(Math.min(area.width, area.height) / labels.length) - 6;
            return Math.max(cell, 10);
          },
          height(ctx) {
            const area = ctx.chart.chartArea;
            if (!area) return 20;
            const cell = Math.floor(Math.min(area.width, area.height) / labels.length) - 6;
            return Math.max(cell, 10);
          }
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1,
        scales: {
          x: {
            type: 'category',
            labels: xLabels,
            offset: true,
            grid: { drawTicks: false, color: "#ccc" },
            title: { display: true, text: "Predicted" }
          },
          y: {
            type: 'category',
            labels,
            offset: true,
            grid: { drawTicks: false, color: "#ccc" },
            title: { display: true, text: "Ground Truth" }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(ctx) {
                const { x, y, v } = ctx.raw || {};
                return `GT: ${y}, Pred: ${x}, Count: ${v}`;
              }
            }
          },
          datalabels: {
            display: true,
            color: '#000',
            font: { weight: 'bold', size: 14 },
            formatter: (value, ctx) => {
              const { x, y, v } = ctx.dataset.data[ctx.dataIndex];
              const gtLabel = y;
              const rowTotal = Object.values(confMatrix[gtLabel] || {}).reduce((a, b) => a + b, 0);
              if (!rowTotal) return "0.0";
              const norm = v / rowTotal;
              return norm.toFixed(2);
            }
          }
        }
      },
      plugins: [ChartDataLabels]
    });

    // === Per-label metrics ===
    perclassHost.innerHTML = perClass.map(m =>
      `<tr>
        <td>${m.label}</td>
        <td>${dec(m.accuracy)}</td>
        <td>${dec(m.precision)}</td>
        <td>${dec(m.recall)}</td>
        <td>${dec(m.f1)}</td>
      </tr>`
    ).join("");
  }

  // ---- extend Excel export ----
  function downloadEvaluation(overall, perEventRows) {
    const rows = [];
    // Prefer model name read from uploaded predictions; fallback to system one
    const usedModelName = modelNamePred || modelName || "";
    rows.push([usedModelName]);

    rows.push(["TIMELINE OVERALL AVERAGES"]);
    rows.push(["Metric", "Accuracy", "Precision", "Recall", "F1-Score"]);
    const valid = perEventRows.filter(r => r.support > 0);
    const tot = valid.reduce((a, r) => a + r.support, 0);
    const macro = {
      precision: valid.length ? valid.reduce((a, r) => a + r.precision, 0) / valid.length : 0,
      recall: valid.length ? valid.reduce((a, r) => a + r.recall, 0) / valid.length : 0,
      accuracy: valid.length ? valid.reduce((a, r) => a + r.accuracy, 0) / valid.length : 0,
      f1: valid.length ? valid.reduce((a, r) => a + r.f1, 0) / valid.length : 0
    };

    const overallAcc = (overall.tp + overall.fp + overall.fn)
      ? (overall.tp / (overall.tp + overall.fp + overall.fn))
      : 0;

    const micro = {
      precision: overall.precision,
      recall: overall.recall,
      accuracy: overallAcc,
      f1: overall.f1
    };
    const weighted = {
      precision: tot ? valid.reduce((a, r) => a + r.precision * r.support, 0) / tot : 0,
      recall: tot ? valid.reduce((a, r) => a + r.recall * r.support, 0) / tot : 0,
      accuracy: tot ? valid.reduce((a, r) => a + r.accuracy * r.support, 0) / tot : 0,
      f1: tot ? valid.reduce((a, r) => a + r.f1 * r.support, 0) / tot : 0
    };
    rows.push(["Macro avg overall", +macro.accuracy.toFixed(4), +macro.precision.toFixed(4), +macro.recall.toFixed(4), +macro.f1.toFixed(4)]);
    rows.push(["Micro avg overall", +micro.accuracy.toFixed(4), +micro.precision.toFixed(4), +micro.recall.toFixed(4), +micro.f1.toFixed(4)]);
    rows.push(["Weighted avg overall", +weighted.accuracy.toFixed(4), +weighted.precision.toFixed(4), +weighted.recall.toFixed(4), +weighted.f1.toFixed(4)]);
    rows.push([]);

    rows.push(["TIMELINE PER-EVENT METRICS"]);
    rows.push(["Event", "TP", "FP", "FN", "Support", "Accuracy", "Precision", "Recall", "F1-Score"]);
    perEventRows.forEach(r => {
      rows.push([r.event, r.tp, r.fp, r.fn, r.support,
      +r.accuracy.toFixed(4), +r.precision.toFixed(4), +r.recall.toFixed(4), +r.f1.toFixed(4)]);
    });
    rows.push([]);

    // ---- RECIST export (if available) ----
    if (recistMatches.length) {
      const recistMetrics = computeRecistMetrics(recistMatches);

      // RECIST AVERAGES
      rows.push(["RECIST OVERALL AVERAGES"]);
      rows.push(["Metric", "Accuracy", "Precision", "Recall", "F1-Score"]);
      rows.push(["Macro avg", +recistMetrics.macro.accuracy.toFixed(4), +recistMetrics.macro.precision.toFixed(4), +recistMetrics.macro.recall.toFixed(4), +recistMetrics.macro.f1.toFixed(4)]);
      rows.push(["Micro avg", +recistMetrics.micro.accuracy.toFixed(4), +recistMetrics.micro.precision.toFixed(4), +recistMetrics.micro.recall.toFixed(4), +recistMetrics.micro.f1.toFixed(4)]);
      rows.push(["Weighted avg", +recistMetrics.weighted.accuracy.toFixed(4), +recistMetrics.weighted.precision.toFixed(4), +recistMetrics.weighted.recall.toFixed(4), +recistMetrics.weighted.f1.toFixed(4)]);
      rows.push([]);

      // RECIST PER-CLASS
      rows.push(["RECIST PER-CLASS METRICS"]);
      rows.push(["Label", "Accuracy", "Precision", "Recall", "F1-Score", "Support"]);
      recistMetrics.perClass.forEach(m => {
        rows.push([m.label,
        +m.accuracy.toFixed(4),
        +m.precision.toFixed(4),
        +m.recall.toFixed(4),
        +m.f1.toFixed(4),
        m.support]);
      });
      rows.push([]);
    }

    const ws = XLSX.utils.aoa_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "evaluation");
    XLSX.writeFile(wb, "timeline_evaluation.xlsx");
  }

  // ---- Across-models panel elements ----
  const modelsDropzone = document.getElementById("dropzone-models");     // multiple files
  const modelsInput = document.getElementById("models-input");        // <input type="file" multiple accept=".xlsx">
  const evalModelsBtn = document.getElementById("evaluate-models-button");
  const modelsWrap = document.getElementById("models-results-section"); // container for heatmap
  const modelsMetricSel = document.getElementById("models-metric-select");   // dropdown: accuracy|precision|recall|f1
  const heatmapHost = document.getElementById("models-heatmap");         // empty div where we render

  let modelFiles = []; // holds 2..4 XLSX files

  // ---- UX helpers ----
  function showAlert(msg, type = 'info', ttl = 5000) {
    if (!alertContainer) { alert(msg); return; }
    alertContainer.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
    if (ttl) setTimeout(() => { alertContainer.innerHTML = ''; }, ttl);
  }
  const showSpinner = () => evalSpinner.classList.remove("d-none");
  const hideSpinner = () => evalSpinner.classList.add("d-none");
  const showResults = () => resultsWrap.classList.remove("d-none");
  function clearResults() {
    if (overallBox) overallBox.innerHTML = "";
    if (overallAvgTbody) overallAvgTbody.innerHTML = "";
    tableElem.innerHTML = "";
    destroyChart();
    recistMatches = []; // reset RECIST matches
    const recistHost = document.getElementById("recist-results");
    if (recistHost) recistHost.innerHTML = ""; // clear RECIST results too
  }

  // ---- Dropzones ----
  let predFile = null, gtFile = null;

  function wireDropzone(zone, input, setter) {
    if (!zone || !input) return;
    zone.addEventListener("click", () => input.click());
    ["dragenter", "dragover", "dragleave", "drop"].forEach(evt =>
      zone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false)
    );
    zone.addEventListener("drop", e => {
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) setter(f);
    });
    input.addEventListener("change", e => {
      const f = e.target.files && e.target.files[0];
      if (f) setter(f);
    });
  }

  function setPredFile(file) {
    predFile = file;
    predDropzone.classList.add("dropzone-success");
    const msg = predDropzone.querySelector(".dropzone-message");
    if (msg) msg.textContent = file.name;
  }
  function setGtFile(file) {
    gtFile = file;
    gtDropzone.classList.add("dropzone-success");
    const msg = gtDropzone.querySelector(".dropzone-message");
    if (msg) msg.textContent = file.name;
  }

  wireDropzone(predDropzone, predInput, setPredFile);
  wireDropzone(gtDropzone, gtInput, setGtFile);

  // ---- Parsing helpers (CSV/XLSX via SheetJS) ----
  async function readFileToArrayBuffer(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onerror = () => reject(new Error("File read error"));
      r.onload = () => resolve(r.result);
      r.readAsArrayBuffer(file);
    });
  }

  function sheetToJsonRows(wb) {
    const sheetName = wb.SheetNames[0];
    const sheet = wb.Sheets[sheetName];
    if (!sheet) return [];

    // Read the full sheet as 2D array (rows)
    const allRows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '', raw: false });
    // 👇 Capture the model name from the first non-empty row (even if extra spaces or hidden chars)
    if (allRows.length && allRows[0].length >= 1) {
      const firstCell = String(allRows[0][0] || "").trim();
      if (firstCell && !firstCell.toLowerCase().includes("id")) {
        modelNamePred = firstCell;
        ("📦 Detected model name from predictions file:", modelNamePred);
      }
    }
    if (!allRows.length) return [];

    // 🔍 Find the header row — where we have all the expected columns
    const expectedHeaders = ["id", "data", "testo", "risposta_recist"];
    let headerIndex = -1;

    for (let i = 0; i < allRows.length; i++) {
      const rowLower = allRows[i].map(x => String(x).toLowerCase().trim());
      if (expectedHeaders.every(h => rowLower.includes(h))) {
        headerIndex = i;
        break;
      }
    }

    if (headerIndex === -1) {
      console.warn("⚠️ No valid header row found in Excel file.");
      return [];
    }

    const header = allRows[headerIndex];
    const body = allRows.slice(headerIndex + 1);

    // Convert remaining rows to JSON objects
    const cleanRows = body.map(row => {
      const obj = {};
      header.forEach((h, i) => {
        obj[h] = row[i] ?? '';
      });
      return obj;
    });

    return cleanRows;
  }

  async function parseAnyFile(file) {
    const buf = await readFileToArrayBuffer(file);
    const wb = XLSX.read(buf, { type: "array" });
    const rows = sheetToJsonRows(wb);
    return normalizeRows(rows);
  }

  // ---- Show/hide sections depending on the mode ----
  function showPredictionsUI() {
    if (resultsWrap) resultsWrap.classList.remove("d-none");
    if (modelsWrap) modelsWrap.classList.add("d-none");
  }
  function showModelsUI() {
    if (resultsWrap) resultsWrap.classList.add("d-none");
    if (modelsWrap) modelsWrap.classList.remove("d-none");
  }

  // ---- Dropzone for models comparison ----
  function setModelFiles(files) {
    modelFiles = files.slice(0, 4); // cap to 4
    if (modelsDropzone) {
      modelsDropzone.classList.toggle("dropzone-success", modelFiles.length > 0);
      const msg = modelsDropzone.querySelector(".dropzone-message");
      if (msg) msg.textContent = modelFiles.length ? modelFiles.map(f => f.name).join(", ") : "Drag & drop up to 4 files";
    }
  }

  if (modelsDropzone && modelsInput) {
    ["dragenter", "dragover", "dragleave", "drop"].forEach(evt =>
      modelsDropzone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false)
    );
    modelsDropzone.addEventListener("click", () => modelsInput.click());
    modelsDropzone.addEventListener("drop", e => {
      const files = Array.from(e.dataTransfer.files || []).filter(f => /\.xlsx$/i.test(f.name));
      setModelFiles(files);
    });
    modelsInput.addEventListener("change", e => {
      const files = Array.from(e.target.files || []).filter(f => /\.xlsx$/i.test(f.name));
      setModelFiles(files);
    });
  }

  // ---- Normalize rows (expect: id, data, testo, risposta_recist?) ----
  function normalizeRows(rawRows) {
    const out = [];
    for (let i = 0; i < rawRows.length; i++) {
      const row = rawRows[i] || {};
      const lower = {};
      Object.keys(row).forEach(k => lower[k.toLowerCase().trim()] = row[k]);

      const id = (lower["id"] ?? "").toString().trim();
      const testo = (lower["testo"] ?? "").toString().trim();
      let data = (lower["data"] ?? "").toString().trim();
      const risposta_recist = (lower["risposta_recist"] ?? "").toString().trim(); // may be empty

      if (!id || !testo) continue;
      data = normalizeDate(data);
      out.push({ id, data, testo, risposta_recist });
    }
    return out;
  }
  function normalizeDate(s) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

    // Excel serial?
    const asNum = Number(s);
    if (!isNaN(asNum) && asNum > 59 && asNum < 60000 && XLSX.SSF) {
      const dc = XLSX.SSF.parse_date_code(asNum);
      if (dc) return pad(dc.y, 4) + "-" + pad(dc.m, 2) + "-" + pad(dc.d, 2);
    }
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      return [d.getFullYear(), pad(d.getMonth() + 1, 2), pad(d.getDate(), 2)].join("-");
    }
    return s;
  }
  const pad = (n, w) => (String(n).length >= w ? String(n) : "0".repeat(w - String(n).length) + n);
  const normId = v => String(v ?? '').trim();

  // ---- Month-level key helpers ----
  function monthKeyFromDate(isoOrAny) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(isoOrAny)) return isoOrAny.slice(0, 7);
    const d = new Date(isoOrAny);
    if (!isNaN(d.getTime())) return `${d.getFullYear()}-${pad(d.getMonth() + 1, 2)}`;
    const m = /(\d{4})[-/\.](\d{1,2})/.exec(isoOrAny);
    if (m) return `${m[1]}-${pad(+m[2], 2)}`;
    return isoOrAny;
  }
  function monthToInt(ym) {
    // ym like "YYYY-MM"
    const m = /^(\d{4})-(\d{2})$/.exec(ym);
    if (!m) return NaN;
    return (+m[1]) * 12 + (+m[2]) - 1; // 0-based month index
  }

  // ---- (optional) Old DOM predictions fallback ----
  function collectPredictionsFromDOM() {
    const host = document.getElementById("features-islands") || document.getElementById("features-container");
    if (!host) return [];
    const blocks = host.querySelectorAll(".patient-block");
    const preds = [];
    blocks.forEach(block => {
      const titleEl = block.querySelector(".patient-title");
      const id = titleEl ? titleEl.textContent.trim() : "";
      if (!id) return;
      block.querySelectorAll(".feature-item").forEach(fi => {
        const dateEl = fi.querySelector(".feature-label");
        const eventEl = fi.querySelector(".feature-value");
        const data = dateEl ? dateEl.textContent.trim() : "";
        const testo = eventEl ? eventEl.textContent.trim() : "";
        if (data && testo) preds.push({ id, data: normalizeDate(data), testo, risposta_recist: "" });
      });
    });
    return preds;
  }

  // ---- Metrics helpers ----
  function computeMetrics(tp, fp, fn) {
    const precision = (tp + fp) ? (tp / (tp + fp)) : 0;
    const recall = (tp + fn) ? (tp / (tp + fn)) : 0;
    const accuracy = (tp + fp + fn) ? (tp / (tp + fp + fn)) : 0;   // positive-class accuracy
    const f1 = (precision + recall) ? (2 * precision * recall / (precision + recall)) : 0;
    return { precision, recall, accuracy, f1, support: tp + fn };
  }
  const pct = x => (x * 100).toFixed(1) + "%";
  const dec = x => (isFinite(x) ? x : 0).toFixed(4);

  // ---- Chart.js bits ----
  function shortLabel(original) {
    if (!original) return original;
    const s = original.toLowerCase();
    if (s.includes("biopsia")) return "Biopsia";
    if (s.includes("diagnosi")) return "Diagnosi";
    if (s.includes("discontinuit")) return "Discontinuità";
    if (s.includes(" i linea") || s.includes(" i°") || s.includes(" 1°")) return "I linea";
    if (s.includes(" ii linea") || s.includes(" ii°") || s.includes(" 2°")) return "II linea";
    if (s.includes(" iii linea") || s.includes(" iii°") || s.includes(" 3°")) return "III linea";
    if (s.includes("tc") || s.includes("tac")) return "TC";
    return original;
  }

  let barChart = null;
  function destroyChart() {
    if (barChart) { barChart.destroy(); barChart = null; }
  }

  function renderChart(perEventRows, metric = "f1") {
    const labels = perEventRows.map(r => shortLabel(r.event));
    const values = perEventRows.map(r =>
      metric === "precision" ? r.precision :
        metric === "recall" ? r.recall :
          metric === "accuracy" ? r.accuracy : r.f1
    );

    const ctx = document.getElementById("per-event-chart");

    if (barChart) {
      barChart.data.labels = labels;
      barChart.data.datasets[0].label = metric.toUpperCase();
      barChart.data.datasets[0].data = values;
      barChart.options.animation = false;
      barChart.update('none');
      return;
    }

    barChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: metric.toUpperCase(), data: values }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${(c.raw * 100).toFixed(1)}%` } }
        },
        layout: { padding: { top: 10, right: 10, bottom: 10, left: 10 } },
        scales: {
          x: {
            ticks: { font: { size: 14, weight: '600' }, maxRotation: 0, autoSkip: false }
          },
          y: { beginAtZero: true, max: 1 }
        }
      }
    });
  }

  // ---- Heatmap helpers ----
  function colorForValue(v) {
    const clamped = Math.max(0, Math.min(1, v || 0));
    const hue = clamped * 120;
    return `hsl(${hue}, 65%, 55%)`;
  }

  function prettyEventLabel(original) {
    if (!original) return original;
    const s = original.toLowerCase();

    if (s.includes("evidenze di discontinuit")) return "Discontinuità";
    if (s.includes("avvio del trattamento di iii linea")) return "Avvio III linea";
    if (s.includes("inizio del trattamento di i linea")) return "Inizio I linea";
    if (s.includes("inizio del trattamento di ii linea")) return "Inizio II linea";
    if (s.includes("inizio del trattamento di iii linea")) return "Inizio III linea";
    if (s.includes("biopsia") || s.includes("agobiopsia")) return "Biopsia/Agobiopsia";
    if (s.includes("diagnosi")) return "Diagnosi";
    if (s.includes("tc") && s.includes("torace")) return "TC torace/total body";

    return original;
  }

  function renderModelsHeatmap(modelsData, metricKey = "f1") {
    if (!heatmapHost) return;
    heatmapHost.innerHTML = "";

    // === Build full event list + add RECIST column ===
    const allEvents = Array.from(new Set(
      modelsData.flatMap(m => m.events.map(e => e.event))
    ))
      .sort((a, b) => a.localeCompare(b, 'it', { sensitivity: 'base' }));

    allEvents.push("Risposta RECIST");  // 👈 Add extra column

    const table = document.createElement("table");
    table.className = "table table-sm table-bordered mb-0";

    const thead = document.createElement("thead");
    thead.className = "thead-light";
    const htr = document.createElement("tr");

    // use pretty labels in the header only
    const displayEvents = allEvents.map(prettyEventLabel);
    htr.innerHTML =
      `<th>Model \\ Event</th>` +
      displayEvents.map(ev => `<th>${escapeHtml(ev)}</th>`).join("");

    thead.appendChild(htr);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    modelsData.forEach(m => {
      const tr = document.createElement("tr");
      const nameCell = document.createElement("td");
      nameCell.innerHTML = `<strong>${escapeHtml(m.model)}</strong>`;
      tr.appendChild(nameCell);

      // --- regular events ---
      allEvents.forEach(ev => {
        const td = document.createElement("td");

        if (ev === "Risposta RECIST") {
          // show weighted RECIST metric
          const recVal = m.recist && m.recist[metricKey] ? m.recist[metricKey] : 0;
          td.textContent = recVal.toFixed(4);
          td.style.background = colorForValue(recVal);
        } else {
          const found = m.events.find(x => x.event === ev) || {};
          const val = Number(found[metricKey]) || 0;
          td.textContent = (isFinite(val) ? val : 0).toFixed(4);
          td.style.background = colorForValue(val);
        }

        td.style.color = "#fff";
        td.style.textAlign = "center";
        td.style.fontWeight = "600";
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    heatmapHost.appendChild(table);
    lastModelsData = modelsData;
    drawHeatmapCanvas(modelsData, metricKey);
  }

  const escapeHtml = s => (s || "").replace(/[&<>"']/g, m => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
  ));

  // draw the same values onto a canvas for PNG download
  function drawHeatmapCanvas(modelsData, metricKey = "f1") {
    const allEvents = Array.from(new Set(
      modelsData.flatMap(m => m.events.map(e => e.event))
    ))
      .sort((a, b) => a.localeCompare(b, 'it', { sensitivity: 'base' }));

    allEvents.push("Risposta RECIST");  // 👈 include RECIST column in image
    const displayEvents = allEvents.map(prettyEventLabel);

    const cellW = 180, cellH = 28, pad = 8;
    const headerH = 64, rowLabelW = 180;

    const width = rowLabelW + allEvents.length * cellW + pad * 2;
    const height = headerH + modelsData.length * cellH + pad * 2;

    let canvas = document.getElementById("models-heatmap-canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.id = "models-heatmap-canvas";
      canvas.style.display = "none";
      if (heatmapHost) heatmapHost.appendChild(canvas);
    }
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.font = "12px Roboto, Arial, sans-serif";
    const headerFont = "13px Roboto, Arial, sans-serif";
    const bodyFont = "12px Roboto, Arial, sans-serif";
    ctx.font = headerFont;
    ctx.textBaseline = "middle";

    function wrapIntoLines(ctx, text, maxWidth) {
      const words = String(text).split(/\s+/);
      const lines = [];
      let cur = "";
      words.forEach(w => {
        const test = cur ? cur + " " + w : w;
        if (ctx.measureText(test).width <= maxWidth || !cur) {
          cur = test;
        } else {
          lines.push(cur);
          cur = w;
        }
      });
      if (cur) lines.push(cur);
      return lines.slice(0, 3);
    }

    ctx.fillStyle = "#333";
    ctx.textAlign = "start";
    ctx.fillText("Model \\ Event", pad, pad + 14);

    const lineH = 16;
    allEvents.forEach((ev, j) => {
      const xLeft = pad + rowLabelW + j * cellW;
      const lines = wrapIntoLines(ctx, displayEvents[j], cellW - 12);
      const totalH = lines.length * lineH;
      let y = pad + (headerH - totalH) / 2 + 10;
      ctx.textAlign = "center";
      lines.forEach(line => {
        ctx.fillText(line, xLeft + cellW / 2, y);
        y += lineH;
      });
      ctx.textAlign = "start";
    });

    ctx.font = bodyFont;
    modelsData.forEach((m, i) => {
      const yTop = pad + headerH + i * cellH;
      ctx.fillStyle = "#000";
      ctx.fillText(m.model, pad, yTop + cellH / 2);

      allEvents.forEach((ev, j) => {
        const xLeft = pad + rowLabelW + j * cellW;
        let v = 0;

        if (ev === "Risposta RECIST") {
          v = m.recist && m.recist[metricKey] ? m.recist[metricKey] : 0;
        } else {
          const found = m.events.find(x => x.event === ev) || {};
          v = Number(found[metricKey]) || 0;
        }

        ctx.fillStyle = colorForValue(v);
        ctx.fillRect(xLeft + 1, yTop + 1, cellW - 2, cellH - 2);

        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.fillText((isFinite(v) ? v : 0).toFixed(4), xLeft + cellW / 2, yTop + cellH / 2);
        ctx.textAlign = "start";
      });
    });
  }

  async function downloadHeatmap() {
    if (!lastModelsData.length) {
      showAlert("No heatmap data to download.", "warning");
      return;
    }
    const metrics = ["accuracy", "precision", "recall", "f1"];
    const zip = new JSZip();

    for (const metric of metrics) {
      drawHeatmapCanvas(lastModelsData, metric);
      const canvas = document.getElementById("models-heatmap-canvas");
      const dataURL = canvas.toDataURL("image/png");
      const base64Data = dataURL.split(",")[1];
      zip.file(`heatmap_${metric}.png`, base64Data, { base64: true });
    }
    const blob = await zip.generateAsync({ type: "blob" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "models_heatmaps.zip";
    link.click();
  }

  // ---- Evaluate (±1 month tolerance ALWAYS ON) ----
  evalBtn.addEventListener("click", async () => {
    try {
      clearResults();
      if (!predFile) {
        const fallback = collectPredictionsFromDOM();
        if (!fallback.length) {
          showAlert("⚠️ Please upload a Predictions file (CSV/XLSX) exported from Timeline Extraction.", "warning");
          return;
        }
      }
      if (!gtFile) {
        showAlert("⚠️ Please upload a Ground Truth file.", "warning");
        return;
      }

      showSpinner();

      let predsAll = [];
      if (predFile) {
        predsAll = (await parseAnyFile(predFile)).map(r => ({ id: normId(r.id), data: r.data, testo: r.testo, risposta_recist: (r.risposta_recist || "").toString().trim() }));
      } else {
        predsAll = collectPredictionsFromDOM().map(r => ({ id: normId(r.id), data: r.data, testo: r.testo, risposta_recist: (r.risposta_recist || "").toString().trim() }));
      }
      if (!predsAll.length) {
        showAlert("⚠️ Predictions appear empty or invalid.", "warning");
        return;
      }

      const gtAll = (await parseAnyFile(gtFile)).map(r => ({ id: normId(r.id), data: r.data, testo: r.testo, risposta_recist: (r.risposta_recist || "").toString().trim() }));
      if (!gtAll.length) {
        showAlert("⚠️ Ground Truth appears empty or invalid.", "warning");
        return;
      }

      const predIdSet = new Set(predsAll.map(r => r.id));
      const gtIdSet = new Set(gtAll.map(r => r.id));
      const commonIds = new Set([...gtIdSet].filter(id => predIdSet.has(id)));

      const preds = predsAll.filter(r => commonIds.has(r.id));
      const gt = gtAll.filter(r => commonIds.has(r.id));

      const droppedPred = predsAll.length - preds.length;
      const droppedGT = gtAll.length - gt.length;
      if (droppedPred > 0 || droppedGT > 0) {
        showAlert(
          `ℹ️ Evaluation only on common patients (by ID). ` +
          `${droppedPred > 0 ? `Ignored ${droppedPred} prediction events without GT. ` : ''}` +
          `${droppedGT > 0 ? `Ignored ${droppedGT} GT events without predictions.` : ''}`,
          'info'
        );
      }
      if (!preds.length || !gt.length) {
        showAlert("⚠️ No overlapping patient IDs between predictions and GT.", "warning");
        return;
      }

      // === tolerance-aware matching (±1 month) ===
      const tolMonths = 1; // ALWAYS ON

      // Build per-(id,event) multisets of prediction months, and list of GT items
      const predMap = new Map(); // key = `${id}|${event}`, value = Map(monthInt => count)
      const gtItems = [];        // { key, monthInt, event }

      const predEventTotals = new Map(); // event -> total preds
      const gtEventTotals = new Map(); // event -> total gt

      for (const r of preds) {
        const key = `${r.id}|${r.testo}`;
        const monthKey = monthKeyFromDate(r.data);
        const mi = monthToInt(monthKey);
        if (!isFinite(mi)) continue;

        if (!predMap.has(key)) predMap.set(key, new Map());
        const m = predMap.get(key);
        m.set(mi, (m.get(mi) || 0) + 1);

        predEventTotals.set(r.testo, (predEventTotals.get(r.testo) || 0) + 1);
      }

      for (const r of gt) {
        const key = `${r.id}|${r.testo}`;
        const monthKey = monthKeyFromDate(r.data);
        const mi = monthToInt(monthKey);
        if (!isFinite(mi)) continue;

        gtItems.push({ key, monthInt: mi, event: r.testo });
        gtEventTotals.set(r.testo, (gtEventTotals.get(r.testo) || 0) + 1);
      }

      // Greedy matching: for each GT item, consume a prediction in same month, then -1, then +1
      const tpEvent = new Map(); // event -> TP count
      let tp_all = 0;
      const offsets = [0, -1, +1];

      for (const gtItem of gtItems) {
        const m = predMap.get(gtItem.key);
        if (!m) continue;

        let matched = false;
        let usedMonth = null;
        for (const off of offsets) {
          const cand = gtItem.monthInt + off;
          const cur = m.get(cand) || 0;
          if (cur > 0) {
            m.set(cand, cur - 1); // consume
            matched = true;
            usedMonth = cand;
            break;
          }
        }

        if (matched) {
          tp_all++;
          tpEvent.set(gtItem.event, (tpEvent.get(gtItem.event) || 0) + 1);

          // === RECIST handling (collect only matched CTs; ignore baselines) ===
          const isCT = /tc|tac/i.test(gtItem.event || "");
          if (isCT) {
            // find the exact GT row for this key+month
            const gtRow = gt.find(r => `${r.id}|${r.testo}` === gtItem.key && monthToInt(monthKeyFromDate(r.data)) === gtItem.monthInt);
            if (gtRow) {
              const gtLabel = (gtRow.risposta_recist || "").toUpperCase();
              if (gtLabel && gtLabel !== "BASELINE") {
                // find the consumed prediction row for this key+usedMonth
                const predRow = preds.find(r => `${r.id}|${r.testo}` === gtItem.key && monthToInt(monthKeyFromDate(r.data)) === usedMonth);
                const predLabel = (predRow && predRow.risposta_recist ? predRow.risposta_recist.toUpperCase() : "NE");
                recistMatches.push({ gt: gtLabel, pred: predLabel || "NE" });
              }
            }
          }
        }
      }

      // Remaining predictions (not consumed) => FP
      let remainingPreds = 0;
      for (const m of predMap.values()) {
        for (const cnt of m.values()) remainingPreds += cnt;
      }
      const fp_all = remainingPreds;
      const fn_all = gtItems.length - tp_all;

      const overallMetrics = {
        tp: tp_all,
        fp: fp_all,
        fn: fn_all,
        ...computeMetrics(tp_all, fp_all, fn_all)
      };

      // Per-event metrics
      const allEvents = Array.from(new Set([
        ...predEventTotals.keys(),
        ...gtEventTotals.keys()
      ])).sort((a, b) => a.localeCompare(b, 'it', { sensitivity: 'base' }));

      const perEventRows = allEvents.map(event => {
        const tp = tpEvent.get(event) || 0;
        const predTot = predEventTotals.get(event) || 0;
        const gtTot = gtEventTotals.get(event) || 0;
        const fp = Math.max(0, predTot - tp);
        const fn = Math.max(0, gtTot - tp);
        const m = computeMetrics(tp, fp, fn);
        return { event, tp, fp, fn, precision: m.precision, recall: m.recall, accuracy: m.accuracy, f1: m.f1, support: m.support };
      });

      // Render timeline results
      renderPerEventTable(perEventRows);
      renderOverallAverages(perEventRows, overallMetrics);
      renderChart(perEventRows, metricSelect.value);
      showPredictionsUI();
      showResults();

      // Fetch RECIST evaluation results from backend (if both files exist)
      if (predFile && gtFile) {
        const formData = new FormData();
        formData.append('predictions', predFile);
        formData.append('ground_truth', gtFile);
        try {
          const res = await fetch('/api/recist_evaluation', {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (res.ok && data.status === 'ok') {
            // Fill tables in the frontend
            if (data.recist_summary) {
              const summaryEl = document.getElementById('recist-summary');
              summaryEl.innerHTML = `
                <tr>
                  <td>RECIST</td>
                  <td>${(data.recist_summary.Accuracy * 100).toFixed(1)}%</td>
                  <td>${(data.recist_summary["Macro Precision"] * 100).toFixed(1)}%</td>
                  <td>${(data.recist_summary["Macro Recall"] * 100).toFixed(1)}%</td>
                  <td>${(data.recist_summary["Macro F1"] * 100).toFixed(1)}%</td>
                </tr>`;
            }

            if (data.recist_perclass) {
              const perclassEl = document.getElementById('recist-perclass');
              perclassEl.innerHTML = data.recist_perclass.map(
                c => `<tr>
                  <td>${c.Label}</td>
                  <td>${(c.Precision * 100).toFixed(1)}%</td>
                  <td>${(c.Recall * 100).toFixed(1)}%</td>
                  <td>${(c.F1 * 100).toFixed(1)}%</td>
                  <td>${c.Support}</td>
                </tr>`
              ).join('');
            }

            if (data.recist_matrix) {
              const matrixDiv = document.getElementById('recist-matrix');
              const { labels, matrix } = data.recist_matrix;
              let html = '<table class="table table-bordered table-sm"><tr><th></th>';
              labels.forEach(l => html += `<th>${l}</th>`);
              html += '</tr>';
              matrix.forEach((row, i) => {
                html += `<tr><th>${labels[i]}</th>`;
                row.forEach(v => html += `<td>${v}</td>`);
                html += '</tr>';
              });
              html += '</table>';
              matrixDiv.innerHTML = html;
            }
          } else {
            console.warn("RECIST evaluation failed", data);
          }
        } catch (e) {
          console.error("RECIST fetch failed", e);
        }
      }

      // Render RECIST results (from matched CTs only, baselines excluded)
      if (recistMatches.length) {
        const recistMetrics = computeRecistMetrics(recistMatches);
        renderRecistResults(recistMetrics);
      }

      currentMode = "predictions";
      dlEvalBtn.onclick = () => downloadEvaluation(overallMetrics, perEventRows);

    } catch (err) {
      console.error(err);
      showAlert("❌ Evaluation failed: " + (err.message || err), "danger", 7000);
    } finally {
      hideSpinner();
    }
  });

  // ---- Parse evaluation workbook for models compare ----
  async function parseEvaluationWorkbook(file) {
    const buf = await readFileToArrayBuffer(file);
    const wb = XLSX.read(buf, { type: "array" });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" });

    let modelName = "";
    for (let r = 0; r < Math.min(3, rows.length); r++) {
      const line = rows[r].map(x => String(x).trim());
      const m = /model\s*[:\-]\s*(.+)$/i.exec(line.join(" "));
      if (m && m[1]) { modelName = m[1].trim(); break; }
      if (line[0]) { modelName = line[0]; break; }
    }
    if (!modelName) modelName = file.name.replace(/\.[^.]+$/, "");

    let start = -1, header = [];
    for (let i = 0; i < rows.length; i++) {
      const joined = rows[i].join(" ").toLowerCase();
      if (joined.includes("per-event metrics")) {
        start = i + 1;
        header = rows[start].map(x => String(x).trim().toLowerCase());
        break;
      }
    }
    if (start < 0) return { model: modelName, events: [] };

    const idx = {
      event: header.indexOf("event"),
      tp: header.indexOf("tp"),
      fp: header.indexOf("fp"),
      fn: header.indexOf("fn"),
      support: header.indexOf("support"),
      accuracy: header.indexOf("accuracy"),
      precision: header.indexOf("precision"),
      recall: header.indexOf("recall"),
      f1: header.indexOf("f1-score")
    };

    const out = [];
    for (let r = start + 1; r < rows.length; r++) {
      const row = rows[r];
      if (!row || row.every(c => String(c).trim() === "")) break;

      const name = idx.event >= 0 ? String(row[idx.event] || "").trim() : "";
      if (!name) continue;

      const pick = k => {
        const id = idx[k];
        const v = id >= 0 ? parseFloat(String(row[id]).replace(",", ".")) : NaN;
        return isFinite(v) ? v : 0;
      };

      let f1Val = 0;
      if (idx.f1 >= 0) {
        const v = parseFloat(String(row[idx.f1]).replace(",", "."));
        if (isFinite(v)) f1Val = v;
      }

      out.push({
        event: name,
        tp: pick("tp"),
        fp: pick("fp"),
        fn: pick("fn"),
        support: pick("support"),
        accuracy: pick("accuracy"),
        precision: pick("precision"),
        recall: pick("recall"),
        f1: f1Val
      });
    }

    // --- Extract RECIST OVERALL AVERAGES if available ---
    let recist = { accuracy: 0, precision: 0, recall: 0, f1: 0 };
    for (let i = 0; i < rows.length; i++) {
      const joined = rows[i].join(" ").toLowerCase();
      if (joined.includes("recist overall averages")) {
        // Next lines have metric rows
        for (let j = i + 1; j < Math.min(i + 5, rows.length); j++) {
          const line = rows[j].map(x => String(x).trim().toLowerCase());
          if (line[0].startsWith("weighted")) {
            recist = {
              accuracy: parseFloat(line[1]) || 0,
              precision: parseFloat(line[2]) || 0,
              recall: parseFloat(line[3]) || 0,
              f1: parseFloat(line[4]) || 0
            };
            break;
          }
        }
        break;
      }
    }

    return { model: modelName, events: out, recist };
  }


  if (evalModelsBtn) {
    evalModelsBtn.addEventListener("click", async () => {
      try {
        if (!modelFiles.length || modelFiles.length < 2) {
          showAlert("Please upload at least 2 (up to 4) evaluation files (.xlsx).", "warning");
          return;
        }
        showSpinner();
        const parsed = [];
        for (const f of modelFiles) {
          try { parsed.push(await parseEvaluationWorkbook(f)); }
          catch (e) { console.error("Parse failed for", f.name, e); showAlert(`Failed to read "${f.name}".`, "danger"); }
        }
        if (!parsed.length) { showAlert("No valid evaluation files parsed.", "danger"); return; }

        const metricKey = (modelsMetricSel && modelsMetricSel.value) || "f1";
        renderModelsHeatmap(parsed, metricKey);

        showModelsUI();
        currentMode = "models";
        dlEvalBtn.onclick = () => downloadHeatmap();
      } catch (err) {
        console.error(err);
        showAlert("❌ Models evaluation failed.", "danger");
      } finally {
        hideSpinner();
      }
    });
  }

  if (modelsMetricSel) {
    modelsMetricSel.addEventListener("change", () => {
      (async () => {
        if (!modelFiles.length) return;
        const parsed = [];
        for (const f of modelFiles) parsed.push(await parseEvaluationWorkbook(f));
        renderModelsHeatmap(parsed, modelsMetricSel.value);
      })();
    });
  }

  // Metric selector -> update chart from table
  metricSelect.addEventListener("change", () => {
    const rows = [];
    function numFromCell(txt) {
      const clean = String(txt).trim();
      const hasPct = clean.includes("%");
      const n = parseFloat(clean.replace("%", "").replace(",", "."));
      if (!isFinite(n)) return 0;
      return hasPct ? n / 100 : n;
    }
    tableElem.querySelectorAll("tr").forEach(tr => {
      const tds = tr.querySelectorAll("td");
      if (tds.length >= 9) {
        const event = tds[0].textContent.trim();
        const accuracy = numFromCell(tds[4].textContent);
        const precision = numFromCell(tds[5].textContent);
        const recall = numFromCell(tds[6].textContent);
        const f1 = numFromCell(tds[7].textContent);
        rows.push({ event, tp, fp, fn, accuracy, precision, recall, f1, support });
      }
    });
    if (rows.length) renderChart(rows, metricSelect.value);
  });

  // ---- Rendering helpers for tables/summary ----
  function renderPerEventTable(perEventRows) {
    tableElem.innerHTML = "";
    perEventRows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(r.event)}</td>
        <td>${dec(r.accuracy)}</td>
        <td>${dec(r.precision)}</td>
        <td>${dec(r.recall)}</td>
        <td>${dec(r.f1)}</td>
      `;
      tableElem.appendChild(tr);
    });
  }

  function renderOverallAverages(perEventRows, overall) {
    // Fill the "Overall Metrics" table body (Accuracy/Precision/Recall/F1)
    overallAvgTbody.innerHTML = "";
    const valid = perEventRows.filter(r => r.support > 0);
    const tot = valid.reduce((a, r) => a + r.support, 0);
    const macro = {
      precision: valid.length ? valid.reduce((a, r) => a + r.precision, 0) / valid.length : 0,
      recall: valid.length ? valid.reduce((a, r) => a + r.recall, 0) / valid.length : 0,
      accuracy: valid.length ? valid.reduce((a, r) => a + r.accuracy, 0) / valid.length : 0,
      f1: valid.length ? valid.reduce((a, r) => a + r.f1, 0) / valid.length : 0
    };
    const micro = {
      precision: overall.precision,
      recall: overall.recall,
      accuracy: (overall.tp + overall.fp + overall.fn) ? (overall.tp / (overall.tp + overall.fp + overall.fn)) : 0,
      f1: overall.f1
    };
    const weighted = {
      precision: tot ? valid.reduce((a, r) => a + r.precision * r.support, 0) / tot : 0,
      recall: tot ? valid.reduce((a, r) => a + r.recall * r.support, 0) / tot : 0,
      accuracy: tot ? valid.reduce((a, r) => a + r.accuracy * r.support, 0) / tot : 0,
      f1: tot ? valid.reduce((a, r) => a + r.f1 * r.support, 0) / tot : 0
    };

    const rows = [
      ["Macro avg overall", dec(macro.accuracy), dec(macro.precision), dec(macro.recall), dec(macro.f1)],
      ["Micro avg overall", dec(micro.accuracy), dec(micro.precision), dec(micro.recall), dec(micro.f1)],
      ["Weighted avg overall", dec(weighted.accuracy), dec(weighted.precision), dec(weighted.recall), dec(weighted.f1)]
    ];
    rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td>${r[4]}</td>`;
      overallAvgTbody.appendChild(tr);
    });
  }
});
