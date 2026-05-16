function resolveApiBaseUrl() {
  const override = window.APP_CONFIG?.API_BASE_URL_OVERRIDE;
  if (typeof override === "string" && override.trim() !== "") {
    return override.trim().replace(/\/+$/, "");
  }
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    return "http://localhost:8000";
  }
  return `http://${host}:8000`;
}

const API_BASE_URL = resolveApiBaseUrl();

const provinceEl = document.getElementById("province");
const value1El = document.getElementById("value1");
const value2El = document.getElementById("value2");
const inputModeEl = document.getElementById("inputMode");
const convertBtnEl = document.getElementById("convertBtn");
const statusTextEl = document.getElementById("statusText");
const resultCardEl = document.getElementById("resultCard");
const qrBoxEl = document.getElementById("qrBox");

const captureBtnEl = document.getElementById("captureBtn");
const pickFileBtnEl = document.getElementById("pickFileBtn");
const ocrImageInputEl = document.getElementById("ocrImageInput");
const ocrImageCaptureInputEl = document.getElementById("ocrImageCaptureInput");
const ocrFileNameTextEl = document.getElementById("ocrFileNameText");
const ocrBtnEl = document.getElementById("ocrBtn");
const ocrStatusTextEl = document.getElementById("ocrStatusText");
const ocrWarningsEl = document.getElementById("ocrWarnings");
const ocrCandidatesTableWrapEl = document.getElementById("ocrCandidatesTableWrap");
const ocrCandidatesTableBodyEl = document.getElementById("ocrCandidatesTableBody");
const previewSelectedBtnEl = document.getElementById("previewSelectedBtn");
const ocrBatchPreviewEl = document.getElementById("ocrBatchPreview");
const ocrMetaDetailsEl = document.getElementById("ocrMetaDetails");
const ocrMetaListEl = document.getElementById("ocrMetaList");
const ocrRawDetailsEl = document.getElementById("ocrRawDetails");
const ocrRawTextEl = document.getElementById("ocrRawText");

const resultLatEl = document.getElementById("resultLat");
const resultLngEl = document.getElementById("resultLng");
const resultOrderEl = document.getElementById("resultOrder");
const resultMapsEl = document.getElementById("resultMaps");
const resultWarningsEl = document.getElementById("resultWarnings");
const resultQrEl = document.getElementById("resultQr");
const downloadQrBtnEl = document.getElementById("downloadQrBtn");
const copyLatLngBtnEl = document.getElementById("copyLatLngBtn");
const copyMapsBtnEl = document.getElementById("copyMapsBtn");
const openMapsBtnEl = document.getElementById("openMapsBtn");

const brandLogoEl = document.getElementById("brandLogo");
const brandFallbackEl = document.getElementById("brandFallback");

const state = {
  currentLat: null,
  currentLng: null,
  lastLatitude: null,
  lastLongitude: null,
  lastMapsUrl: "",
};

brandLogoEl.addEventListener("error", () => {
  brandLogoEl.style.display = "none";
  brandFallbackEl.style.display = "block";
});

function setOcrStatus(message, type = "default") {
  ocrStatusTextEl.textContent = message;
  ocrStatusTextEl.classList.remove("success", "error");
  if (type === "success") ocrStatusTextEl.classList.add("success");
  if (type === "error") ocrStatusTextEl.classList.add("error");
}

function usedOrderToVietnamese(order) {
  if (order === "easting_northing") return "Giá trị 1 là Đông, Giá trị 2 là Bắc";
  if (order === "northing_easting") return "Giá trị 1 là Bắc, Giá trị 2 là Đông";
  return order || "-";
}

function translateWarningText(warning) {
  if (!warning) return "";
  const value = String(warning).trim();
  if (value === "Input order auto-detected as northing/easting (value1/value2 may be swapped).") {
    return "Hệ thống tự nhận diện thứ tự tọa độ là Bắc/Đông. Vui lòng kiểm tra lại giá trị 1 và giá trị 2.";
  }
  if (value === "Input order auto-detected as easting/northing.") {
    return "Hệ thống tự nhận diện thứ tự tọa độ là Đông/Bắc.";
  }
  if (value === "Both coordinate orders produce plausible Vietnam positions; defaulted to easting/northing.") {
    return "Cả hai thứ tự tọa độ đều cho kết quả hợp lý trong phạm vi Việt Nam; hệ thống tạm chọn thứ tự Đông/Bắc.";
  }
  if (value === "Neither coordinate order looks plausible in Vietnam bbox. Review coordinate values and province.") {
    return "Không có thứ tự tọa độ nào cho kết quả hợp lý trong phạm vi Việt Nam. Vui lòng kiểm tra lại giá trị tọa độ và tỉnh/thành phố.";
  }
  return value;
}

