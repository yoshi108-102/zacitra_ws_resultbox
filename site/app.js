const config = window.APP_CONFIG;
const storageKey = "literature_portal_tokens";
const pkceVerifierKey = "literature_portal_pkce_verifier";
const state = {
  currentFolderId: null,
  documents: [],
  folders: [],
};

function randomString(length) {
  const charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => charset[byte % charset.length]).join("");
}

async function sha256(value) {
  const data = new TextEncoder().encode(value);
  return crypto.subtle.digest("SHA-256", data);
}

function toBase64Url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function buildAuthorizeUrl() {
  const verifier = randomString(64);
  const challenge = toBase64Url(await sha256(verifier));
  window.sessionStorage.setItem(pkceVerifierKey, verifier);

  const params = new URLSearchParams({
    client_id: config.clientId,
    response_type: "code",
    scope: config.scopes.join(" "),
    redirect_uri: config.redirectUri,
    code_challenge_method: "S256",
    code_challenge: challenge,
  });

  return `https://${config.cognitoDomain}/oauth2/authorize?${params.toString()}`;
}

function decodeJwt(token) {
  const [, payload] = token.split(".");
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
  return JSON.parse(atob(padded));
}

function loadTokens() {
  const raw = window.sessionStorage.getItem(storageKey);
  return raw ? JSON.parse(raw) : null;
}

function getApiBaseUrl() {
  return (config.apiBaseUrl || "").replace(/\/$/, "");
}

function showAuthenticatedView(idToken) {
  const claims = decodeJwt(idToken);
  document.getElementById("public-view").classList.add("hidden");
  document.getElementById("private-view").classList.remove("hidden");
  document.getElementById("user-email").textContent = claims.email || "-";
  document.getElementById("user-sub").textContent = claims.sub || "-";
}

function showPublicView() {
  document.getElementById("private-view").classList.add("hidden");
  document.getElementById("public-view").classList.remove("hidden");
}

function logout() {
  window.sessionStorage.removeItem(storageKey);
  const params = new URLSearchParams({
    client_id: config.clientId,
    logout_uri: config.logoutUri,
  });
  window.location.href = `https://${config.cognitoDomain}/logout?${params.toString()}`;
}

function setUploadStatus(message, isError = false) {
  const element = document.getElementById("upload-status");
  element.textContent = message;
  element.classList.toggle("status-error", isError);
}

function getCurrentFolderName() {
  if (!state.currentFolderId) {
    return "ルート";
  }

  return state.folders.find((folder) => folder.folder_id === state.currentFolderId)?.folder_name || "ルート";
}

