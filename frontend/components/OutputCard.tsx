"use client";

import ModeIndicator from "./ModeIndicator";
import type { Output } from "@/lib/types";

interface OutputCardProps {
  output: Output;
  onClick?: () => void;
}

export default function OutputCard({ output, onClick }: OutputCardProps) {
  const time = output.created_at
    ? new Date(output.created_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  const interpretation = output.neuron_header
    ?.replace(/^[#<!-]*\s*NEURON:\s*/i, "")
    ?.replace(/\s*\|.*$/, "")
    ?.replace(/-->$/, "")
    ?.trim() || "";

  const fileUrl = `/api/gallery/${output.user_id}/${output.id}/file`;

  return (
    <div
      onClick={onClick}
      className="group bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden hover:border-slate-600 transition-all cursor-pointer"
    >
      {/* Preview */}
      <div className="aspect-video bg-slate-950 relative overflow-hidden">
        {output.file_type === "png" || output.file_type === "jpg" ? (
          <img
            src={fileUrl}
            alt={interpretation || "AI generated art"}
            className="w-full h-full object-cover"
          />
        ) : output.file_type === "mp3" ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <span className="text-4xl opacity-40">&#x266A;</span>
            <audio
              src={fileUrl}
              controls
              className="w-4/5 h-8"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        ) : output.file_type === "html" || output.file_type === "svg" ? (
          <iframe
            src={fileUrl}
            className="w-full h-full border-0 pointer-events-none scale-[0.5] origin-top-left"
            style={{ width: "200%", height: "200%" }}
            sandbox="allow-scripts"
            title={output.id}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <span className="text-3xl text-slate-700 font-mono">.{output.file_type}</span>
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      </div>

      {/* Meta */}
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <ModeIndicator mode={output.detected_mode} />
          <span className="text-[10px] text-slate-500">{time}</span>
        </div>
        {interpretation && (
          <p className="text-xs text-slate-400 line-clamp-2">{interpretation}</p>
        )}
      </div>
    </div>
  );
}
