document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("user-form");
  const response = await fetch("/api/user");
  const user = await response.json();

  form.usr_name.value = user.usr_name || "";
  form.usr_name_kana.value = user.usr_name_kana || "";
  form.usr_gender.value = user.usr_gender || "1";
  form.usr_birthday.value = user.usr_birthday || "";
  form.usr_age.value = user.usr_age || "";
  form.usr_addr.value = user.usr_addr || "";
  form.usr_phone.value = user.usr_phone || "";
  form.usr_mobile.value = user.usr_mobile || "";
  form.usr_email.value = user.usr_email || "";
  form.usr_family.value = user.usr_family || "1";
  form.usr_licenses.value = user.usr_licenses || "";
  form.usr_siboudouki.value = user.usr_siboudouki || "";
  form.usr_hobby.value = user.usr_hobby || "";
  form.usr_skill.value = user.usr_skill || "";
  form.usr_access.value = user.usr_access || "";

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveUser();
  });
});

/**
 * フォームからユーザー情報を収集してサーバーに保存する
 */
async function saveUser() {
  try {
    const form = document.getElementById("user-form");
    if (!form) return;

    const data = {
      usr_name: form.usr_name.value,
      usr_name_kana: form.usr_name_kana.value,
      usr_gender: form.usr_gender.value,
      usr_birthday: form.usr_birthday.value,
      usr_age: form.usr_age.value,
      usr_addr: form.usr_addr.value,
      usr_phone: form.usr_phone.value,
      usr_mobile: form.usr_mobile.value,
      usr_email: form.usr_email.value,
      usr_family: form.usr_family.value,
      usr_licenses: form.usr_licenses.value,
      usr_siboudouki: form.usr_siboudouki.value,
      usr_hobby: form.usr_hobby.value,
      usr_skill: form.usr_skill.value,
      usr_access: form.usr_access.value,
    };

    console.log("Saving user data:", data);
    const response = await fetch("/admin/user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (await handleAdminAuthError(response)) {
      return;
    }
    if (!response.ok) {
      console.error(
        "Failed to save user data:",
        response.status,
        response.statusText
      );
      alert("保存に失敗しました");
      return;
    }
    alert("保存しました");
  } catch (error) {
    console.error("Error saving user data:", error);
    alert("保存中にエラーが発生しました");
  }
}

/**
 * 胸像写真のアップロードフロントエンド処理
 */
async function uploadImage() {
  const fileInput = document.getElementById("fileInput");
  const file = fileInput.files[0];
  if (!file) {
    alert("画像を選択してください");
    return;
  }

  const progressContainer = document.getElementById("progressContainer");
  const progressBar = document.getElementById("uploadProgress");
  const progressText = document.getElementById("progressText");

  // プログレスバー表示・初期化
  progressContainer.style.display = "block";
  progressBar.value = 0;
  progressText.textContent = "0%";

  const chunkSize = 1024;
  const totalChunks = Math.ceil(file.size / chunkSize);
  const filename = "tmp.jpg";

  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const chunk = file.slice(start, end);
    const isFinal = i === totalChunks - 1;

    const headers = new Headers();
    headers.append("X-Filename", filename);
    headers.append("X-Final", isFinal.toString());

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        headers,
        body: chunk,
      });
      if (await handleAdminAuthError(response)) {
        return;
      }

      const result = await response.json();
      console.log(`Chunk ${i + 1}/${totalChunks}:`, result);

      const progress = Math.round(((i + 1) / totalChunks) * 100);
      progressBar.value = progress;
      progressText.textContent = `${progress}%`;
    } catch (error) {
      console.error("アップロード中にエラーが発生しました:", error);
      break;
    }
  }

  reloadImage();
  progressText.textContent = "アップロード完了";
}

function reloadImage() {
  const img = document.getElementById("userImage");
  // タイムスタンプを追加してキャッシュを強制的に無効化
  const timestamp = new Date().getTime();

  fetch(`/image.jpg?t=${timestamp}`, { cache: "no-store" })
    .then((res) => res.blob())
    .then((blob) => {
      const blobUrl = URL.createObjectURL(blob);
      const newImg = document.createElement("img");
      newImg.id = "userImage";
      newImg.src = blobUrl;
      newImg.onload = () => URL.revokeObjectURL(blobUrl);

      img.parentNode.replaceChild(newImg, img);
    })
    .catch((err) => {
      console.error("画像の再読み込み失敗:", err);
    });
}
