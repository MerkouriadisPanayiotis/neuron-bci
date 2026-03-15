"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useBrainSocket } from "@/hooks/useBrainSocket";
import { api } from "@/hooks/useApi";
import BrainViz from "@/components/BrainViz";
import SignalQuality from "@/components/SignalQuality";
import TrendSparklines from "@/components/TrendSparklines";
import ModeIndicator from "@/components/ModeIndicator";
import GenerationStream from "@/components/GenerationStream";
import type { User, SessionStatus, WSMessage } from "@/lib/types";

export default function DashboardPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.userId as string;

  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<SessionStatus | null>(null);
  const [generationText, setGenerationText] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [detectedMode, setDetectedMode] = useState<string | null>(null);
  const [generationPhase, setGenerationPhase] = useState<string | null>(null);
  const [interpretation, setInterpretation] = useState<string | null>(null);
  const [outputFile, setOutputFile] = useState<{ id: string; file_type: string; media_type: string; user_id?: string } | null>(null);
  const [error, setError] = useState("");

  const handleWsMessage = useCallback((msg: WSMessage) => {
    if (msg.type === "generation_started") {
      setIsGenerating(true);
      setGenerationText("");
      setDetectedMode(null);
      setGenerationPhase("interpreting");
      setInterpretation(null);
      setOutputFile(null);
    } else if (msg.type === "generation_chunk") {
      setGenerationText((prev) => prev + (msg as { text: string }).text);
    } else if ((msg as Record<string, unknown>).type === "generation_phase") {
      const m = msg as Record<string, string>;
      setGenerationPhase(m.phase);
      if (m.mode) setDetectedMode(m.mode);
      if (m.interpretation) setInterpretation(m.interpretation);
    } else if (msg.type === "generation_complete") {
      setIsGenerating(false);
      setGenerationPhase(null);
      const m = msg as { output: { id: string; detected_mode: string; file_type: string; media_type?: string } };
      setDetectedMode(m.output.detected_mode);
      setOutputFile({ id: m.output.id, file_type: m.output.file_type, media_type: m.output.media_type || "", user_id: userId });
    } else if (msg.type === "error") {
      setError((msg as { message: string }).message);
      setIsGenerating(false);
      setGenerationPhase(null);
    }
  }, [userId]);

  const { brainData, connected } = useBrainSocket({ userId, onMessage: handleWsMessage });

  useEffect(() => {
    api<User>(`/api/users/${userId}`).then(setUser).catch(() => router.push("/"));
    api<SessionStatus>(`/api/sessions/${userId}/status`).then(setSession).catch(() => {});
  }, [userId, router]);

  const startSession = async () => {
    try {
      const s = await api<SessionStatus>(`/api/sessions/${userId}/start`, {
        method: "POST",
        body: JSON.stringify({ source: "osc" }),
      });
      setSession(s);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const stopSession = async () => {
    try {
      await api(`/api/sessions/${userId}/stop`, { method: "POST" });
      setSession(null);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const triggerGeneration = async () => {
    try {
      setError("");
      await api(`/api/generate/${userId}`, {
        method: "POST",
        body: JSON.stringify({ mode: "auto" }),
      });
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800/50">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/")} className="text-slate-500 hover:text-slate-300 transition-colors">
            NEURON
          </button>
          <span className="text-slate-700">/</span>
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
              style={{ backgroundColor: user.avatar_color }}
            >
              {user.name[0].toUpperCase()}
            </div>
            <span className="text-sm text-white">{user.name}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
          <button
            onClick={() => router.push(`/experiment/${userId}`)}
            className="text-xs text-slate-400 hover:text-white px-3 py-1 border border-slate-800 rounded-lg transition-colors"
          >
            Brain Learning
          </button>
          <button
            onClick={() => router.push(`/gallery/${userId}`)}
            className="text-xs text-slate-400 hover:text-white px-3 py-1 border border-slate-800 rounded-lg transition-colors"
          >
            Gallery
          </button>
          <button
            onClick={() => router.push(`/profile/${userId}`)}
            className="text-xs text-slate-400 hover:text-white px-3 py-1 border border-slate-800 rounded-lg transition-colors"
          >
            Profile
          </button>
        </div>
      </header>

      {/* Main three-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Brain visualization */}
        <div className="w-72 border-r border-slate-800/50 p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="text-xs text-slate-400 uppercase tracking-wider">Brain Data</h2>
            {session?.active ? (
              <button onClick={stopSession} className="text-[10px] text-red-400 hover:text-red-300">
                Stop
              </button>
            ) : (
              <button onClick={startSession} className="text-[10px] text-cyan-400 hover:text-cyan-300">
                Connect
              </button>
            )}
          </div>

          {brainData ? (
            <>
              <BrainViz data={brainData} />
              <SignalQuality
                quality={brainData.signal_quality}
                horseshoe={brainData.horseshoe}
              />
              <TrendSparklines trend={brainData.trend} />
              <div className="text-[10px] text-slate-600 font-mono">
                Snap #{brainData.snapshot_number} | {Math.round(brainData.session_duration)}s
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-slate-600">
                <div className="text-2xl mb-2 opacity-30">&#x25CB;</div>
                <p className="text-xs">
                  {session?.active
                    ? "Waiting for brain data..."
                    : "Click Connect to start"}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Center: Generation output */}
        <div className="flex-1 flex flex-col border-r border-slate-800/50">
          <GenerationStream
            text={generationText}
            isGenerating={isGenerating}
            detectedMode={detectedMode}
            phase={generationPhase}
            interpretation={interpretation}
            outputFile={outputFile}
          />
        </div>

        {/* Right: Controls */}
        <div className="w-64 p-4 flex flex-col gap-4 overflow-y-auto">
          <h2 className="text-xs text-slate-400 uppercase tracking-wider">Controls</h2>

          {/* Mode detection */}
          {detectedMode && (
            <div>
              <p className="text-[10px] text-slate-500 mb-1">Detected Mode</p>
              <ModeIndicator mode={detectedMode} large />
            </div>
          )}

          {/* Brain learning required banner */}
          {(user.learning_phase ?? 0) < 1 && (
            <div className="bg-amber-900/20 border border-amber-700/50 rounded-xl p-4 text-center">
              <p className="text-sm text-amber-300 font-medium mb-2">
                Brain Learning Required
              </p>
              <p className="text-xs text-amber-400/70 mb-3">
                NEURON needs to learn your unique neural patterns before it can interpret your thoughts.
              </p>
              <button
                onClick={() => router.push(`/experiment/${userId}`)}
                className="w-full py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium transition-all"
              >
                Start Brain Learning
              </button>
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={triggerGeneration}
            disabled={isGenerating || !session?.active || (user.learning_phase ?? 0) < 1}
            className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl font-medium transition-all"
          >
            {isGenerating
              ? "Generating..."
              : (user.learning_phase ?? 0) < 1
              ? "Complete Brain Learning First"
              : "Generate Now"}
          </button>

          {/* Learning status */}
          <div className="bg-slate-900/50 rounded-xl p-3 border border-slate-800">
            <p className="text-[10px] text-slate-500 mb-2">Brain Learning</p>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-300">
                Phase {user.learning_phase}/4
              </span>
              <span className="text-[10px] text-slate-500">
                {user.learning_phase === 0
                  ? "Not started"
                  : user.learning_phase >= 4
                  ? "Fully learned"
                  : "Trained"}
              </span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1">
              <div
                className="h-1 rounded-full bg-cyan-500 transition-all"
                style={{ width: `${(user.learning_phase / 4) * 100}%` }}
              />
            </div>
            {user.confidence && Object.keys(user.confidence).length > 0 && (
              <div className="mt-2 flex gap-1">
                {Object.entries(user.confidence).map(([domain, conf]) => (
                  <div key={domain} className="flex-1 text-center">
                    <div className="text-[10px] font-mono text-slate-400">
                      {Math.round(conf * 100)}%
                    </div>
                    <div className="text-[8px] text-slate-600 capitalize">{domain}</div>
                  </div>
                ))}
              </div>
            )}
            {user.learning_phase > 0 && user.learning_phase < 4 && (
              <button
                onClick={() => router.push(`/experiment/${userId}`)}
                className="mt-2 w-full py-1.5 text-[10px] text-cyan-400 hover:text-white border border-slate-700 hover:border-cyan-600 rounded-lg transition-colors"
              >
                Continue Training (Phase {user.learning_phase + 1})
              </button>
            )}
          </div>

          {/* Session info */}
          {session?.active && (
            <div className="bg-slate-900/50 rounded-xl p-3 border border-slate-800">
              <p className="text-[10px] text-slate-500 mb-1">Session</p>
              <div className="text-xs text-slate-400 font-mono space-y-0.5">
                <div>Source: {session.source.toUpperCase()}</div>
                <div>Snapshots: {brainData?.snapshot_number || 0}</div>
                <div>Signal: {Math.round((brainData?.signal_quality || 0) * 100)}%</div>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-2">
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
