"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/hooks/useApi";
import OutputCard from "@/components/OutputCard";
import ModeIndicator from "@/components/ModeIndicator";
import type { Output } from "@/lib/types";

export default function GalleryPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.userId as string;

  const [outputs, setOutputs] = useState<Output[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [selectedOutput, setSelectedOutput] = useState<Output | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const query = filter ? `?mode=${filter}` : "";
    api<Output[]>(`/api/gallery/${userId}${query}`)
      .then(setOutputs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId, filter]);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800/50">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/dashboard/${userId}`)}
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            &larr; Dashboard
          </button>
        </div>
        <h1 className="text-sm font-medium text-white">Gallery</h1>
        <div className="flex gap-2">
          {[null, "code", "art", "music"].map((mode) => (
            <button
              key={mode || "all"}
              onClick={() => setFilter(mode)}
              className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
                filter === mode
                  ? "border-cyan-500 text-cyan-400"
                  : "border-slate-800 text-slate-500 hover:text-slate-300"
              }`}
            >
              {mode ? mode.toUpperCase() : "ALL"}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : outputs.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-slate-600">
            <div className="text-center">
              <div className="text-4xl mb-3 opacity-30">&#x25A1;</div>
              <p className="text-sm">No outputs yet</p>
              <p className="text-xs text-slate-700 mt-1">
                Generate from your brain data on the dashboard
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {outputs.map((output) => (
              <OutputCard
                key={output.id}
                output={output}
                onClick={() => setSelectedOutput(output)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Full-screen preview modal */}
      {selectedOutput && (
        <div className="fixed inset-0 bg-black/90 z-50 flex flex-col">
          <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <ModeIndicator mode={selectedOutput.detected_mode} />
              <span className="text-xs text-slate-400">
                {selectedOutput.neuron_header
                  ?.replace(/^[#<!-]+\s*NEURON:\s*/i, "")
                  ?.replace(/\s*\|.*$/, "")
                  ?.replace(/-->$/, "")}
              </span>
            </div>
            <button
              onClick={() => setSelectedOutput(null)}
              className="text-slate-400 hover:text-white text-xl transition-colors"
            >
              &#x2715;
            </button>
          </div>
          <div className="flex-1">
            {selectedOutput.file_type === "html" || selectedOutput.file_type === "svg" ? (
              <iframe
                src={`/api/gallery/${userId}/${selectedOutput.id}/file`}
                className="w-full h-full border-0"
                sandbox="allow-scripts"
                title={selectedOutput.id}
              />
            ) : (
              <div className="p-6 font-mono text-sm text-slate-300 overflow-auto h-full">
                <pre>Loading...</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
