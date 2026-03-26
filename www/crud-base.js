/**
 * CRUD 操作の共通ベースクラス
 * jobhist, portrait, simplehist などの共通ロジックを提供
 */
class CrudBase {
  constructor(config) {
    this.apiEndpoint = config.apiEndpoint;
    this.adminEndpoint = config.adminEndpoint;
    this.containerId = config.containerId;
    this.dataKey = config.dataKey;
    this.itemNumberKey = config.itemNumberKey;
    this.renderItemCallback = config.renderItem;
    this.data = [];
  }

  /**
   * データをサーバーから読み込む
   */
  async load() {
    try {
      console.log(`Fetching data from ${this.apiEndpoint}`);
      const response = await fetch(this.apiEndpoint);
      if (!response.ok) {
        console.error(
          "Failed to fetch data:",
          response.status,
          response.statusText
        );
        return;
      }
      this.data = await response.json();
      console.log(`Data loaded:`, this.data);
      this.render();
    } catch (error) {
      console.error("Error loading data:", error);
    }
  }

  /**
   * データを画面に表示する
   */
  render() {
    const container = document.getElementById(this.containerId);
    if (!container) {
      console.error(`${this.containerId} element not found`);
      return;
    }
    container.innerHTML = this.data
      .map((entry, index) => this.renderItemCallback(entry, index))
      .join("");
    console.log(
      `Rendered form with ${this.data.length} entries`
    );
  }

  /**
   * データを更新する
   */
  update(index, key, value) {
    this.data[index][key] = value;
    console.log(`Updated entry ${index}:`, this.data[index]);
  }

  /**
   * 新しいアイテムを追加する
   */
  add(newItem) {
    newItem[this.itemNumberKey] = this.data.length + 1;
    this.data.push(newItem);
    console.log("Added new entry:", this.data);
    this.render();
  }

  /**
   * アイテムを削除する
   */
  remove(index) {
    this.data.splice(index, 1);
    this.data.forEach((entry, i) => (entry[this.itemNumberKey] = i + 1));
    console.log(
      `Removed entry at index ${index}, New data:`,
      this.data
    );
    this.render();
  }

  /**
   * データをサーバーに保存する
   */
  async save() {
    try {
      console.log("Saving data:", this.data);
      const response = await fetch(this.adminEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.data),
      });
      if (await handleAdminAuthError(response)) {
        return;
      }
      if (!response.ok) {
        console.error(
          "Failed to save data:",
          response.status,
          response.statusText
        );
        alert("保存に失敗しました");
        return;
      }
      alert("保存しました");
    } catch (error) {
      console.error("Error saving data:", error);
      alert("保存中にエラーが発生しました");
    }
  }

  /**
   * HTML 文字列をエスケープする (XSS 対策)
   */
  escapeHtml(text) {
    if (!text) return "";
    return text.replace(/[&<>"']/g, function(match) {
      const escape = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      };
      return escape[match];
    });
  }
}
