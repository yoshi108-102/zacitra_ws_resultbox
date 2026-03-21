const config = window.APP_CONFIG;
const storageKey = "literature_portal_tokens";
const pkceVerifierKey = "literature_portal_pkce_verifier";

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
  return JSON.parse(atob(normalized));
}

function loadTokens() {
  const raw = window.sessionStorage.getItem(storageKey);
  return raw ? JSON.parse(raw) : null;
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

document.getElementById("login-button").addEventListener("click", async () => {
  window.location.href = await buildAuthorizeUrl();
});

document.getElementById("logout-button").addEventListener("click", logout);

const tokens = loadTokens();
if (tokens?.id_token) {
  showAuthenticatedView(tokens.id_token);
} else {
  showPublicView();
}
