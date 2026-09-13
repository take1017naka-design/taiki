/* PSVTアブレーション 用語・メモ帳
 * データはこの端末のブラウザ(localStorage)に保存されます。
 * 「データ管理」タブのエクスポート/インポートでバックアップ・Git管理してください。
 */

const STORAGE_KEY = "psvt-ablation-app-data-v1";

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function nowStr() {
  return new Date().toLocaleString("ja-JP");
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// エスケープ済みテキストに対して検索語を <mark> でハイライトする
function highlightText(str, query) {
  const escaped = escapeHtml(str);
  if (!query) return escaped;
  return escaped.replace(new RegExp(escapeRegExp(escapeHtml(query)), "ig"), (m) => `<mark>${m}</mark>`);
}

function defaultState() {
  return {
    terms: [
      {
        id: uid(), term: "PSVT", reading: "はっさせいじょうしつせいひんぱく",
        category: "不整脈", description: "発作性上室性頻拍(Paroxysmal SupraVentricular Tachycardia)。突然始まり突然止まる規則正しい頻拍の総称。代表的な機序にAVNRT・AVRTがある。",
        related: "AVNRT, AVRT, WPW症候群", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "AVNRT", reading: "ぼうしつけっせつりえんとりーせいひんぱく",
        category: "不整脈", description: "房室結節リエントリー性頻拍。房室結節内の遅伝導路(slow pathway)と速伝導路(fast pathway)の二重伝導路を旋回するリエントリー性頻拍。アブレーションではslow pathwayを焼灼することが多い。",
        related: "PSVT, slow pathway, fast pathway", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "AVRT", reading: "ぼうしつりえんとりーせいひんぱく",
        category: "不整脈", description: "房室リエントリー性頻拍。房室結節と副伝導路(Kent束など)を旋回するリエントリー性頻拍。WPW症候群に伴うことが多い。",
        related: "PSVT, WPW症候群, 副伝導路", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "WPW症候群", reading: "だぶりゅーぴーだぶりゅーしょうこうぐん",
        category: "不整脈", description: "Wolff-Parkinson-White症候群。副伝導路(Kent束)の存在によりデルタ波・PQ短縮を示し、AVRTを起こしやすい病態。",
        related: "AVRT, 副伝導路, デルタ波", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "His束", reading: "ひすそく",
        category: "解剖", description: "房室結節から続き、左右脚に分かれる特殊心筋の伝導路。カテーテルを置いてHis電位を記録し、房室伝導の評価やカテーテル位置の指標に用いる。",
        related: "房室結節, 右脚, 左脚", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "冠静脈洞(CS)", reading: "かんじょうみゃくどう",
        category: "解剖", description: "Coronary Sinus。左房後壁を走行する静脈で、多極カテーテルを留置して左房側の興奮伝播順序を記録するのに使われる。",
        related: "多極カテーテル, 左房", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "エントレインメント", reading: "えんとれいんめんと",
        category: "手技・検査", description: "頻拍中にペーシングで頻拍レートより速く駆動し、頻拍がリエントリー性かどうか、また回路上の部位かを判定する手技。post-pacing interval(PPI)などで評価する。",
        related: "PPI, リエントリー", memo: "", updatedAt: nowStr(),
      },
      {
        id: uid(), term: "ERP(有効不応期)", reading: "いーあーるぴー",
        category: "生理検査", description: "Effective Refractory Period。刺激を加えても伝導・興奮が生じなくなる最長の連結期。房室結節や副伝導路の伝導特性評価に用いる。",
        related: "不応期, 電気生理検査", memo: "", updatedAt: nowStr(),
      },
    ],
    rmc: [
      { id: uid(), name: "基本設定", items: [] },
      { id: uid(), name: "フィルタ設定", items: [] },
      { id: uid(), name: "記録条件", items: [] },
      { id: uid(), name: "カテーテル表示設定", items: [] },
      { id: uid(), name: "ペーシング設定", items: [] },
      { id: uid(), name: "トラブルシューティング", items: [] },
    ],
    notes: [
      { id: uid(), name: "手技の流れ", items: [] },
      { id: uid(), name: "合併症・対応", items: [] },
      { id: uid(), name: "Tips・注意点", items: [] },
      { id: uid(), name: "ふりかえり", items: [] },
    ],
    scratch: [],
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    if (!parsed.terms || !parsed.rmc || !parsed.notes || !parsed.scratch) throw new Error("invalid");
    return parsed;
  } catch (e) {
    console.warn("failed to load state, using defaults", e);
    return defaultState();
  }
}

let state = loadState();

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  const statusEl = document.getElementById("data-status");
  if (statusEl) statusEl.textContent = `最終保存: ${nowStr()}`;
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2200);
}

