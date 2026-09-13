/*
 * songs.js
 * 楽曲データの定義。BPM・コード進行・各パートのステップパターンから
 * 「音声イベント（演奏データ）」と「譜面（タップノーツ）」を
 * 同一のソースから同時生成することで、音楽と譜面が完全に同期する。
 */
(function (global) {
  "use strict";

  const semi = global.RG.semitoneRatio;

  const CHORD_INTERVALS = {
    maj: [0, 4, 7],
    min: [0, 3, 7],
  };

  function chordFreqs(rootHz, chord) {
    return CHORD_INTERVALS[chord.quality].map((iv) => rootHz * semi(chord.rootOffset + iv));
  }

  // 16ステップ(16分音符)パターンから絶対時間へ変換するビルダー
  function buildSong(def) {
    const stepDur = 60 / def.bpm / 4; // 16分音符の長さ(秒)
    const barDur = stepDur * 16;
    const audioEvents = [];
    const chartNotes = [];

    for (let bar = 0; bar < def.bars; bar++) {
      const chord = def.progression[bar % def.progression.length];
      const barStart = bar * barDur;
      const rootFreqBass = def.bassRoot * semi(chord.rootOffset);
      const leadChordFreqs = chordFreqs(def.leadRoot, chord);

      const p = def.pattern;

      p.kick.forEach((step) => {
        const t = barStart + step * stepDur;
        audioEvents.push({ time: t, type: "kick" });
        chartNotes.push({ time: t, lane: def.lanes.kick });
      });

      p.snare.forEach((step) => {
        const t = barStart + step * stepDur;
        audioEvents.push({ time: t, type: def.snareType || "snare" });
        chartNotes.push({ time: t, lane: def.lanes.snare });
      });

      p.hihat.forEach((step) => {
        const t = barStart + step * stepDur;
        const open = p.hihatOpen && p.hihatOpen.includes(step);
        audioEvents.push({ time: t, type: "hihat", open });
      });

      p.bass.forEach((step, i) => {
        const t = barStart + step * stepDur;
        const iv = def.bassIntervals ? def.bassIntervals[i % def.bassIntervals.length] : 0;
        const f = rootFreqBass * semi(iv);
        audioEvents.push({ time: t, type: "bass", freq: f, dur: stepDur * 1.8 });
        chartNotes.push({ time: t, lane: def.lanes.bass });
      });

      p.lead.forEach((step, i) => {
        const t = barStart + step * stepDur;
        const f = leadChordFreqs[def.leadToneSeq[i % def.leadToneSeq.length]];
        audioEvents.push({
          time: t,
          type: "lead",
          freq: f,
          dur: stepDur * (def.leadSustainSteps || 2.2),
          leadType: def.leadType,
        });
        chartNotes.push({ time: t, lane: def.lanes.lead });
      });
    }

    const duration = def.bars * barDur;
    chartNotes.sort((a, b) => a.time - b.time);
    audioEvents.sort((a, b) => a.time - b.time);

    return {
      id: def.id,
      name: def.name,
      genre: def.genre,
      bpm: def.bpm,
      duration,
      audioEvents,
      chartNotes,
      themeColor: def.themeColor,
      themeColor2: def.themeColor2,
    };
  }

  // ================= ロック =================
  // Em - C - G - D (i - VI - III - VII) の定番ロック進行
  const rockDef = {
    id: "rock01",
    name: "RED IGNITION",
    genre: "ROCK",
    bpm: 148,
    bars: 48,
    bassRoot: 82.407, // E2
    leadRoot: 164.814, // E3
    themeColor: "#ff3b5c",
    themeColor2: "#ff9a3b",
    progression: [
      { rootOffset: 0, quality: "min" }, // Em
      { rootOffset: 8, quality: "maj" }, // C
      { rootOffset: 3, quality: "maj" }, // G
      { rootOffset: 10, quality: "maj" }, // D
    ],
    lanes: { kick: 0, snare: 1, bass: 2, lead: 3 },
    leadType: "rock",
    leadToneSeq: [0, 1, 2, 1],
    bassIntervals: [0, 0],
    leadSustainSteps: 1.8,
    snareType: "snare",
    pattern: {
      kick: [0, 8],
      snare: [4, 12],
      hihat: [0, 2, 4, 6, 8, 10, 12, 14],
      hihatOpen: [14],
      bass: [2, 10],
      lead: [6, 14],
    },
  };

  // ================= ポップス =================
  // C - G - Am - F (I - V - vi - IV) の王道ポップ進行
  const popDef = {
    id: "pop01",
    name: "CANDY SKYLINE",
    genre: "POPS",
    bpm: 124,
    bars: 48,
    bassRoot: 65.406, // C2
    leadRoot: 261.626, // C4
    themeColor: "#35e0ff",
    themeColor2: "#ff5fd8",
    progression: [
      { rootOffset: 0, quality: "maj" }, // C
      { rootOffset: 7, quality: "maj" }, // G
      { rootOffset: 9, quality: "min" }, // Am
      { rootOffset: 5, quality: "maj" }, // F
    ],
    lanes: { kick: 0, snare: 1, bass: 2, lead: 3 },
    leadType: "pop",
    leadToneSeq: [0, 2, 1, 2],
    bassIntervals: [0, 7],
    leadSustainSteps: 2.4,
    snareType: "clap",
    pattern: {
      kick: [0, 4, 8, 12],
      snare: [4, 12],
      hihat: [0, 2, 4, 6, 8, 10, 12, 14],
      hihatOpen: [6, 14],
      bass: [2, 6, 10, 14],
      lead: [2, 10],
    },
  };

  const SONGS = [buildSong(rockDef), buildSong(popDef)];

  global.RG = global.RG || {};
  global.RG.SONGS = SONGS;
})(window);