async function loadProvinces() {
  provinceEl.innerHTML = '<option value="">Đang tải danh sách tỉnh/thành...</option>';
  try {
    const resp = await fetch(`${API_BASE_URL}/api/provinces`);
    if (!resp.ok) throw new Error("Không tải được danh sách tỉnh/thành.");
    const data = await resp.json();
    provinceEl.innerHTML = '<option value="">Chọn tỉnh/thành phố</option>';
    for (const province of data.provinces || []) {
      const opt = document.createElement("option");
      opt.value = province;
      opt.textContent = province;
      provinceEl.appendChild(opt);
    }
    const variants = ["TP.Hồ Chí Minh", "TP Hồ Chí Minh", "Thành phố Hồ Chí Minh", "TP.HCM"];
    const options = Array.from(provinceEl.options).map((o) => o.value.trim());
    const found = variants.find((v) => options.includes(v));
    if (found) provinceEl.value = found;
  } catch (_err) {
    provinceEl.innerHTML = '<option value="">Không tải được danh sách tỉnh/thành</option>';
    statusTextEl.textContent = `Không kết nối được backend (${API_BASE_URL}).`;
  }
}

function setLoading(isLoading) {
  convertBtnEl.disabled = isLoading;
  convertBtnEl.textContent = isLoading ? "Đang chuyển đổi..." : "Chuyển đổi";
}

function setOcrLoading(isLoading) {
  ocrBtnEl.disabled = isLoading;
  ocrBtnEl.textContent = isLoading ? "Đang OCR..." : "OCR tọa độ";
}

function renderWarnings(warnings) {
  resultWarningsEl.innerHTML = "";
  if (!warnings || warnings.length === 0) {
    const li = document.createElement("li");
    li.style.color = "#64748B";
    li.textContent = "Không có cảnh báo.";
    resultWarningsEl.appendChild(li);
    return;
  }
  for (const warning of warnings) {
    const li = document.createElement("li");
    li.textContent = translateWarningText(warning);
    resultWarningsEl.appendChild(li);
  }
}

function renderOcrWarnings(warnings) {
  ocrWarningsEl.innerHTML = "";
  for (const warning of warnings || []) {
    const li = document.createElement("li");
    li.textContent = warning === "OCR is experimental. Please verify values before conversion."
      ? "OCR đang trong giai đoạn thử nghiệm. Vui lòng kiểm tra kỹ kết quả trước khi chuyển đổi."
      : warning;
    ocrWarningsEl.appendChild(li);
  }
}

function mapOcrErrorMessage(payload) {
  if (!payload || payload.ok !== false) return null;
  if (payload.stage === "image_open") {
    return "Không đọc được file ảnh. Hãy dùng JPG/PNG rõ nét và thử lại.";
  }
  if (payload.error_code === "TESSERACT_UNAVAILABLE" || payload.stage === "tesseract_run") {
    return "Chưa cấu hình được Tesseract OCR. Kiểm tra TESSERACT_CMD/PATH.";
  }
  return payload.message || "OCR thất bại.";
}

function normalizeConfidenceText(text) {
  let value = text || "";
  value = value.replace("detected from same OCR row", "Nhận diện từ cùng dòng OCR");
  value = value.replace("corrected by column context", "Đã hiệu chỉnh theo ngữ cảnh cùng cột");
  value = value.replace("detected from nearby OCR numbers (low confidence)", "Nhận diện từ các số OCR gần nhau (độ tin cậy thấp)");
  return value;
}

