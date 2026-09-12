/*
 * visualizer.js
 * 音楽（周波数解析データ）に反応する背景ビジュアル。
 * 実写映像の代わりに、楽曲のビートに同期したジェネラティブ映像を描画する。
 */
(function (global) {
  "use strict";

  class Visualizer {
    constructor(color1, color2) {
      this.color1 = color1;
      this.color2 = color2;
      this.particles = [];
      this.lastKickPulse = 0;
      this.pulseAmount = 0;
      for (let i = 0; i < 46; i++) {
        this.particles.push({
          x: Math.random(),
          y: Math.random(),
          r: 1 + Math.random() * 2.4,
          speed: 0.02 + Math.random() * 0.05,
          drift: (Math.random() - 0.5) * 0.02,
        });
      }
    }

    triggerPulse() {
      this.pulseAmount = 1;
    }

    draw(ctx, w, h, freqData, t) {
      ctx.clearRect(0, 0, w, h);

      // ベースグラデーション
      const grad = ctx.createRadialGradient(w / 2, h * 0.4, 0, w / 2, h * 0.4, Math.max(w, h) * 0.8);
      grad.addColorStop(0, this._withAlpha(this.color1, 0.16 + this.pulseAmount * 0.18));
      grad.addColorStop(0.5, this._withAlpha(this.color2, 0.08));
      grad.addColorStop(1, "rgba(4,3,8,1)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      // 周波数バー（画面下部、控えめに）
      if (freqData) {
        const bars = 40;
        const step = Math.floor(freqData.length / bars);
        const bw = w / bars;
        for (let i = 0; i < bars; i++) {
          const v = freqData[i * step] / 255;
          const bh = v * h * 0.22;
          ctx.fillStyle = this._withAlpha(i % 2 === 0 ? this.color1 : this.color2, 0.16);
          ctx.fillRect(i * bw, h - bh, bw - 2, bh);
        }
      }

      // 浮遊パーティクル
      ctx.save();
      this.particles.forEach((p) => {
        p.y -= p.speed * 0.01;
        p.x += p.drift * 0.01;
        if (p.y < -0.02) p.y = 1.02;
        if (p.x < -0.02) p.x = 1.02;
        if (p.x > 1.02) p.x = -0.02;
        const px = p.x * w;
        const py = p.y * h;
        ctx.beginPath();
        ctx.fillStyle = this._withAlpha("#ffffff", 0.18 + this.pulseAmount * 0.15);
        ctx.arc(px, py, p.r + this.pulseAmount * 1.5, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();

      // ビートパルス（キック検出時に外周が光る）
      if (this.pulseAmount > 0.001) {
        ctx.save();
        ctx.strokeStyle = this._withAlpha(this.color1, this.pulseAmount * 0.5);
        ctx.lineWidth = 10 + this.pulseAmount * 30;
        ctx.beginPath();
        ctx.rect(4, 4, w - 8, h - 8);
        ctx.stroke();
        ctx.restore();
        this.pulseAmount *= 0.86;
      }
    }

    _withAlpha(hex, alpha) {
      const c = this._hexToRgb(hex);
      return `rgba(${c.r},${c.g},${c.b},${alpha})`;
    }

    _hexToRgb(hex) {
      const h = hex.replace("#", "");
      const bigint = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
      return { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 };
    }
  }

  global.RG = global.RG || {};
  global.RG.Visualizer = Visualizer;
})(window);
