"use client";

const MODE_CONFIG: Record<string, { label: string; icon: string; color: string; bg: string }> = {
  code: { label: "CODE", icon: "{ }", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/30" },
  art: { label: "ART", icon: "◆", color: "text-purple-400", bg: "bg-purple-500/10 border-purple-500/30" },
  music: { label: "MUSIC", icon: "♪", color: "text-pink-400", bg: "bg-pink-500/10 border-pink-500/30" },
  auto: { label: "AUTO", icon: "◉", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/30" },
};

interface ModeIndicatorProps {
  mode: string;
  confidence?: number;
  large?: boolean;
}

export default function ModeIndicator({ mode, confidence, large = false }: ModeIndicatorProps) {
  const config = MODE_CONFIG[mode] || MODE_CONFIG.auto;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border ${config.bg}`}>
      <span className={`${large ? "text-lg" : "text-sm"} font-mono ${config.color}`}>
        {config.icon}
      </span>
      <span className={`${large ? "text-base" : "text-xs"} font-bold tracking-wider ${config.color}`}>
        {config.label}
      </span>
      {confidence !== undefined && (
        <span className="text-[10px] text-slate-500 font-mono">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}