/* ---------- タブ切り替え ---------- */

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
}

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (btn) switchTab(btn.dataset.tab);
});

/* ---------- ① 用語辞書 ---------- */

let termFormState = null; // { mode: 'add'|'edit', id? , prefill? }

// 用語名の完全一致・前方一致を優先し、それ以外は他フィールドの一致順に並べる
// (PCI/EVTの検索アプリのように、探している語を上位に出す)
function matchRank(t, query) {
  const term = (t.term || "").toLowerCase();
  const reading = (t.reading || "").toLowerCase();
  if (term === query) return 0;
  if (term.startsWith(query)) return 1;
  if (reading.startsWith(query)) return 2;
  if (term.includes(query)) return 3;
  if (reading.includes(query)) return 4;
  if ((t.related || "").toLowerCase().includes(query)) return 5;
  if ((t.category || "").toLowerCase().includes(query)) return 6;
  if ((t.description || "").toLowerCase().includes(query)) return 7;
  return 8;
}

function renderTerms() {
  const rawQuery = document.getElementById("term-search").value.trim();
  const query = rawQuery.toLowerCase();
  const list = document.getElementById("term-list");
  const items = [...state.terms]
    .filter((t) => {
      if (!query) return true;
      return [t.term, t.reading, t.description, t.related, t.category]
        .some((f) => (f || "").toLowerCase().includes(query));
    })
    .sort((a, b) => {
      if (query) {
        const diff = matchRank(a, query) - matchRank(b, query);
        if (diff !== 0) return diff;
      }
      return (a.reading || a.term).localeCompare(b.reading || b.term, "ja");
    });

  if (items.length === 0) {
    if (query) {
      list.innerHTML = `
        <div class="empty-hint">
          <p>「${escapeHtml(rawQuery)}」に一致する用語は登録されていません。</p>
          <button class="btn btn-primary btn-small" onclick="openTermForm('add', null, '', '${escapeHtml(rawQuery)}')">「${escapeHtml(rawQuery)}」を新しい用語として追加</button>
        </div>`;
    } else {
      list.innerHTML = `<p class="empty-hint">まだ用語が登録されていません。「＋ 用語を追加」から登録してください。</p>`;
    }
  } else {
    list.innerHTML = items.map((t) => `
      <div class="card">
        <div class="card-head">
          <div>
            <p class="card-title">${highlightText(t.term, rawQuery)}</p>
            <p class="card-meta">${t.reading ? highlightText(t.reading, rawQuery) + " ・ " : ""}${t.category ? `<span class="card-badge">${escapeHtml(t.category)}</span>` : ""}更新: ${escapeHtml(t.updatedAt)}</p>
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary btn-small" onclick="openTermForm('edit','${t.id}')">編集</button>
            <button class="btn btn-danger btn-small" onclick="deleteTerm('${t.id}')">削除</button>
          </div>
        </div>
        <div class="card-body">${highlightText(t.description, rawQuery)}</div>
        ${t.related ? `<p class="card-meta">関連: ${highlightText(t.related, rawQuery)}</p>` : ""}
        ${t.memo ? `<p class="card-meta">メモ: ${escapeHtml(t.memo)}</p>` : ""}
      </div>
    `).join("");
  }
  renderTermForm();
}

