/*
 * audio-engine.js
 * Web Audio API による軽量シンセサイザー。
 * ドラム / ベース / リードをすべてオシレーター & ノイズバッファから
 * リアルタイム合成することで、著作権フリーのオリジナル楽曲を
 * ロック / ポップス風に鳴らす。
 */
(function (global) {
  "use strict";

  function semitoneRatio(n) {
    return Math.pow(2, n / 12);
  }

  class SynthEngine {
    constructor() {
      this.ctx = null;
      this.master = null;
      this.analyser = null;
      this.noiseBuffer = null;
    }

    // ユーザー操作の中で呼び出すこと（ブラウザの自動再生制限対策）
    ensureContext() {
      if (this.ctx) return this.ctx;
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new Ctx();

      this.master = this.ctx.createGain();
      this.master.gain.value = 0.9;

      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.75;

      this.master.connect(this.analyser);
      this.analyser.connect(this.ctx.destination);

      this.noiseBuffer = this._buildNoiseBuffer();
      return this.ctx;
    }

    get currentTime() {
      return this.ctx ? this.ctx.currentTime : 0;
    }

    resume() {
      if (this.ctx && this.ctx.state === "suspended") {
        return this.ctx.resume();
      }
      return Promise.resolve();
    }

    _buildNoiseBuffer() {
      const len = this.ctx.sampleRate * 1.0;
      const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
      return buf;
    }

    _noiseSource() {
      const src = this.ctx.createBufferSource();
      src.buffer = this.noiseBuffer;
      src.loop = true;
      return src;
    }

    // ---- 打楽器 ----
    playKick(time, { pitch = 150, tail = 0.22, gain = 1.0 } = {}) {
      const ctx = this.ctx;
      const osc = ctx.createOscillator();
      const amp = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(pitch, time);
      osc.frequency.exponentialRampToValueAtTime(Math.max(30, pitch * 0.25), time + tail);
      amp.gain.setValueAtTime(gain, time);
      amp.gain.exponentialRampToValueAtTime(0.001, time + tail);
      osc.connect(amp).connect(this.master);
      osc.start(time);
      osc.stop(time + tail + 0.02);
    }

    playSnare(time, { gain = 0.85, tail = 0.16 } = {}) {
      const ctx = this.ctx;
      const noise = this._noiseSource();
      const bp = ctx.createBiquadFilter();
      bp.type = "highpass";
      bp.frequency.value = 1500;
      const namp = ctx.createGain();
      namp.gain.setValueAtTime(gain, time);
      namp.gain.exponentialRampToValueAtTime(0.001, time + tail);
      noise.connect(bp).connect(namp).connect(this.master);
      noise.start(time);
      noise.stop(time + tail + 0.02);

      const osc = ctx.createOscillator();
      const oamp = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(190, time);
      oamp.gain.setValueAtTime(gain * 0.6, time);
      oamp.gain.exponentialRampToValueAtTime(0.001, time + 0.09);
      osc.connect(oamp).connect(this.master);
      osc.start(time);
      osc.stop(time + 0.1);
    }

    playHihat(time, { open = false, gain = 0.35 } = {}) {
      const ctx = this.ctx;
      const noise = this._noiseSource();
      const hp = ctx.createBiquadFilter();
      hp.type = "highpass";
      hp.frequency.value = 7000;
      const amp = ctx.createGain();
      const tail = open ? 0.22 : 0.045;
      amp.gain.setValueAtTime(gain, time);
      amp.gain.exponentialRampToValueAtTime(0.001, time + tail);
      noise.connect(hp).connect(amp).connect(this.master);
      noise.start(time);
      noise.stop(time + tail + 0.02);
    }

    playClap(time, { gain = 0.7 } = {}) {
      const ctx = this.ctx;
      for (let i = 0; i < 3; i++) {
        const t = time + i * 0.012;
        const noise = this._noiseSource();
        const bp = ctx.createBiquadFilter();
        bp.type = "bandpass";
        bp.frequency.value = 1200;
        bp.Q.value = 1.2;
        const amp = ctx.createGain();
        amp.gain.setValueAtTime(gain * (1 - i * 0.2), t);
        amp.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
        noise.connect(bp).connect(amp).connect(this.master);
        noise.start(t);
        noise.stop(t + 0.09);
      }
    }

    // ---- ベース ----
    playBass(time, freq, dur, { wave = "sawtooth", gain = 0.55 } = {}) {
      const ctx = this.ctx;
      const osc = ctx.createOscillator();
      osc.type = wave;
      osc.frequency.setValueAtTime(freq, time);
      const lp = ctx.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.setValueAtTime(1200, time);
      lp.frequency.exponentialRampToValueAtTime(300, time + dur);
      const amp = ctx.createGain();
      amp.gain.setValueAtTime(0.0001, time);
      amp.gain.exponentialRampToValueAtTime(gain, time + 0.01);
      amp.gain.exponentialRampToValueAtTime(0.001, time + dur);
      osc.connect(lp).connect(amp).connect(this.master);
      osc.start(time);
      osc.stop(time + dur + 0.02);
    }

    // ---- リード / メロディ ----
    playLead(time, freq, dur, { type = "rock", gain = 0.5 } = {}) {
      const ctx = this.ctx;
      const amp = ctx.createGain();
      amp.gain.setValueAtTime(0.0001, time);
      amp.gain.exponentialRampToValueAtTime(gain, time + 0.008);
      amp.gain.exponentialRampToValueAtTime(0.001, time + dur);
      amp.connect(this.master);

      if (type === "rock") {
        // 2基のオシレーター(ルート+5度)を歪ませてパワーコード風に
        const shaper = ctx.createWaveShaper();
        shaper.curve = this._distortionCurve(28);
        shaper.connect(amp);
        [0, 7].forEach((iv) => {
          const osc = ctx.createOscillator();
          osc.type = "sawtooth";
          osc.frequency.setValueAtTime(freq * semitoneRatio(iv), time);
          osc.connect(shaper);
          osc.start(time);
          osc.stop(time + dur + 0.02);
        });
      } else {
        // 明るいプラック / アルペジオ向けシンセ
        const osc1 = ctx.createOscillator();
        osc1.type = "triangle";
        osc1.frequency.setValueAtTime(freq, time);
        const osc2 = ctx.createOscillator();
        osc2.type = "square";
        osc2.frequency.setValueAtTime(freq * 2, time);
        const osc2gain = ctx.createGain();
        osc2gain.gain.value = 0.18;
        const lp = ctx.createBiquadFilter();
        lp.type = "lowpass";
        lp.frequency.setValueAtTime(4500, time);
        osc1.connect(lp);
        osc2.connect(osc2gain).connect(lp);
        lp.connect(amp);
        osc1.start(time);
        osc1.stop(time + dur + 0.02);
        osc2.start(time);
        osc2.stop(time + dur + 0.02);
      }
    }

    playCountClick(time, accent) {
      const ctx = this.ctx;
      const osc = ctx.createOscillator();
      const amp = ctx.createGain();
      osc.type = "square";
      osc.frequency.value = accent ? 1400 : 900;
      amp.gain.setValueAtTime(0.4, time);
      amp.gain.exponentialRampToValueAtTime(0.001, time + 0.06);
      osc.connect(amp).connect(this.master);
      osc.start(time);
      osc.stop(time + 0.07);
    }

    playHitSound(time) {
      const ctx = this.ctx;
      const osc = ctx.createOscillator();
      const amp = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(1800, time);
      amp.gain.setValueAtTime(0.12, time);
      amp.gain.exponentialRampToValueAtTime(0.001, time + 0.05);
      osc.connect(amp).connect(this.master);
      osc.start(time);
      osc.stop(time + 0.06);
    }

    _distortionCurve(amount) {
      const n = 44100;
      const curve = new Float32Array(n);
      const k = amount;
      for (let i = 0; i < n; i++) {
        const x = (i * 2) / n - 1;
        curve[i] = ((3 + k) * x * 20 * (Math.PI / 180)) / (Math.PI + k * Math.abs(x));
      }
      return curve;
    }

    getFrequencyData() {
      if (!this.analyser) return null;
      const data = new Uint8Array(this.analyser.frequencyBinCount);
      this.analyser.getByteFrequencyData(data);
      return data;
    }
  }

  global.RG = global.RG || {};
  global.RG.SynthEngine = SynthEngine;
  global.RG.semitoneRatio = semitoneRatio;
})(window);