function renderOcrCandidates(candidates) {
  ocrCandidatesTableBodyEl.innerHTML = "";
  ocrBatchPreviewEl.innerHTML = "";
  ocrMetaListEl.innerHTML = "";

  if (!candidates || candidates.length === 0) {
    ocrCandidatesTableWrapEl.classList.add("hidden");
    ocrMetaDetailsEl.classList.add("hidden");
    return;
  }

  const hasRowBased = candidates.some(
    (c) => !String(c.confidence_note || "").toLowerCase().includes("nearby ocr numbers")
  );
  const list = hasRowBased
    ? candidates.filter((c) => !String(c.confidence_note || "").toLowerCase().includes("nearby ocr numbers"))
    : candidates;

  if (list.length === 0) {
    ocrCandidatesTableWrapEl.classList.add("hidden");
    ocrMetaDetailsEl.classList.add("hidden");
    return;
  }

  ocrCandidatesTableWrapEl.classList.remove("hidden");

  for (const item of list) {
    const candidateId = `ocr-${String(item.point_label || "")}-${String(item.value1)}-${String(item.value2)}`.replace(/\s+/g, "-");
    const tr = document.createElement("tr");

    const tdSelect = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "ocr-select";
    checkbox.dataset.candidateId = candidateId;
    checkbox.dataset.label = item.point_label || "";
    checkbox.dataset.v1 = String(item.value1);
    checkbox.dataset.v2 = String(item.value2);
    tdSelect.appendChild(checkbox);

    const tdLabel = document.createElement("td");
    tdLabel.textContent = item.point_label || "-";

    const tdV1 = document.createElement("td");
    tdV1.textContent = String(item.value1);

    const tdV2 = document.createElement("td");
    tdV2.textContent = String(item.value2);

    const tdAction = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "secondary-btn";
    btn.type = "button";
    btn.textContent = "Dùng";
    btn.addEventListener("click", () => {
      value1El.value = String(item.value1);
      value2El.value = String(item.value2);
      statusTextEl.textContent = "Đã điền tọa độ từ OCR. Vui lòng kiểm tra và bấm Chuyển đổi.";
    });
    tdAction.appendChild(btn);

    tr.appendChild(tdSelect);
    tr.appendChild(tdLabel);
    tr.appendChild(tdV1);
    tr.appendChild(tdV2);
    tr.appendChild(tdAction);
    ocrCandidatesTableBodyEl.appendChild(tr);

    const li = document.createElement("li");
    const confidence = normalizeConfidenceText(item.confidence_note || "");
    const corrections = (item.corrections || []).join(" | ");
    li.textContent = corrections ? `Điểm ${item.point_label}: ${confidence}; ${corrections}` : `Điểm ${item.point_label}: ${confidence}`;
    ocrMetaListEl.appendChild(li);
  }

  if (ocrMetaListEl.children.length > 0) {
    ocrMetaDetailsEl.classList.remove("hidden");
  } else {
    ocrMetaDetailsEl.classList.add("hidden");
  }
}

function previewSelectedCandidates() {
  ocrBatchPreviewEl.innerHTML = "";
  const checked = Array.from(document.querySelectorAll(".ocr-select:checked"));
  if (checked.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Chưa chọn cặp nào để xem trước.";
    ocrBatchPreviewEl.appendChild(li);
    return;
  }
  const uniq = new Map();
  checked.forEach((item) => {
    const key = `${item.dataset.label}|${item.dataset.v1}|${item.dataset.v2}`;
    if (!uniq.has(key)) uniq.set(key, item);
  });
  for (const item of uniq.values()) {
    const li = document.createElement("li");
    li.textContent = `Điểm ${item.dataset.label || "-"}: ${item.dataset.v1} | ${item.dataset.v2}`;
    ocrBatchPreviewEl.appendChild(li);
  }
}

function setSelectedFile(file) {
  if (!file) {
    ocrFileNameTextEl.textContent = "Chưa chọn ảnh.";
    return;
  }
  ocrFileNameTextEl.textContent = `Ảnh đã chọn: ${file.name}`;
}

async function runOcr() {
  const file = (ocrImageInputEl.files && ocrImageInputEl.files[0]) || (ocrImageCaptureInputEl.files && ocrImageCaptureInputEl.files[0]);
  if (!file) {
    setOcrStatus("Vui lòng chọn ảnh trước khi OCR.", "error");
    return;
  }

  setOcrStatus("");
  renderOcrWarnings([]);
  ocrCandidatesTableBodyEl.innerHTML = "";
  ocrBatchPreviewEl.innerHTML = "";
  ocrMetaListEl.innerHTML = "";
  ocrCandidatesTableWrapEl.classList.add("hidden");
  ocrMetaDetailsEl.classList.add("hidden");
  ocrRawDetailsEl.classList.add("hidden");
  setOcrLoading(true);

  try {
    const form = new FormData();
    form.append("image", file);
    const resp = await fetch(`${API_BASE_URL}/api/ocr-coordinates`, { method: "POST", body: form });
    const data = await resp.json();
    if (!resp.ok || data?.ok === false) {
      const friendly = mapOcrErrorMessage(data);
      const stage = data?.stage ? ` [giai đoạn: ${data.stage}]` : "";
      const suggestion = data?.suggestion ? ` Gợi ý: ${data.suggestion}` : "";
      setOcrStatus(`${friendly}${stage}.${suggestion}`, "error");
      renderOcrWarnings([data?.detail || "Yêu cầu OCR thất bại."]);
      return;
    }

    setOcrStatus("OCR hoàn tất. Hãy xác minh kết quả trước khi dùng.", "success");
    renderOcrWarnings(data.warnings || []);
    renderOcrCandidates(data.candidates || []);
    ocrRawTextEl.textContent = data.raw_text || "";
    ocrRawDetailsEl.classList.remove("hidden");
  } catch (err) {
    setOcrStatus(`Lỗi OCR: ${err.message}`, "error");
  } finally {
    setOcrLoading(false);
  }
}