function openTermForm(mode, id, prefillDescription, prefillTerm) {
  termFormState = { mode, id, prefillDescription, prefillTerm };
  renderTermForm();
  document.getElementById("term-form-area").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeTermForm() {
  termFormState = null;
  renderTermForm();
}

function renderTermForm() {
  const area = document.getElementById("term-form-area");
  if (!termFormState) { area.innerHTML = ""; return; }
  let data = { term: termFormState.prefillTerm || "", reading: "", category: "", description: termFormState.prefillDescription || "", related: "", memo: "" };
  if (termFormState.mode === "edit") {
    const t = state.terms.find((x) => x.id === termFormState.id);
    if (t) data = { ...t };
  }
  area.innerHTML = `
    <div class="form-box">
      <div class="form-row">
        <label>用語</label>
        <input type="text" id="f-term" value="${escapeHtml(data.term)}" placeholder="例: AVNRT">
      </div>
      <div class="form-row">
        <label>読み</label>
        <input type="text" id="f-reading" value="${escapeHtml(data.reading)}" placeholder="ひらがな読み">
      </div>
      <div class="form-row">
        <label>分類</label>
        <input type="text" id="f-category" value="${escapeHtml(data.category)}" placeholder="例: 不整脈 / 解剖 / 機器 / 手技">
      </div>
      <div class="form-row">
        <label>解説</label>
        <textarea id="f-description" rows="4" placeholder="意味・定義を記入">${escapeHtml(data.description)}</textarea>
      </div>
      <div class="form-row">
        <label>関連用語</label>
        <input type="text" id="f-related" value="${escapeHtml(data.related)}" placeholder="カンマ区切り">
      </div>
      <div class="form-row">
        <label>メモ・出典</label>
        <input type="text" id="f-memo" value="${escapeHtml(data.memo)}">
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" onclick="closeTermForm()">キャンセル</button>
        <button class="btn btn-primary" onclick="saveTermForm()">保存</button>
      </div>
    </div>
  `;
}

function saveTermForm() {
  const term = document.getElementById("f-term").value.trim();
  if (!term) { toast("用語名を入力してください"); return; }
  const payload = {
    term,
    reading: document.getElementById("f-reading").value.trim(),
    category: document.getElementById("f-category").value.trim(),
    description: document.getElementById("f-description").value.trim(),
    related: document.getElementById("f-related").value.trim(),
    memo: document.getElementById("f-memo").value.trim(),
    updatedAt: nowStr(),
  };
  if (termFormState.mode === "edit") {
    const t = state.terms.find((x) => x.id === termFormState.id);
    Object.assign(t, payload);
  } else {
    state.terms.push({ id: uid(), ...payload });
  }
  save();
  closeTermForm();
  renderTerms();
  toast("保存しました");
}

function deleteTerm(id) {
  if (!confirm("この用語を削除しますか？")) return;
  state.terms = state.terms.filter((t) => t.id !== id);
  save();
  renderTerms();
}

document.getElementById("term-add-btn").addEventListener("click", () => openTermForm("add"));
document.getElementById("term-search").addEventListener("input", renderTerms);

/* ---------- ② RMCメモ / ③ 自分用メモ (共通コンポーネント) ---------- */

const sections = {
  rmc: { containerId: "rmc-categories", label: "RMCメモ" },
  notes: { containerId: "notes-categories", label: "自分用メモ" },
};

let itemFormState = {}; // key(rmc/notes) -> {mode, categoryId, itemId}
let collapsedCategories = {}; // categoryId -> bool

function renderSection(key) {
  const cfg = sections[key];
  const container = document.getElementById(cfg.containerId);
  const categories = state[key];

  if (categories.length === 0) {
    container.innerHTML = `<p class="empty-hint">大項目がありません。「＋ 大項目を追加」から作成してください。</p>`;
    return;
  }

  container.innerHTML = categories.map((cat) => {
    const collapsed = !!collapsedCategories[cat.id];
    const form = itemFormState[key] && itemFormState[key].categoryId === cat.id ? renderItemFormHtml(key, cat) : "";
    const itemsHtml = cat.items.length
      ? cat.items.map((it) => `
        <div class="card">
          <div class="card-head">
            <div>
              <p class="card-title">${escapeHtml(it.title)}</p>
              <p class="card-meta">更新: ${escapeHtml(it.updatedAt)}</p>
            </div>
            <div class="card-actions">
              <button class="btn btn-secondary btn-small" onclick="openItemForm('${key}','${cat.id}','${it.id}')">編集</button>
              <button class="btn btn-danger btn-small" onclick="deleteItem('${key}','${cat.id}','${it.id}')">削除</button>
            </div>
          </div>
          <div class="card-body">${escapeHtml(it.content)}</div>
        </div>
      `).join("")
      : `<p class="empty-hint">まだ項目がありません。</p>`;

    return `
      <div class="category-block ${collapsed ? "collapsed" : ""}">
        <div class="category-header" onclick="toggleCategory('${cat.id}')">
          <h2>${escapeHtml(cat.name)}<span class="category-count">(${cat.items.length})</span></h2>
          <div class="category-actions" onclick="event.stopPropagation()">
            <button class="btn btn-secondary btn-small" onclick="openItemForm('${key}','${cat.id}')">＋ 項目追加</button>
            <button class="btn btn-secondary btn-small" onclick="renameCategory('${key}','${cat.id}')">名称変更</button>
            <button class="btn btn-danger btn-small" onclick="deleteCategory('${key}','${cat.id}')">削除</button>
          </div>
        </div>
        <div class="category-body">
          ${form}
          ${itemsHtml}
        </div>
      </div>
    `;
  }).join("");
}

function renderItemFormHtml(key, currentCat) {
  const st = itemFormState[key];
  let data = { title: "", content: "" };
  if (st.mode === "edit") {
    const it = currentCat.items.find((i) => i.id === st.itemId);
    if (it) data = { ...it };
  }
  const categoryOptions = state[key].map((c) => `<option value="${c.id}" ${c.id === currentCat.id ? "selected" : ""}>${escapeHtml(c.name)}</option>`).join("");
  return `
    <div class="form-box">
      <div class="form-row">
        <label>タイトル</label>
        <input type="text" id="if-title-${key}" value="${escapeHtml(data.title)}" placeholder="例: フィルタ設定の基本値">
      </div>
      <div class="form-row">
        <label>内容</label>
        <textarea id="if-content-${key}" rows="4" placeholder="設定値・手順・注意点など">${escapeHtml(data.content)}</textarea>
      </div>
      <div class="form-row">
        <label>大項目(移動する場合はここで変更)</label>
        <select id="if-category-${key}">${categoryOptions}</select>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" onclick="closeItemForm('${key}')">キャンセル</button>
        <button class="btn btn-primary" onclick="saveItemForm('${key}','${currentCat.id}')">保存</button>
      </div>
    </div>
  `;
}

function toggleCategory(id) {
  collapsedCategories[id] = !collapsedCategories[id];
  renderAll();
}

function openItemForm(key, categoryId, itemId) {
  itemFormState[key] = { mode: itemId ? "edit" : "add", categoryId, itemId };
  renderSection(key);
}

function closeItemForm(key) {
  delete itemFormState[key];
  renderSection(key);
}

function saveItemForm(key, formCategoryId) {
  const st = itemFormState[key];
  const title = document.getElementById(`if-title-${key}`).value.trim();
  const content = document.getElementById(`if-content-${key}`).value.trim();
  const targetCategoryId = document.getElementById(`if-category-${key}`).value;
  if (!title) { toast("タイトルを入力してください"); return; }

  const sourceCat = state[key].find((c) => c.id === formCategoryId);
  if (st.mode === "edit") {
    const idx = sourceCat.items.findIndex((i) => i.id === st.itemId);
    const item = sourceCat.items[idx];
    item.title = title; item.content = content; item.updatedAt = nowStr();
    if (targetCategoryId !== formCategoryId) {
      sourceCat.items.splice(idx, 1);
      state[key].find((c) => c.id === targetCategoryId).items.push(item);
    }
  } else {
    const targetCat = state[key].find((c) => c.id === targetCategoryId);
    targetCat.items.push({ id: uid(), title, content, updatedAt: nowStr() });
  }
  save();
  closeItemForm(key);
  toast("保存しました");
}

function deleteItem(key, categoryId, itemId) {
  if (!confirm("この項目を削除しますか？")) return;
  const cat = state[key].find((c) => c.id === categoryId);
  cat.items = cat.items.filter((i) => i.id !== itemId);
  save();
  renderSection(key);
}

function addCategory(key) {
  const name = prompt("新しい大項目の名前を入力してください");
  if (!name || !name.trim()) return;
  state[key].push({ id: uid(), name: name.trim(), items: [] });
  save();
  renderSection(key);
}

function renameCategory(key, id) {
  const cat = state[key].find((c) => c.id === id);
  const name = prompt("大項目の名前を変更", cat.name);
  if (!name || !name.trim()) return;
  cat.name = name.trim();
  save();
  renderSection(key);
}

function deleteCategory(key, id) {
  const cat = state[key].find((c) => c.id === id);
  if (cat.items.length > 0) {
    if (!confirm(`「${cat.name}」には${cat.items.length}件の項目があります。中の項目もすべて削除されますが、よろしいですか？`)) return;
  } else if (!confirm(`「${cat.name}」を削除しますか？`)) {
    return;
  }
  state[key] = state[key].filter((c) => c.id !== id);
  save();
  renderSection(key);
}

document.getElementById("rmc-add-category-btn").addEventListener("click", () => addCategory("rmc"));
document.getElementById("notes-add-category-btn").addEventListener("click", () => addCategory("notes"));

/* ---------- 気になるメモ ---------- */

function renderScratch() {
  const list = document.getElementById("scratch-list");
  if (state.scratch.length === 0) {
    list.innerHTML = `<p class="empty-hint">気になることが登録されていません。</p>`;
    return;
  }
  const noteOptions = state.notes.map((c) => `<option value="notes:${c.id}">自分用メモ / ${escapeHtml(c.name)}</option>`).join("");
  const rmcOptions = state.rmc.map((c) => `<option value="rmc:${c.id}">RMCメモ / ${escapeHtml(c.name)}</option>`).join("");

  list.innerHTML = [...state.scratch].reverse().map((s) => `
    <div class="card">
      <div class="card-head">
        <div>
          <p class="card-meta"><span class="scratch-status open">未解決</span>${escapeHtml(s.createdAt)}</p>
        </div>
        <div class="card-actions">
          <button class="btn btn-danger btn-small" onclick="deleteScratch('${s.id}')">削除</button>
        </div>
      </div>
      <div class="card-body">${escapeHtml(s.text)}</div>
      <div class="form-row" style="margin-top:0.6rem;">
        <label>解決したら保存先を選んで記録</label>
        <select id="scratch-target-${s.id}">
          <option value="">-- 保存先を選択 --</option>
          <option value="term">用語辞書に用語として追加</option>
          <optgroup label="自分用メモ">${noteOptions}</optgroup>
          <optgroup label="RMCメモ">${rmcOptions}</optgroup>
        </select>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary btn-small" onclick="resolveScratch('${s.id}')">記録する</button>
      </div>
    </div>
  `).join("");
}

document.getElementById("scratch-add-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("scratch-input");
  const text = input.value.trim();
  if (!text) return;
  state.scratch.push({ id: uid(), text, createdAt: nowStr() });
  input.value = "";
  save();
  renderScratch();
});

