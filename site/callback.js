const config = window.APP_CONFIG;
const storageKey = "literature_portal_tokens";
const pkceVerifierKey = "literature_portal_pkce_verifier";

async function exchangeCodeForTokens(code, verifier) {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.clientId,
    code,
    redirect_uri: config.redirectUri,
    code_verifier: verifier,
  });

  const response = await fetch(`https://${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });

  if (!response.ok) {
    throw new Error(`Token exchange failed with status ${response.status}`);
  }

  return response.json();
}

async function main() {
  const status = document.getElementById("status");
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const verifier = window.sessionStorage.getItem(pkceVerifierKey);

  if (!code || !verifier) {
    status.textContent = "認証に必要な情報がありません。最初からやり直してください。";
    return;
  }

  try {
    const tokens = await exchangeCodeForTokens(code, verifier);
    window.sessionStorage.setItem(storageKey, JSON.stringify(tokens));
    window.sessionStorage.removeItem(pkceVerifierKey);
    status.textContent = "ログインが完了しました。ホームへ戻ります。";
    window.location.replace("./");
  } catch (error) {
    status.textContent = `ログイン処理に失敗しました: ${error.message}`;
  }
}

main();