async function copyText(text, successMessage) {
  if (!text) {
    statusTextEl.textContent = "Không có dữ liệu để sao chép.";
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    statusTextEl.textContent = successMessage;
  } catch (_err) {
    statusTextEl.textContent = "Không sao chép được. Trình duyệt có thể đang chặn clipboard.";
  }
}

async function convertCoordinates() {
  const province = provinceEl.value.trim();
  const value1 = Number(value1El.value);
  const value2 = Number(value2El.value);
  const inputMode = inputModeEl.value;

  if (!province) {
    statusTextEl.textContent = "Vui lòng chọn tỉnh/thành phố.";
    return;
  }
  if (Number.isNaN(value1) || Number.isNaN(value2)) {
    statusTextEl.textContent = "Vui lòng nhập đầy đủ 2 giá trị tọa độ hợp lệ.";
    return;
  }

  statusTextEl.textContent = "";
  setLoading(true);
  try {
    const payload = {
      province,
      value1,
      value2,
      input_mode: inputMode,
      current_lat: null,
      current_lng: null,
    };
    const resp = await fetch(`${API_BASE_URL}/api/convert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data?.detail || "Chuyển đổi thất bại.");

    state.lastLatitude = Number(data.latitude);
    state.lastLongitude = Number(data.longitude);
    state.lastMapsUrl = data.google_maps_url || "";

    resultLatEl.textContent = state.lastLatitude.toFixed(12);
    resultLngEl.textContent = state.lastLongitude.toFixed(12);
    resultOrderEl.textContent = usedOrderToVietnamese(data.used_order);
    resultMapsEl.href = state.lastMapsUrl || "#";
    resultMapsEl.textContent = state.lastMapsUrl || "-";

    if (data.qr_png_base64) {
      resultQrEl.src = `data:image/png;base64,${data.qr_png_base64}`;
      qrBoxEl.classList.remove("hidden");
    } else {
      resultQrEl.removeAttribute("src");
      qrBoxEl.classList.add("hidden");
    }

    renderWarnings(data.warnings || []);
    resultCardEl.classList.remove("hidden");
    if (typeof resultCardEl.scrollIntoView === "function") {
      resultCardEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    statusTextEl.textContent = "Chuyển đổi thành công.";
  } catch (err) {
    statusTextEl.textContent = `Lỗi: ${err.message}`;
  } finally {
    setLoading(false);
  }
}

captureBtnEl.addEventListener("click", () => ocrImageCaptureInputEl.click());
pickFileBtnEl.addEventListener("click", () => ocrImageInputEl.click());
ocrImageCaptureInputEl.addEventListener("change", () => setSelectedFile(ocrImageCaptureInputEl.files?.[0] || null));
ocrImageInputEl.addEventListener("change", () => setSelectedFile(ocrImageInputEl.files?.[0] || null));

copyLatLngBtnEl.addEventListener("click", async () => {
  if (state.lastLatitude == null || state.lastLongitude == null) {
    statusTextEl.textContent = "Chưa có kết quả để sao chép Lat/Long.";
    return;
  }
  await copyText(`${state.lastLatitude},${state.lastLongitude}`, "Đã sao chép Lat/Long.");
});

copyMapsBtnEl.addEventListener("click", async () => {
  if (!state.lastMapsUrl) {
    statusTextEl.textContent = "Chưa có link Google Maps để sao chép.";
    return;
  }
  await copyText(state.lastMapsUrl, "Đã sao chép link Google Maps.");
});

openMapsBtnEl.addEventListener("click", () => {
  if (!state.lastMapsUrl) {
    statusTextEl.textContent = "Chưa có link Google Maps để mở.";
    return;
  }
  window.open(state.lastMapsUrl, "_blank", "noopener");
});

downloadQrBtnEl.addEventListener("click", () => {
  const src = resultQrEl.getAttribute("src") || "";
  if (!src.startsWith("data:image/png;base64,")) {
    statusTextEl.textContent = "Chưa có ảnh QR để tải.";
    return;
  }
  const link = document.createElement("a");
  link.href = src;
  link.download = "vietinbank-vn2000-google-maps-qr.png";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
});

convertBtnEl.addEventListener("click", convertCoordinates);
ocrBtnEl.addEventListener("click", runOcr);
previewSelectedBtnEl.addEventListener("click", previewSelectedCandidates);

loadProvinces();
