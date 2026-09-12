/*
 * game.js
 * ゲーム本体: 楽曲のスケジューリング、ノーツの描画、入力判定、
 * スコア・コンボ計算を担当する。
 */
(function (global) {
  "use strict";

  const LANE_KEYS = ["d", "f", "j", "k"];
  const APPROACH_TIME = 1.55; // ノーツが出現してから判定ラインに到達するまでの秒数
  const WINDOW = { perfect: 0.05, great: 0.1, good: 0.16 };
  const JUDGE_SCORE = { perfect: 1000, great: 700, good: 300, miss: 0 };
  const COUNT_IN_BEATS = 4;

  class Game {
    constructor(engine, canvas) {
      this.engine = engine;
      this.canvas = canvas;
      this.ctx2d = canvas.getContext("2d");
      this.visualizer = null;
      this.song = null;
      this.notes = [];
      this.state = "idle"; // idle | countdown | playing | paused | finished
      this.songStartTime = 0; // AudioContext 時刻での曲頭
      this.pauseElapsed = 0;
      this.rafId = null;

      this.score = 0;
      this.combo = 0;
      this.maxCombo = 0;
      this.judgeCounts = { perfect: 0, great: 0, good: 0, miss: 0 };

      this.callbacks = {};

      this._resize = this._resize.bind(this);
      window.addEventListener("resize", this._resize);
      this._resize();
    }

    on(name, fn) {
      this.callbacks[name] = fn;
    }

    _emit(name, payload) {
      if (this.callbacks[name]) this.callbacks[name](payload);
    }

    _resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = this.canvas.getBoundingClientRect();
      this.canvas.width = rect.width * dpr;
      this.canvas.height = rect.height * dpr;
      this.ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.width = rect.width;
      this.height = rect.height;
      this.hitY = this.height - 118;
      this.spawnY = -40;
      const laneW = Math.min(this.width * 0.7, 460) / 4;
      this.laneW = laneW;
      this.laneStartX = this.width / 2 - laneW * 2;
    }

    loadSong(song) {
      this.song = song;
      this.visualizer = new global.RG.Visualizer(song.themeColor, song.themeColor2);
      this.notes = song.chartNotes.map((n, i) => ({
        id: i,
        time: n.time,
        lane: n.lane,
        judged: false,
        result: null,
      }));
      this.score = 0;
      this.combo = 0;
      this.maxCombo = 0;
      this.judgeCounts = { perfect: 0, great: 0, good: 0, miss: 0 };
      this._nextEventIndex = 0;
      this._activeJudgeFlash = null;
    }

    start() {
      this.engine.ensureContext();
      this.engine.resume();
      this.state = "countdown";
      const beatDur = 60 / this.song.bpm;
      const now = this.engine.currentTime;
      const countStart = now + 0.15;

      for (let i = 0; i < COUNT_IN_BEATS; i++) {
        this.engine.playCountClick(countStart + i * beatDur, i === 0);
      }

      this.songStartTime = countStart + COUNT_IN_BEATS * beatDur;
      this._scheduleAllAudio();
      this._runCountdownUI(countStart, beatDur);

      this._loop = this._loop.bind(this);
      this.rafId = requestAnimationFrame(this._loop);
    }

    _runCountdownUI(countStart, beatDur) {
      const el = document.getElementById("countdown");
      const labels = ["3", "2", "1", "GO!"];
      labels.forEach((label, i) => {
        const delayMs = Math.max(0, (countStart + i * beatDur - this.engine.currentTime) * 1000);
        setTimeout(() => {
          el.textContent = label;
          el.style.animation = "none";
          void el.offsetWidth;
          el.style.animation = "judgePop 0.4s ease-out";
          if (label === "GO!") {
            setTimeout(() => {
              el.textContent = "";
            }, 400);
          }
        }, delayMs);
      });
    }

    _scheduleAllAudio() {
      const engine = this.engine;
      const t0 = this.songStartTime;
      this.song.audioEvents.forEach((ev) => {
        const time = t0 + ev.time;
        switch (ev.type) {
          case "kick":
            engine.playKick(time);
            break;
          case "snare":
            engine.playSnare(time);
            break;
          case "clap":
            engine.playClap(time);
            break;
          case "hihat":
            engine.playHihat(time, { open: ev.open });
            break;
          case "bass":
            engine.playBass(time, ev.freq, ev.dur);
            break;
          case "lead":
            engine.playLead(time, ev.freq, ev.dur, { type: ev.leadType });
            break;
        }
      });
    }

    pause() {
      if (this.state !== "playing") return;
      this.state = "paused";
      this.pauseElapsed = this.engine.currentTime - this.songStartTime;
      this.engine.ctx.suspend();
      cancelAnimationFrame(this.rafId);
    }

    resume() {
      if (this.state !== "paused") return;
      this.engine.ctx.resume().then(() => {
        this.state = "playing";
        this.rafId = requestAnimationFrame(this._loop);
      });
    }

    stop() {
      cancelAnimationFrame(this.rafId);
      this.state = "idle";
      if (this.engine.ctx) {
        this.engine.master.gain.setValueAtTime(this.engine.master.gain.value, this.engine.currentTime);
      }
    }

    getElapsed() {
      return this.engine.currentTime - this.songStartTime;
    }

    _loop() {
      if (this.state === "paused" || this.state === "idle" || this.state === "finished") return;

      const elapsed = this.getElapsed();

      if (elapsed >= 0 && this.state === "countdown") {
        this.state = "playing";
      }

      this._autoMiss(elapsed);
      this._draw(elapsed);
      this._emit("progress", Math.min(1, Math.max(0, elapsed / this.song.duration)));

      if (elapsed > this.song.duration + 2.2) {
        this._finish();
        return;
      }

      this.rafId = requestAnimationFrame(this._loop);
    }

    _autoMiss(elapsed) {
      for (const note of this.notes) {
        if (note.judged) continue;
        if (elapsed - note.time > WINDOW.good) {
          note.judged = true;
          note.result = "miss";
          this.judgeCounts.miss++;
          this.combo = 0;
          this._showJudge("miss");
        }
      }
    }

    handleLaneInput(lane) {
      if (this.state !== "playing") return;
      const elapsed = this.getElapsed();
      let best = null;
      let bestDt = Infinity;
      for (const note of this.notes) {
        if (note.judged || note.lane !== lane) continue;
        const dt = Math.abs(note.time - elapsed);
        if (dt < bestDt) {
          bestDt = dt;
          best = note;
        }
      }
      if (best && bestDt <= WINDOW.good) {
        this._judgeNote(best, bestDt);
      }
      this._flashLane(lane);
    }

    _judgeNote(note, dt) {
      note.judged = true;
      let result;
      if (dt <= WINDOW.perfect) result = "perfect";
      else if (dt <= WINDOW.great) result = "great";
      else result = "good";

      note.result = result;
      this.judgeCounts[result]++;
      if (result === "miss") {
        this.combo = 0;
      } else {
        this.combo++;
        this.maxCombo = Math.max(this.maxCombo, this.combo);
        const multiplier = Math.min(2.0, 1 + Math.floor(this.combo / 10) * 0.1);
        this.score += Math.round(JUDGE_SCORE[result] * multiplier);
        this.engine.playHitSound(this.engine.currentTime);
      }
      this._showJudge(result);
      this._emit("score", { score: this.score, combo: this.combo });
    }

    _showJudge(result) {
      this._emit("judge", result);
    }

    _flashLane(lane) {
      this._emit("laneFlash", lane);
    }

    _draw(elapsed) {
      const ctx = this.ctx2d;
      const w = this.width;
      const h = this.height;

      const freqData = this.engine.getFrequencyData();

      // キック検出でビジュアルパルス
      if (!this._lastPulseCheck || elapsed - this._lastPulseCheck > 0.03) {
        this._lastPulseCheck = elapsed;
        const kicks = this.song.audioEvents;
        while (this._pulseIdx === undefined) this._pulseIdx = 0;
        while (this._pulseIdx < kicks.length && kicks[this._pulseIdx].time < elapsed) {
          if (kicks[this._pulseIdx].type === "kick") this.visualizer.triggerPulse();
          this._pulseIdx++;
        }
      }

      this.visualizer.draw(ctx, w, h, freqData, elapsed);

      // レーン
      const laneW = this.laneW;
      const startX = this.laneStartX;
      for (let i = 0; i < 4; i++) {
        const x = startX + i * laneW;
        ctx.fillStyle = i % 2 === 0 ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.045)";
        ctx.fillRect(x, 0, laneW, h);
      }

      // 判定ライン
      ctx.strokeStyle = "rgba(255,255,255,0.55)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(startX, this.hitY);
      ctx.lineTo(startX + laneW * 4, this.hitY);
      ctx.stroke();

      // ノーツ
      for (const note of this.notes) {
        if (note.judged) continue;
        const progress = 1 - (note.time - elapsed) / APPROACH_TIME;
        if (progress < -0.05 || progress > 1.05) continue;
        const y = this.spawnY + (this.hitY - this.spawnY) * progress;
        const x = startX + note.lane * laneW + laneW / 2;
        this._drawNote(ctx, x, y, laneW, note.lane);
      }
    }

    _drawNote(ctx, x, y, laneW, lane) {
      const colors = ["#ff9a3b", "#ff3b5c", "#35e0ff", "#7bff6a"];
      const r = laneW * 0.36;
      ctx.save();
      ctx.shadowColor = colors[lane];
      ctx.shadowBlur = 14;
      ctx.fillStyle = colors[lane];
      ctx.beginPath();
      ctx.roundRect(x - r, y - r * 0.55, r * 2, r * 1.1, 8);
      ctx.fill();
      ctx.restore();
    }

    _finish() {
      this.state = "finished";
      cancelAnimationFrame(this.rafId);
      const total =
        this.judgeCounts.perfect + this.judgeCounts.great + this.judgeCounts.good + this.judgeCounts.miss;
      const weighted =
        this.judgeCounts.perfect * 1 + this.judgeCounts.great * 0.7 + this.judgeCounts.good * 0.4;
      const accuracy = total > 0 ? (weighted / total) * 100 : 0;
      this._emit("finish", {
        score: this.score,
        maxCombo: this.maxCombo,
        judgeCounts: this.judgeCounts,
        accuracy,
      });
    }
  }

  global.RG = global.RG || {};
  global.RG.Game = Game;
  global.RG.LANE_KEYS = LANE_KEYS;
})(window);
