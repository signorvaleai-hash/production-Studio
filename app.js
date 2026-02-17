const form = document.getElementById("formatForm");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submitBtn");
const previewStatusEl = document.getElementById("previewStatus");

const frontCoverInput = form.elements["front_cover"];
const backCoverInput = form.elements["back_cover"];
const autoFixCheckbox = form.elements["auto_fix_covers"];

const frontPreviewImg = document.getElementById("frontPreviewImg");
const backPreviewImg = document.getElementById("backPreviewImg");
const frontPreviewMeta = document.getElementById("frontPreviewMeta");
const backPreviewMeta = document.getElementById("backPreviewMeta");

let activePreviewRun = 0;

frontCoverInput.addEventListener("change", runCoverPreview);
backCoverInput.addEventListener("change", runCoverPreview);
autoFixCheckbox.addEventListener("change", runCoverPreview);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Formatting manuscript and building production package...";
  submitBtn.disabled = true;

  try {
    const formData = new FormData(form);
    const selectedProfiles = formData.getAll("profiles");
    if (selectedProfiles.length === 0) {
      throw new Error("Select at least one output format.");
    }

    const response = await fetch("/api/format", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let message = "Failed to format manuscript.";
      try {
        const error = await response.json();
        if (error.error) {
          message = error.error;
        }
      } catch (_) {
        // Keep fallback message.
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match?.[1] || "production_ready.zip";

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    statusEl.textContent = "Done. Production package downloaded.";
  } catch (error) {
    statusEl.textContent = error.message;
  } finally {
    submitBtn.disabled = false;
  }
});

async function fetchCoverPreview(file, role, autoFixCovers) {
  const data = new FormData();
  data.append("cover", file);
  data.append("role", role);
  if (autoFixCovers) {
    data.append("auto_fix_covers", "on");
  }

  const response = await fetch("/api/preview-cover", {
    method: "POST",
    body: data,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(payload?.error || "Preview request failed.");
  }
  return payload;
}

function renderPreview(data, imageEl, metaEl) {
  imageEl.src = data.preview_data_url;
  imageEl.hidden = false;

  const finalInfo = data.final || {};
  const dims = finalInfo.width && finalInfo.height ? `${finalInfo.width}x${finalInfo.height}` : "unknown";
  const format = finalInfo.format || "unknown";
  const dpi = Array.isArray(finalInfo.dpi) ? `${finalInfo.dpi[0]}x${finalInfo.dpi[1]}` : "missing";
  const warnings = (finalInfo.warnings || []).map((w) => `- ${w}`).join("\n");
  const errors = (finalInfo.errors || []).map((e) => `- ${e}`).join("\n");

  let meta = `${data.message}\nFormat: ${format}\nDimensions: ${dims}\nDPI: ${dpi}\n`;
  if (data.auto_corrected) {
    meta += "Auto-corrected: Yes\n";
  }
  if (errors) {
    meta += `Errors:\n${errors}\n`;
  }
  if (warnings) {
    meta += `Warnings:\n${warnings}`;
  }
  metaEl.textContent = meta.trim();
}

function resetPreview(imageEl, metaEl, message) {
  imageEl.hidden = true;
  imageEl.removeAttribute("src");
  metaEl.textContent = message;
}

async function runCoverPreview() {
  const runId = ++activePreviewRun;
  const frontFile = frontCoverInput.files[0];
  const backFile = backCoverInput.files[0];

  if (!frontFile && !backFile) {
    resetPreview(frontPreviewImg, frontPreviewMeta, "Waiting for front cover.");
    resetPreview(backPreviewImg, backPreviewMeta, "Waiting for back cover.");
    previewStatusEl.textContent = "No cover uploaded yet.";
    return;
  }

  const autoFixCovers = autoFixCheckbox.checked;
  previewStatusEl.textContent = "Checking cover files...";

  const frontResult = await runSinglePreview(
    runId,
    frontFile,
    "front",
    frontPreviewImg,
    frontPreviewMeta,
    "No front cover uploaded."
  );
  const backResult = await runSinglePreview(
    runId,
    backFile,
    "back",
    backPreviewImg,
    backPreviewMeta,
    "No back cover uploaded."
  );

  if (runId !== activePreviewRun) {
    return;
  }

  if (frontResult.error || backResult.error) {
    previewStatusEl.textContent = "One or more covers failed preview checks.";
    return;
  }

  if ((frontResult.checked && !frontResult.canProceed) || (backResult.checked && !backResult.canProceed)) {
    previewStatusEl.textContent = autoFixCovers
      ? "Some covers still need correction."
      : "Cover does not meet KDP requirements. Turn on auto-correct to fix.";
    return;
  }

  previewStatusEl.textContent = "Cover preview updated automatically.";
}

async function runSinglePreview(runId, file, role, imageEl, metaEl, emptyMessage) {
  if (!file) {
    resetPreview(imageEl, metaEl, emptyMessage);
    return { checked: false, canProceed: true, error: null };
  }

  try {
    const data = await fetchCoverPreview(file, role, autoFixCheckbox.checked);
    if (runId !== activePreviewRun) {
      return { checked: true, canProceed: true, error: null };
    }
    renderPreview(data, imageEl, metaEl);
    return { checked: true, canProceed: Boolean(data.can_proceed), error: null };
  } catch (error) {
    if (runId !== activePreviewRun) {
      return { checked: true, canProceed: false, error: null };
    }
    resetPreview(imageEl, metaEl, error.message || "Preview failed.");
    return { checked: true, canProceed: false, error };
  }
}
