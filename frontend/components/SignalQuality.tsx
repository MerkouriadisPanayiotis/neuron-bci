"use client";

interface SignalQualityProps {
  quality: number;
  horseshoe: number[];
}

const SENSOR_NAMES = ["TP9", "AF7", "AF8", "TP10"];
const QUALITY_LABELS: Record<number, string> = { 1: "Good", 2: "OK", 3: "Bad", 4: "Off" };
const QUALITY_COLORS: Record<number, string> = {
  1: "bg-green-500",
  2: "bg-yellow-500",
  3: "bg-red-500",
  4: "bg-gray-600",
};

export default function SignalQuality({ quality, horseshoe }: SignalQualityProps) {
  const pct = Math.round(quality * 100);
  const color = quality > 0.6 ? "text-green-400" : quality > 0.3 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400 uppercase tracking-wider">Signal</span>
        <span className={`text-sm font-mono font-bold ${color}`}>{pct}%</span>
      </div>
      <div className="w-full bg-slate-800 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${
            quality > 0.6 ? "bg-green-500" : quality > 0.3 ? "bg-yellow-500" : "bg-red-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="grid grid-cols-4 gap-1">
        {horseshoe.map((val, i) => (
          <div key={i} className="flex flex-col items-center gap-0.5">
            <div className={`w-2 h-2 rounded-full ${QUALITY_COLORS[val] || "bg-gray-600"}`} />
            <span className="text-[9px] text-slate-500">{SENSOR_NAMES[i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
