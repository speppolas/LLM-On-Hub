


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

  let predFile = null;
  let gtFile = null;

  function setupDropzone(dropzone, fileSetter) {
    const input = dropzone.querySelector("input");
    dropzone.addEventListener("click", () => input.click());
    input.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        fileSetter(file);
        dropzone.classList.add("dropzone-success");
        dropzone.querySelector(".dropzone-message").textContent = file.name;
      }
    });
  }

  setupDropzone(predDropzone, f => predFile = f);
  setupDropzone(gtDropzone, f => gtFile = f);

  evaluateBtn.addEventListener("click", async () => {
    if (!predFile || !gtFile) {
      alert("⚠️ Please upload both prediction and ground truth files.");
      return;
    }

    const formData = new FormData();
    formData.append("predictions", predFile);
    formData.append("ground_truth", gtFile);

    spinner.classList.remove("d-none");

    try {
      const response = await fetch("/upload_evaluation_data", {
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