function getVisibleDocuments() {
  return state.documents.filter((item) => (item.folder_id || null) === state.currentFolderId);
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("ja-JP", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "-";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function resolvePdfContentType(file) {
  if (file.type === "application/pdf") {
    return "application/pdf";
  }

  if (file.name.toLowerCase().endsWith(".pdf")) {
    return "application/pdf";
  }

  return file.type || "";
}

async function apiFetch(path, options = {}) {
  const tokens = loadTokens();
  if (!tokens?.access_token) {
    throw new Error("アクセストークンがありません。再ログインしてください。");
  }

  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${tokens.access_token}`);

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.error?.message || message;
    } catch (_error) {
      // Ignore non-JSON error responses and use the fallback message.
    }
    throw new Error(message);
  }

  return response;
}

async function apiJson(path, options = {}) {
  const response = await apiFetch(path, options);
  return response.json();
}

async function openDocument(documentId, button) {
  button.disabled = true;
  try {
    const payload = await apiJson(`/documents/${documentId}/download-url`);
    window.open(payload.download_url, "_blank", "noopener");
  } finally {
    button.disabled = false;
  }
}

function renderFolders() {
  const list = document.getElementById("folder-list");
  const currentFolder = document.getElementById("current-folder-label");

  currentFolder.textContent = `表示中: ${getCurrentFolderName()}`;
  list.innerHTML = "";

  [
    {
      folder_id: null,
      folder_name: "ルート",
    },
    ...state.folders,
  ].forEach((folder) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "folder-pill";
    if (folder.folder_id === state.currentFolderId) {
      button.classList.add("active");
    }
    button.textContent = folder.folder_name;
    button.addEventListener("click", () => {
      state.currentFolderId = folder.folder_id;
      renderLibrary();
    });
    list.appendChild(button);
  });
}

async function moveDocument(documentId, folderId, button, select) {
  button.disabled = true;
  select.disabled = true;

  try {
    const updated = await apiJson(`/documents/${documentId}/move`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        folder_id: folderId,
      }),
    });

    state.documents = state.documents.map((item) => {
      if (item.document_id === documentId) {
        return updated;
      }
      return item;
    });
    renderLibrary();
    setUploadStatus(`PDF を ${updated.folder_id ? "選択したフォルダ" : "ルート"} に移動しました。`);
  } finally {
    button.disabled = false;
    select.disabled = false;
  }
}

async function deleteDocument(documentId, button) {
  if (!window.confirm("この PDF を削除しますか？")) {
    return;
  }

  button.disabled = true;
  try {
    await apiJson(`/documents/${documentId}`, {
      method: "DELETE",
    });
    state.documents = state.documents.filter((item) => item.document_id !== documentId);
    renderLibrary();
    setUploadStatus("PDF を削除しました。");
  } finally {
    button.disabled = false;
  }
}

function renderDocuments() {
  const list = document.getElementById("documents-list");
  const empty = document.getElementById("documents-empty");
  const items = getVisibleDocuments();

  list.innerHTML = "";
  empty.textContent = state.currentFolderId
    ? "このフォルダにはまだ PDF はありません。"
    : "まだ PDF はありません。";

  if (!items.length) {
    empty.classList.remove("hidden");
    list.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  list.classList.remove("hidden");

  items.forEach((item) => {
    const row = document.createElement("li");
    row.className = "document-item";

    const info = document.createElement("div");
    info.className = "document-info";

    const name = document.createElement("p");
    name.className = "document-name";
    name.textContent = item.file_name;

    const meta = document.createElement("p");
    meta.className = "document-meta";
    meta.textContent = `${formatBytes(item.file_size)} / ${formatDate(item.created_at)}`;

    const badge = document.createElement("span");
    badge.className = "document-status";
    badge.textContent = item.status === "ready" ? "READY" : "PENDING";

    info.append(name, meta, badge);

    const actions = document.createElement("div");
    actions.className = "document-actions";

    const openButton = document.createElement("button");
    openButton.className = "button secondary button-small";
    openButton.type = "button";
    openButton.textContent = "開く";
    openButton.disabled = item.status !== "ready";
    openButton.addEventListener("click", () => {
      openDocument(item.document_id, openButton).catch((error) => {
        setUploadStatus(`文書を開けませんでした: ${error.message}`, true);
      });
    });

    const moveSelect = document.createElement("select");
    moveSelect.className = "folder-select";
    [
      {
        folder_id: null,
        folder_name: "ルート",
      },
      ...state.folders,
    ].forEach((folder) => {
      const option = document.createElement("option");
      option.value = folder.folder_id || "";
      option.textContent = folder.folder_name;
      moveSelect.appendChild(option);
    });
    moveSelect.value = item.folder_id || "";

    const moveButton = document.createElement("button");
    moveButton.className = "button secondary button-small";
    moveButton.type = "button";
    moveButton.textContent = "移動";
    moveButton.disabled = item.status !== "ready";
    moveButton.addEventListener("click", () => {
      moveDocument(item.document_id, moveSelect.value || null, moveButton, moveSelect).catch((error) => {
        setUploadStatus(`PDF を移動できませんでした: ${error.message}`, true);
      });
    });

    const deleteButton = document.createElement("button");
    deleteButton.className = "button danger button-small";
    deleteButton.type = "button";
    deleteButton.textContent = "削除";
    deleteButton.addEventListener("click", () => {
      deleteDocument(item.document_id, deleteButton).catch((error) => {
        setUploadStatus(`PDF を削除できませんでした: ${error.message}`, true);
      });
    });

    actions.append(openButton, moveSelect, moveButton, deleteButton);
    row.append(info, actions);
    list.appendChild(row);
  });
}

function renderLibrary() {
  if (state.currentFolderId && !state.folders.some((folder) => folder.folder_id === state.currentFolderId)) {
    state.currentFolderId = null;
  }

  renderFolders();
  renderDocuments();
}

async function loadLibrary() {
  const [documentsPayload, foldersPayload] = await Promise.all([
    apiJson("/documents"),
    apiJson("/folders"),
  ]);
  state.documents = documentsPayload.items || [];
  state.folders = (foldersPayload.items || []).sort((left, right) => (
    left.folder_name.localeCompare(right.folder_name, "ja")
  ));
  renderLibrary();
}

async function cleanupFailedUpload(documentId) {
  try {
    await apiJson(`/documents/${documentId}`, {
      method: "DELETE",
    });
  } catch (_error) {
    // Best effort cleanup for failed uploads.
  }
}

async function createFolder(event) {
  event.preventDefault();

  const input = document.getElementById("folder-name");
  const button = document.getElementById("create-folder-button");
  const folderName = input.value.trim();

  if (!folderName) {
    setUploadStatus("フォルダ名を入力してください。", true);
    return;
  }

  button.disabled = true;
  try {
    const created = await apiJson("/folders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        folder_name: folderName,
      }),
    });

    state.folders = [...state.folders, created].sort((left, right) => (
      left.folder_name.localeCompare(right.folder_name, "ja")
    ));
    state.currentFolderId = created.folder_id;
    input.value = "";
    renderLibrary();
    setUploadStatus("フォルダを作成しました。");
  } catch (error) {
    setUploadStatus(`フォルダを作成できませんでした: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
}

async function uploadSelectedPdf(event) {
  event.preventDefault();
  const input = document.getElementById("pdf-file");
  const file = input.files?.[0];

  if (!file) {
    setUploadStatus("PDFファイルを選択してください。", true);
    return;
  }

  const contentType = resolvePdfContentType(file);
  if (contentType !== "application/pdf") {
    setUploadStatus("PDFファイルのみアップロードできます。", true);
    return;
  }

  const submitButton = document.getElementById("upload-button");
  submitButton.disabled = true;
  setUploadStatus("アップロードの準備をしています。");

  let createdDocumentId = null;
  try {
    const upload = await apiJson("/uploads", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        file_name: file.name,
        content_type: contentType,
        file_size: file.size,
        folder_id: state.currentFolderId,
      }),
    });
    createdDocumentId = upload.document_id;

    const uploadResponse = await fetch(upload.upload_url, {
      method: upload.upload_method || "PUT",
      headers: upload.upload_headers || {
        "Content-Type": contentType,
      },
      body: file,
    });

    if (!uploadResponse.ok) {
      throw new Error(`S3 upload failed with status ${uploadResponse.status}`);
    }

    const completed = await apiJson(`/documents/${upload.document_id}/complete`, {
      method: "POST",
    });

    state.documents = [completed, ...state.documents.filter((item) => item.document_id !== completed.document_id)];
    renderLibrary();
    input.value = "";
    setUploadStatus(`${getCurrentFolderName()} に PDF をアップロードしました。`);
  } catch (error) {
    if (createdDocumentId) {
      await cleanupFailedUpload(createdDocumentId);
    }
    setUploadStatus(`アップロードに失敗しました: ${error.message}`, true);
  } finally {
    submitButton.disabled = false;
  }
}

document.getElementById("login-button").addEventListener("click", async () => {
  window.location.href = await buildAuthorizeUrl();
});

document.getElementById("logout-button").addEventListener("click", logout);
document.getElementById("upload-form").addEventListener("submit", uploadSelectedPdf);
document.getElementById("folder-form").addEventListener("submit", createFolder);
document.getElementById("refresh-documents-button").addEventListener("click", () => {
  loadLibrary().then(() => {
    setUploadStatus("フォルダと文書一覧を更新しました。");
  }).catch((error) => {
    setUploadStatus(`一覧の取得に失敗しました: ${error.message}`, true);
  });
});

const tokens = loadTokens();
if (tokens?.id_token) {
  showAuthenticatedView(tokens.id_token);
  loadLibrary().catch((error) => {
    setUploadStatus(`一覧の取得に失敗しました: ${error.message}`, true);
  });
} else {
  showPublicView();
}
