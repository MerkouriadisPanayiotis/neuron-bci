"use client";

const BAND_COLORS: Record<string, string> = {
  delta: "#8b5cf6",
  theta: "#06b6d4",
  alpha: "#22c55e",
  beta: "#f59e0b",
  gamma: "#ef4444",
};

const BAND_SYMBOLS: Record<string, string> = {
  delta: "δ",
  theta: "θ",
  alpha: "α",
  beta: "β",
  gamma: "γ",
};

interface TrendSparklinesProps {
  trend: Record<string, number[]>;
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (!values || values.length < 2) return <span className="text-slate-600">—</span>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 80;
  const h = 20;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={w} height={h} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function TrendSparklines({ trend }: TrendSparklinesProps) {
  return (
    <div className="space-y-1">
      <span className="text-xs text-slate-400 uppercase tracking-wider">Trend</span>
      {Object.entries(trend).map(([band, values]) => (
        <div key={band} className="flex items-center gap-2">
          <span className="text-xs font-mono w-4" style={{ color: BAND_COLORS[band] }}>
            {BAND_SYMBOLS[band]}
          </span>
          <Sparkline values={values} color={BAND_COLORS[band]} />
          {values.length >= 2 && (
            <span className="text-[10px] font-mono text-slate-500">
              {(values[values.length - 1] - values[0]) >= 0 ? "+" : ""}
              {(values[values.length - 1] - values[0]).toFixed(3)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
