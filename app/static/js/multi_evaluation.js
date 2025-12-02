


// EVALUATION VALE
document.addEventListener("DOMContentLoaded", function () {
  const predDropzone = document.getElementById("dropzone-pred");
  const gtDropzone = document.getElementById("dropzone-gt");
  const evaluateBtn = document.getElementById("evaluate-button");
  const spinner = document.getElementById("loading-spinner");
  const resultsSection = document.getElementById("results-section");

  // 🔹 Nascondi i risultati solo se NON arriviamo da una valutazione appena fatta (?ev=1)
  const params = new URLSearchParams(window.location.search);
  const justEvaluated = params.get("ev") === "1";
  if (resultsSection && !justEvaluated) {
    resultsSection.classList.add("d-none");
  }

  let predFile = [];
  let gtFile = [];

  function setupDropzone(dropzone, filesList) {
    const input = dropzone.querySelector("input");
    dropzone.addEventListener("click", () => input.click());
    while (filesList.length) filesList.pop();
    input.addEventListener("change", (e) => {
      for (i = 0; i < e.target.files.length; i++) {
        file = e.target.files[i];
        console.log('setting file', file);
        filesList.push(file)
      }

      dropzone.classList.add("dropzone-success");
      dropzone.querySelector(".dropzone-message").textContent = filesList.map(f => f.name).join(', ');
    });
  }

  setupDropzone(predDropzone, predFile);
  setupDropzone(gtDropzone, gtFile);

  evaluateBtn.addEventListener("click", async () => {
    if (!predFile || !gtFile) {
      alert("⚠️ Please upload both prediction and ground truth files.");
      return;
    }

    const formData = new FormData();
    for (i = 0; i < predFile.length; i++) formData.append("predictions" + i, predFile[i]);
    formData.append("ground_truth", gtFile[0]);

    spinner.classList.remove("d-none");

    try {
      const response = await fetch("/upload_multi_evaluation_data", {
        method: "POST",
        body: formData
      });
      const result = await response.json();
      if (response.ok && result.status === "ok") {
        // 🔹 Vai alla stessa pagina con ev=1 per NON nascondere i risultati al reload
        const url = new URL(window.location.href);
        url.searchParams.set("ev", "1");
        window.location = url.toString();
      } else {
        throw new Error(result.error || "Unknown error");
      }
    } catch (err) {
      alert("❌ Evaluation failed: " + err.message);
    } finally {
      spinner.classList.add("d-none");
    }
  });


});

