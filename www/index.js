document.addEventListener("DOMContentLoaded", async () => {
  const dateTime = document.getElementById("datetime");
  const userInfo = document.getElementById("user-info");
  const simplehistInfo = document.getElementById("simplehist-info");
  const jobhistInfo = document.getElementById("jobhist-info");
  const portraitInfo = document.getElementById("portrait-info");

  const user = await (await fetch("/api/user")).json();
  const simplehist = await (await fetch("/api/simplehist")).json();

  if (Object.keys(user).length === 0 && simplehist.length === 0) {
    userInfo.innerHTML = "<p>データなし</p>";
    return;
  }

  dateTime.innerHTML = getTodayFormatted();

  userInfo.innerHTML = `
    <div class="profile-top">
      <div class="user-image">
        <img src="/image.jpg" alt="User" loading="lazy">
      </div>
      <dl>
        <div class="field field-name">
          <dt>名前</dt>
          <dd class="user-name">${escapeHTML(user.usr_name)} (${escapeHTML(
    user.usr_name_kana
  )})</dd>
        </div>
        <div class="field field-address">
          <dt>住所</dt><dd>${escapeHTML(user.usr_addr)}</dd>
        </div>
      </dl>
      <dl class="personal-block personal-contacts">
        <div class="field"><dt>電話番号</dt><dd>${escapeHTML(
          user.usr_phone || "なし"
        )}</dd></div>
        <div class="field"><dt>携帯番号</dt><dd>${escapeHTML(
          user.usr_mobile
        )}</dd></div>
        <div class="field field-email"><dt>E メール</dt><dd>${escapeHTML(
          user.usr_email
        )}</dd></div>
      </dl>
      <dl class="personal-block personal-demographics">
        <div class="field"><dt>生年月日</dt><dd>${escapeHTML(
          user.usr_birthday
        )}</dd></div>
        <div class="field"><dt>年齢</dt><dd>満${escapeHTML(
          user.usr_age
        )}歳</dd></div>
        <div class="field"><dt>性別</dt><dd>${
          user.usr_gender === "1" ? "女" : "男"
        }</dd></div>
        <div class="field"><dt>扶養家族</dt><dd>${
          user.usr_family === "1" ? "あり" : "なし"
        }</dd></div>
      </dl>
    </div>
    <dl>
      <div class="field-block field-licenses">
        <dt>免許・資格</dt><dd>${escapeHTML(user.usr_licenses).replace(
          /\n/g,
          "<br>"
        )}</dd>
      </div>
      <div class="field-block field-skill">
        <dt>特技</dt><dd>${parseMarkdown(user.usr_skill)}</dd>
      </div>
      <div class="field-block field-motivation">
        <dt>志望動機</dt><dd>${parseMarkdown(user.usr_siboudouki)}</dd>
      </div>
      <div class="field-block field-access">
        <dt>通勤時間</dt><dd>${escapeHTML(user.usr_access)}</dd>
      </div>
      <div class="field-block field-hobby">
        <dt>趣味</dt><dd>${parseMarkdown(user.usr_hobby)}</dd>
      </div>
    </dl>
  `;

  simplehistInfo.innerHTML = `
    <ul class="history-list">
      ${simplehist
        .map(
          (h) =>
            `<li class="history-item">${escapeHTML(
              h.hist_datetime
            )} ${escapeHTML(h.hist_status)}: ${escapeHTML(h.hist_name)}</li>`
        )
        .join("")}
    </ul>
  `;

  const jobhist = await (await fetch("/api/jobhist")).json();
  jobhistInfo.innerHTML = `
    ${jobhist
      .map(
        (j) => `
          <div class="job-entry">
            <h4 class="job-title">${escapeHTML(j.job_name)}</h4>
            <div class="job-detail">${parseMarkdown(j.job_description)}</div>
          </div>
        `
      )
      .join("")}
  `;

  const portrait = await (await fetch("/api/portrait")).json();
  portraitInfo.innerHTML = `
    ${portrait
      .map(
        (p) => `
          <div class="portrait-item">
            <h5 class="portrait-title"><a target="_blank" href="${escapeHTML(
              p.portrait_url
            )}">${escapeHTML(p.portrait_url)}</a></h5>
            <div class="portrait-body">${parseMarkdown(
              p.portrait_summary
            )}</div>
          </div>
        `
      )
      .join("")}
  `;
});

function parseMarkdown(text) {
  if (!text) return "";
  if (typeof marked !== "undefined" && marked.parse) {
    return marked.parse(text);
  }
  return escapeHTML(text).replace(/\n/g, "<br>");
}

function escapeHTML(text) {
  if (!text) return "";
  return text.replace(/[&<>"']/g, function (match) {
    const escape = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return escape[match];
  });
}

function getTodayFormatted() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");

  return `${year}年${month}月${day}日 現在`;
}

function ipToNum(ip) {
  return (
    ip
      .split(".")
      .reduce((acc, octet) => (acc << 8) + parseInt(octet, 10), 0) >>> 0
  );
}

// admin クラスの要素を表示/非表示にする関数
function toggleAdminElements(show) {
  const adminElements = document.querySelectorAll(".admin");
  adminElements.forEach((element) => {
    element.style.display = show ? "block" : "none";
  });
}

async function checkServerNetwork() {
  const currentHost = window.location.hostname;
  const adminNetworks = [];

  // Default AP network
  adminNetworks.push({
    base: ipToNum("192.168.4.0"),
    mask: ipToNum("255.255.255.0"),
  });

  try {
    const res = await fetch("/api/network");
    if (res.ok) {
      const info = await res.json();
      if (info.sta && info.sta.ip) {
        const staIp = ipToNum(info.sta.ip);
        const staMask = ipToNum(info.sta.netmask);
        const staBase = staIp & staMask;
        adminNetworks.push({
          base: staBase,
          mask: staMask,
        });
      }
    }
  } catch (e) {
    console.warn("Failed to fetch network info", e);
  }

  const isIp =
    /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(
      currentHost
    );

  let isAdmin = false;

  if (isIp) {
    const hostNum = ipToNum(currentHost);
    isAdmin = adminNetworks.some((net) => (hostNum & net.mask) === net.base);
  }

  toggleAdminElements(isAdmin);
  return isAdmin;
}

// ページロード時に実行
document.addEventListener("DOMContentLoaded", function () {
  checkServerNetwork();
});

function recheckServerNetwork() {
  return checkServerNetwork();
}
