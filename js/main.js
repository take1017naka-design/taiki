/*
 * main.js
 * 画面遷移とUIイベントの配線。
 */
(function () {
  "use strict";

  const engine = new RG.SynthEngine();
  const canvas = document.getElementById("game-canvas");
  const game = new RG.Game(engine, canvas);

  const screens = {
    title: document.getElementById("screen-title"),
    game: document.getElementById("screen-game"),
    result: document.getElementById("screen-result"),
  };

  function showScreen(name) {
    Object.values(screens).forEach((s) => s.classList.remove("active"));
    screens[name].classList.add("active");
  }

  // ---------- タイトル画面: 曲リスト構築 ----------
  const songListEl = document.getElementById("song-list");
  RG.SONGS.forEach((song) => {
    const card = document.createElement("div");
    card.className = "song-card " + song.genre.toLowerCase().replace("s", "");
    const mm = Math.floor(song.duration / 60);
    const ss = String(Math.floor(song.duration % 60)).padStart(2, "0");
    card.innerHTML = `
      <span class="song-genre">${song.genre}</span>
      <div class="song-name">${song.name}</div>
      <p class="song-meta">BPM ${song.bpm} ・ ${mm}:${ss}</p>
      <div class="song-diff">
        <span class="dot on ${song.genre.toLowerCase().replace("s", "")}"></span>
        <span class="dot on ${song.genre.toLowerCase().replace("s", "")}"></span>
        <span class="dot on ${song.genre.toLowerCase().replace("s", "")}"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    `;
    card.addEventListener("click", () => startGame(song));
    songListEl.appendChild(card);
  });

  // ---------- ゲーム画面 HUD 要素 ----------
  const hudScore = document.getElementById("hud-score");
  const hudCombo = document.getElementById("hud-combo");
  const hudJudge = document.getElementById("hud-judge");
  const hudSongTitle = document.getElementById("hud-song-title");
  const progressFill = document.getElementById("progress-fill");
  const pauseOverlay = document.getElementById("pause-overlay");

  let judgeTimeout = null;
  let comboTimeout = null;

  game.on("score", ({ score, combo }) => {
    hudScore.textContent = score.toLocaleString();
    if (combo >= 2) {
      hudCombo.innerHTML = `${combo}<small>COMBO</small>`;
      hudCombo.classList.add("show");
      clearTimeout(comboTimeout);
      comboTimeout = setTimeout(() => hudCombo.classList.remove("show"), 700);
    } else {
      hudCombo.classList.remove("show");
    }
  });

  game.on("judge", (result) => {
    const labelMap = { perfect: "PERFECT", great: "GREAT", good: "GOOD", miss: "MISS" };
    hudJudge.textContent = labelMap[result];
    hudJudge.className = "hud-judge " + result;
    clearTimeout(judgeTimeout);
    void hudJudge.offsetWidth;
    hudJudge.classList.add("pop-in");
    judgeTimeout = setTimeout(() => {
      hudJudge.classList.remove("pop-in");
    }, 320);
  });

  game.on("progress", (p) => {
    progressFill.style.width = p * 100 + "%";
  });

  game.on("laneFlash", (lane) => {
    const btn = document.querySelector(`.lane-btn[data-lane="${lane}"]`);
    if (!btn) return;
    btn.classList.add("active");
    setTimeout(() => btn.classList.remove("active"), 90);
  });

  game.on("finish", (result) => {
    showResult(result);
  });

  // ---------- 入力: キーボード ----------
  const KEY_TO_LANE = { d: 0, f: 1, j: 2, k: 3 };
  window.addEventListener("keydown", (e) => {
    const key = e.key.toLowerCase();
    if (key in KEY_TO_LANE && screens.game.classList.contains("active")) {
      if (e.repeat) return;
      game.handleLaneInput(KEY_TO_LANE[key]);
    }
    if (key === "escape" && screens.game.classList.contains("active")) {
      togglePause();
    }
  });

  // ---------- 入力: タッチ / クリック ----------
  document.querySelectorAll(".lane-btn").forEach((btn) => {
    const lane = parseInt(btn.dataset.lane, 10);
    btn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      game.handleLaneInput(lane);
      btn.classList.add("active");
    });
    btn.addEventListener("pointerup", () => btn.classList.remove("active"));
    btn.addEventListener("pointerleave", () => btn.classList.remove("active"));
  });

  // ---------- 一時停止 ----------
  const btnPause = document.getElementById("btn-pause");
  const btnResume = document.getElementById("btn-resume");
  const btnQuit = document.getElementById("btn-quit");

  function togglePause() {
    if (game.state === "playing") {
      game.pause();
      pauseOverlay.classList.remove("hidden");
    } else if (game.state === "paused") {
      game.resume();
      pauseOverlay.classList.add("hidden");
    }
  }

  btnPause.addEventListener("click", togglePause);
  btnResume.addEventListener("click", togglePause);
  btnQuit.addEventListener("click", () => {
    game.stop();
    pauseOverlay.classList.add("hidden");
    showScreen("title");
  });

  // ---------- ゲーム開始 ----------
  let currentSong = null;

  function startGame(song) {
    currentSong = song;
    hudSongTitle.textContent = `${song.genre} / ${song.name}`;
    hudScore.textContent = "0";
    hudCombo.classList.remove("show");
    progressFill.style.width = "0%";
    showScreen("game");
    requestAnimationFrame(() => {
      game._resize();
      game.loadSong(song);
      game.start();
    });
  }

  // ---------- リザルト画面 ----------
  const resultRank = document.getElementById("result-rank");
  const resultTitle = document.getElementById("result-song-title");
  const resultScore = document.getElementById("result-score");
  const resultCombo = document.getElementById("result-combo");
  const resultAccuracy = document.getElementById("result-accuracy");
  const judgeBreakdown = document.getElementById("judge-breakdown");

  function computeRank(score, accuracy) {
    if (accuracy >= 98) return "S";
    if (accuracy >= 92) return "A";
    if (accuracy >= 82) return "B";
    if (accuracy >= 65) return "C";
    return "D";
  }

  function showResult(result) {
    resultTitle.textContent = `${currentSong.genre} / ${currentSong.name}`;
    resultScore.textContent = result.score.toLocaleString();
    resultCombo.textContent = result.maxCombo;
    resultAccuracy.textContent = result.accuracy.toFixed(1) + "%";
    resultRank.textContent = computeRank(result.score, result.accuracy);

    const jc = result.judgeCounts;
    judgeBreakdown.innerHTML = `
      <div class="jb perfect"><b>${jc.perfect}</b>PERFECT</div>
      <div class="jb great"><b>${jc.great}</b>GREAT</div>
      <div class="jb good"><b>${jc.good}</b>GOOD</div>
      <div class="jb miss"><b>${jc.miss}</b>MISS</div>
    `;
    showScreen("result");
  }

  document.getElementById("btn-retry").addEventListener("click", () => startGame(currentSong));
  document.getElementById("btn-back").addEventListener("click", () => showScreen("title"));
})();