function deleteScratch(id) {
  state.scratch = state.scratch.filter((s) => s.id !== id);
  save();
  renderScratch();
}

function resolveScratch(id) {
  const sel = document.getElementById(`scratch-target-${id}`);
  const value = sel.value;
  if (!value) { toast("保存先を選択してください"); return; }
  const s = state.scratch.find((x) => x.id === id);

  if (value === "term") {
    state.scratch = state.scratch.filter((x) => x.id !== id);
    save();
    switchTab("terms");
    openTermForm("add", null, s.text);
    renderTerms();
    toast("用語追加フォームに内容を入れました。用語名を入力して保存してください");
    return;
  }

  const [key, categoryId] = value.split(":");
  const cat = state[key].find((c) => c.id === categoryId);
  const firstLine = s.text.split("\n")[0].slice(0, 40) || "気になるメモより";
  cat.items.push({ id: uid(), title: firstLine, content: s.text, updatedAt: nowStr() });
  state.scratch = state.scratch.filter((x) => x.id !== id);
  save();
  switchTab(key);
  renderAll();
  toast(`「${cat.name}」に記録しました`);
}

/* ---------- データ管理 ---------- */

document.getElementById("export-btn").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  a.href = url;
  a.download = `psvt-ablation-data-${ts}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("import-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(reader.result);
      if (!parsed.terms || !parsed.rmc || !parsed.notes || !parsed.scratch) throw new Error("形式が正しくありません");
      if (!confirm("現在のデータを上書きしてインポートします。よろしいですか？")) return;
      state = parsed;
      save();
      renderAll();
      toast("インポートしました");
    } catch (err) {
      alert("インポートに失敗しました: " + err.message);
    }
  };
  reader.readAsText(file);
  e.target.value = "";
});

document.getElementById("reset-btn").addEventListener("click", () => {
  if (!confirm("すべてのデータを初期状態に戻します。元に戻せません。よろしいですか？")) return;
  state = defaultState();
  save();
  renderAll();
  toast("初期データにリセットしました");
});

/* ---------- 初期描画 ---------- */

function renderAll() {
  renderTerms();
  renderSection("rmc");
  renderSection("notes");
  renderScratch();
}

renderAll();
save();
