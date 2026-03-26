const loginForm = document.getElementById("admin-login-form");
const loginError = document.getElementById("login-error");

function getNextAdminPath() {
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");
  if (next && next.startsWith("/admin/")) {
    return next;
  }
  return "/admin/user";
}

function showLoginError(message) {
  loginError.textContent = message;
  loginError.hidden = false;
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.hidden = true;

  const formData = new FormData(loginForm);
  const password = formData.get("password");

  try {
    const response = await fetch("/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });

    if (response.ok) {
      window.location.href = getNextAdminPath();
      return;
    }

    if (response.status === 401) {
      showLoginError("パスワードが違います。");
      return;
    }

    if (response.status === 503) {
      showLoginError("管理用パスワードが未設定です。");
      return;
    }

    showLoginError("ログインに失敗しました。");
  } catch (error) {
    console.error("ログインエラー:", error);
    showLoginError("通信エラーが発生しました。");
  }
});
