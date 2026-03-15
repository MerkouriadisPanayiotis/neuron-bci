"use client";

import { useEffect, useRef, useState } from "react";
import ModeIndicator from "./ModeIndicator";

interface GenerationStreamProps {
  text: string;
  isGenerating: boolean;
  detectedMode: string | null;
  phase: string | null;
  interpretation: string | null;
  outputFile: { id: string; file_type: string; media_type: string; user_id?: string } | null;
}

export default function GenerationStream({
  text, isGenerating, detectedMode, phase, interpretation, outputFile,
}: GenerationStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text]);

  // Auto-open modal when generation completes
  useEffect(() => {
    if (outputFile && !isGenerating) {
      setModalOpen(true);
    }
  }, [outputFile, isGenerating]);

  const outputUrl = outputFile
    ? `/api/gallery/${outputFile.user_id}/${outputFile.id}/file`
    : null;

  // ─── Empty state ───
  if (!text && !isGenerating && !outputFile) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600">
        <div className="text-center">
          <div className="text-4xl mb-3 opacity-30">&#x25C9;</div>
          <p className="text-sm">Waiting for generation...</p>
          <p className="text-xs text-slate-700 mt-1">Brain data will trigger Claude automatically</p>
        </div>
      </div>
    );
  }

  // ─── Phase indicator ───
  const phaseLabel = () => {
    switch (phase) {
      case "interpreting": return "Claude is reading your brain data...";
      case "decided": return `Mode: ${detectedMode?.toUpperCase()} — ${interpretation || ""}`;
      case "generating_image": return "Generating your image...";
      case "generating_music": return "ElevenLabs is composing your music...";
      case "saving": return "Deploying...";
      case "fallback": return "API key not set — saved prompt as text";
      default: return null;
    }
  };

  return (
    <>
      <div className="flex flex-col h-full">
        {/* Status bar */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800">
          <div className="flex items-center gap-2">
            {isGenerating && (
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 bg-cyan-500 rounded-full animate-pulse" />
                <span className="text-xs text-cyan-400 font-mono">GENERATING</span>
              </div>
            )}
            {!isGenerating && outputFile && (
              <button
                onClick={() => setModalOpen(true)}
                className="text-xs text-green-400 font-mono hover:text-green-300 transition-colors"
              >
                COMPLETE — Click to view
              </button>
            )}
          </div>
          {detectedMode && <ModeIndicator mode={detectedMode} />}
        </div>

        {/* Phase message */}
        {phase && isGenerating && (
          <div className="px-3 py-2 bg-slate-900/50 border-b border-slate-800/50">
            <p className="text-xs text-slate-400">{phaseLabel()}</p>
          </div>
        )}

        {/* Interpretation */}
        {interpretation && (
          <div className="px-3 py-2 bg-slate-900/30 border-b border-slate-800/50">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Brain State</p>
            <p className="text-xs text-slate-300 italic">{interpretation}</p>
          </div>
        )}

        {/* Main content area */}
        <div ref={scrollRef} className="flex-1 overflow-auto p-3">
          {/* Completed output preview */}
          {outputFile && !isGenerating && (
            <div className="flex items-center justify-center h-full">
              {outputFile.file_type === "png" || outputFile.file_type === "jpg" ? (
                <button onClick={() => setModalOpen(true)} className="cursor-pointer">
                  <img
                    src={outputUrl!}
                    alt="AI generated art"
                    className="max-w-full max-h-full rounded-lg shadow-2xl hover:opacity-90 transition-opacity"
                  />
                </button>
              ) : outputFile.file_type === "mp3" ? (
                <div className="text-center space-y-4">
                  <div className="text-6xl opacity-30">&#x266A;</div>
                  <audio controls autoPlay src={outputUrl!} className="w-80" />
                  <p className="text-xs text-slate-500">AI-generated from your brain state</p>
                </div>
              ) : outputFile.file_type === "html" ? (
                <div className="text-center space-y-4">
                  <p className="text-sm text-slate-300">Your app is ready</p>
                  <button
                    onClick={() => setModalOpen(true)}
                    className="px-6 py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-medium transition-colors"
                  >
                    Open App
                  </button>
                </div>
              ) : (
                <pre className="font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap break-words w-full">
                  {text}
                </pre>
              )}
            </div>
          )}

          {/* Streaming text (during generation) */}
          {isGenerating && (
            <div>
              <pre className="font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
                {text}
              </pre>
              {(phase === "generating_image" || phase === "generating_music") && (
                <div className="flex items-center justify-center py-8">
                  <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                </div>
              )}
              {phase !== "generating_image" && phase !== "generating_music" && text && (
                <span className="inline-block w-2 h-4 bg-cyan-500 animate-pulse ml-0.5" />
              )}
            </div>
          )}
        </div>
      </div>

      {/* ─── Full-screen modal ─── */}
      {modalOpen && outputFile && outputUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="relative w-full h-full max-w-6xl max-h-[90vh] bg-slate-900 rounded-2xl overflow-hidden border border-slate-700 shadow-2xl flex flex-col">
            {/* Modal header */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900">
              <div className="flex items-center gap-3">
                {detectedMode && <ModeIndicator mode={detectedMode} />}
                {interpretation && (
                  <p className="text-xs text-slate-400 italic truncate max-w-md">{interpretation}</p>
                )}
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg px-2 transition-colors"
              >
                &#x2715;
              </button>
            </div>

            {/* Modal content */}
            <div className="flex-1 overflow-hidden">
              {(outputFile.file_type === "html") ? (
                <iframe
                  src={outputUrl}
                  className="w-full h-full border-0"
                  sandbox="allow-scripts allow-same-origin"
                  title="NEURON generated app"
                />
              ) : (outputFile.file_type === "png" || outputFile.file_type === "jpg") ? (
                <div className="flex items-center justify-center h-full p-4">
                  <img
                    src={outputUrl}
                    alt="AI generated art"
                    className="max-w-full max-h-full object-contain rounded-lg"
                  />
                </div>
              ) : outputFile.file_type === "mp3" ? (
                <div className="flex flex-col items-center justify-center h-full gap-6">
                  <div className="text-8xl opacity-20">&#x266A;</div>
                  <audio controls autoPlay src={outputUrl} className="w-96" />
                </div>
              ) : (
                <pre className="p-4 font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap overflow-auto h-full">
                  {text}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
