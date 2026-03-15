"use client";

import { useRef, useEffect } from "react";
import type { BrainData } from "@/lib/types";

const BAND_COLORS: Record<string, string> = {
  delta: "#8b5cf6",   // purple
  theta: "#06b6d4",   // cyan
  alpha: "#22c55e",   // green
  beta: "#f59e0b",    // amber
  gamma: "#ef4444",   // red
};

const BAND_LABELS = ["delta", "theta", "alpha", "beta", "gamma"];
const BAND_SYMBOLS = ["δ", "θ", "α", "β", "γ"];

interface BrainVizProps {
  data: BrainData | null;
  compact?: boolean;
}

export default function BrainViz({ data, compact = false }: BrainVizProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const smoothBands = useRef<Record<string, number>>({});

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;

    function draw() {
      if (!ctx) return;
      ctx.clearRect(0, 0, w, h);

      // Smooth interpolation
      if (data?.bands) {
        for (const band of BAND_LABELS) {
          const target = Math.abs(data.bands[band] || 0);
          const current = smoothBands.current[band] || 0;
          smoothBands.current[band] = current + (target - current) * 0.15;
        }
      }

      const barWidth = compact ? w / 7 : w / 6;
      const maxBarHeight = h - (compact ? 30 : 60);
      const baseY = h - (compact ? 20 : 40);

      BAND_LABELS.forEach((band, i) => {
        const val = smoothBands.current[band] || 0;
        const barH = Math.min(val * maxBarHeight * 0.8, maxBarHeight);
        const x = (compact ? 8 : 16) + i * barWidth;
        const bw = barWidth * 0.65;

        // Glow effect
        ctx.shadowColor = BAND_COLORS[band];
        ctx.shadowBlur = 12;

        // Bar gradient
        const grad = ctx.createLinearGradient(x, baseY, x, baseY - barH);
        grad.addColorStop(0, BAND_COLORS[band] + "cc");
        grad.addColorStop(1, BAND_COLORS[band] + "44");
        ctx.fillStyle = grad;

        // Rounded bar
        const radius = Math.min(bw / 2, 6);
        ctx.beginPath();
        ctx.moveTo(x, baseY);
        ctx.lineTo(x, baseY - barH + radius);
        ctx.quadraticCurveTo(x, baseY - barH, x + radius, baseY - barH);
        ctx.lineTo(x + bw - radius, baseY - barH);
        ctx.quadraticCurveTo(x + bw, baseY - barH, x + bw, baseY - barH + radius);
        ctx.lineTo(x + bw, baseY);
        ctx.fill();

        ctx.shadowBlur = 0;

        // Label
        ctx.fillStyle = "#94a3b8";
        ctx.font = compact ? "10px monospace" : "12px monospace";
        ctx.textAlign = "center";
        ctx.fillText(BAND_SYMBOLS[i], x + bw / 2, baseY + (compact ? 12 : 16));

        if (!compact) {
          ctx.fillStyle = "#64748b";
          ctx.font = "9px monospace";
          ctx.fillText((data?.bands[band] || 0).toFixed(2), x + bw / 2, baseY + 30);
        }
      });

      // Signal quality ring (top right)
      if (!compact && data) {
        const sq = data.signal_quality;
        const cx = w - 30;
        const cy = 30;
        const r = 18;

        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = "#1e293b";
        ctx.lineWidth = 4;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * sq);
        ctx.strokeStyle = sq > 0.6 ? "#22c55e" : sq > 0.3 ? "#f59e0b" : "#ef4444";
        ctx.lineWidth = 4;
        ctx.stroke();

        ctx.fillStyle = "#e2e8f0";
        ctx.font = "bold 11px monospace";
        ctx.textAlign = "center";
        ctx.fillText(`${Math.round(sq * 100)}%`, cx, cy + 4);
      }

      animRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => cancelAnimationFrame(animRef.current);
  }, [data, compact]);

  return (
    <canvas
      ref={canvasRef}
      className={`w-full ${compact ? "h-32" : "h-64"}`}
      style={{ imageRendering: "auto" }}
    />
  );
}
