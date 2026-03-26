function redirectToAdminLogin() {
  window.location.href = "/admin/login";
}

async function handleAdminAuthError(response) {
  if (response.status !== 401) {
    return false;
  }

  alert("認証が切れました。再ログインしてください。");
  redirectToAdminLogin();
  return true;
}

async function logoutAdmin() {
  try {
    await fetch("/admin/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("ログアウトエラー:", error);
  }

  redirectToAdminLogin();
}
