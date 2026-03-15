"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/hooks/useApi";
import type { Experiment, ExperimentTask, WSMessage, BrainData } from "@/lib/types";
import BrainViz from "./BrainViz";

/** Play a short tone using the Web Audio API. */
function playTone(frequency: number, durationMs: number) {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = frequency;
    gain.gain.value = 0.3;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);
    osc.stop(ctx.currentTime + durationMs / 1000);
  } catch {
    // Audio not available — ignore
  }
}

interface ExperimentFlowProps {
  userId: string;
  brainData: BrainData | null;
  onRegisterHandler: (handler: (msg: WSMessage) => void) => void;
  onComplete: () => void;
}

type ExperimentState = "idle" | "loading" | "task_active" | "interpreting" | "complete";

export default function ExperimentFlow({ userId, brainData, onRegisterHandler, onComplete }: ExperimentFlowProps) {
  const [state, setState] = useState<ExperimentState>("idle");
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [tasks, setTasks] = useState<ExperimentTask[]>([]);
  const [currentTaskIndex, setCurrentTaskIndex] = useState(0);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [interpretation, setInterpretation] = useState("");
  const [summary, setSummary] = useState("");
  const [confidence, setConfidence] = useState<Record<string, number>>({});
  const [error, setError] = useState("");

  const startExperiment = useCallback(async () => {
    setState("loading");
    setError("");
    setTasks([]);
    setCurrentTaskIndex(0);
    try {
      const exp = await api<Experiment & { all_tasks?: ExperimentTask[] }>(`/api/experiments/${userId}/start`, {
        method: "POST",
        body: JSON.stringify({ phase: 1 }),
      });
      setExperiment(exp);
      // Populate all tasks from the API response
      if (exp.all_tasks && exp.all_tasks.length > 0) {
        setTasks(exp.all_tasks);
      } else if (exp.current_task) {
        setTasks([exp.current_task]);
      }
      setState("task_active");
    } catch (e: unknown) {
      setError((e as Error).message);
      setState("idle");
    }
  }, [userId]);

  // Handle experiment-related WebSocket messages
  useEffect(() => {
    onRegisterHandler((msg: WSMessage) => {
      if (msg.type === "experiment_started") {
        const m = msg as { type: "experiment_started"; experiment_id: string; total_tasks: number; first_task: ExperimentTask | null; all_tasks?: ExperimentTask[] };
        if (m.all_tasks && m.all_tasks.length > 0) {
          setTasks(m.all_tasks);
        } else if (m.first_task) {
          setTasks((prev) => [...prev, m.first_task!]);
        }
      } else if (msg.type === "experiment_instruction") {
        const m = msg as { type: "experiment_instruction"; task_id: string; task_type: string; instruction: string; duration_seconds: number };
        setTasks((prev) => {
          const exists = prev.some((t) => t.id === m.task_id);
          if (exists) return prev;
          return [...prev, {
            id: m.task_id,
            experiment_id: experiment?.id || "",
            task_order: prev.length,
            task_type: m.task_type,
            instruction: m.instruction,
            duration_seconds: m.duration_seconds,
            interpretation: "",
            started_at: null,
            completed_at: null,
          }];
        });
        setTimeRemaining(m.duration_seconds);
        setState("task_active");
      } else if (msg.type === "experiment_interpretation") {
        const m = msg as { type: "experiment_interpretation"; task_id: string; interpretation: string };
        setInterpretation(m.interpretation);
        setState("interpreting");
      } else if (msg.type === "experiment_complete") {
        const m = msg as { type: "experiment_complete"; discrimination_summary: string; confidence: Record<string, number> };
        setSummary(m.discrimination_summary);
        setConfidence(m.confidence);
        setState("complete");
      }
    });
  }, [experiment, onRegisterHandler]);

  // Whether the current task's timer was started (to distinguish "not started" 0 from "finished" 0)
  const timerStartedRef = useRef(false);
  const autoCompletingRef = useRef(false);

  // Countdown timer with audio cues
  useEffect(() => {
    if (state !== "task_active" || timeRemaining <= 0) return;
    timerStartedRef.current = true;
    const interval = setInterval(() => {
      setTimeRemaining((t) => {
        const next = t - 1;
        if (next === 2) playTone(660, 200);   // warning tone
        if (next === 1) playTone(880, 200);   // almost done
        if (next <= 0) {
          playTone(1047, 400);                 // completion tone (C6)
          clearInterval(interval);
          return 0;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [state, timeRemaining]);

  // Auto-complete task when timer reaches 0
  useEffect(() => {
    if (state === "task_active" && timeRemaining === 0 && timerStartedRef.current && !autoCompletingRef.current) {
      autoCompletingRef.current = true;
      completeTask().finally(() => {
        autoCompletingRef.current = false;
        timerStartedRef.current = false;
      });
    }
  }, [state, timeRemaining]);

  const currentTask = tasks[currentTaskIndex];

  const startTask = async () => {
    if (!currentTask || !experiment) return;
    try {
      await api(`/api/experiments/${userId}/tasks/${currentTask.id}/start`, { method: "POST" });
      playTone(523, 150); // C5 — task start cue
      setTimeRemaining(currentTask.duration_seconds);
      timerStartedRef.current = false; // will be set true by the timer effect
      setState("task_active");
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const completeTask = useCallback(async () => {
    if (!currentTask || !experiment) return;
    setState("interpreting");
    try {
      const result = await api<{ interpretation: string; completed_tasks: number; total_tasks: number }>(
        `/api/experiments/${userId}/tasks/${currentTask.id}/complete`,
        { method: "POST" },
      );
      // For neutral tasks (empty interpretation), auto-advance to next task
      if (!result.interpretation && currentTaskIndex < tasks.length - 1) {
        setInterpretation("");
        setCurrentTaskIndex((i) => i + 1);
        setState("task_active");
        setTimeRemaining(0);
      } else if (result.interpretation) {
        // Non-neutral: WS handler will set interpretation and state
        // But as a fallback, set it from the API response too
        setInterpretation(result.interpretation);
        setState("interpreting");
      }
    } catch (e: unknown) {
      setError((e as Error).message);
      setState("task_active");
    }
  }, [currentTask, experiment, userId, currentTaskIndex, tasks.length]);

  const nextTask = () => {
    setInterpretation("");
    setCurrentTaskIndex((i) => i + 1);
    setState("task_active");
    setTimeRemaining(0);
    timerStartedRef.current = false;
  };

  const finalizeExperiment = async () => {
    if (!experiment) return;
    setState("loading");
    try {
      const result = await api<{ discrimination_summary: string; confidence: Record<string, number> }>(
        `/api/experiments/${userId}/experiments/${experiment.id}/finalize`,
        { method: "POST" }
      );
      setSummary(result.discrimination_summary);
      setConfidence(result.confidence);
      setState("complete");
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  // ─── Render states ───

  if (state === "idle") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
        <div className="text-center max-w-lg">
          <h2 className="text-2xl font-bold text-white mb-3">Brain Learning</h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            NEURON will guide you through a series of mental imagery exercises to learn your unique
            brain patterns for coding, art, and music. This takes about 15 minutes.
          </p>
          <p className="text-slate-500 text-xs mt-3">
            Make sure your Muse Athena is connected and you&apos;re in a quiet environment.
          </p>
        </div>
        <button
          onClick={startExperiment}
          className="px-8 py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-medium transition-colors"
        >
          Start Brain Learning
        </button>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Claude is designing your experiment...</p>
        </div>
      </div>
    );
  }

  if (state === "complete") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
        <div className="text-center max-w-lg">
          <div className="text-4xl mb-4">&#x2713;</div>
          <h2 className="text-2xl font-bold text-white mb-3">Learning Complete</h2>
          {summary && (
            <div className="bg-slate-800/50 rounded-lg p-4 mb-4 text-left">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Discrimination Summary</p>
              <p className="text-sm text-slate-300 italic">&ldquo;{summary}&rdquo;</p>
            </div>
          )}
          <div className="flex gap-4 justify-center mb-4">
            {Object.entries(confidence).map(([domain, conf]) => (
              <div key={domain} className="text-center">
                <div className="text-lg font-bold text-white">{Math.round(conf * 100)}%</div>
                <div className="text-xs text-slate-400 capitalize">{domain}</div>
              </div>
            ))}
          </div>
        </div>
        <button
          onClick={onComplete}
          className="px-8 py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-medium transition-colors"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  // Task active or interpreting
  return (
    <div className="flex flex-col h-full">
      {/* Progress bar */}
      <div className="px-4 py-2 border-b border-slate-800">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">
            Task {currentTaskIndex + 1} of {tasks.length || "?"}
          </span>
          {currentTask && (
            <span className="text-xs font-mono text-slate-500 capitalize">
              {currentTask.task_type}
            </span>
          )}
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1">
          <div
            className="h-1 rounded-full bg-cyan-500 transition-all duration-300"
            style={{ width: `${tasks.length ? ((currentTaskIndex + 1) / tasks.length) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 gap-6">
        {state === "task_active" && currentTask && (
          <>
            <p className="text-lg text-white text-center max-w-md leading-relaxed">
              {currentTask.instruction}
            </p>

            {timeRemaining > 0 ? (
              <>
                {/* Circular timer */}
                <div className="relative w-24 h-24">
                  <svg className="w-24 h-24 -rotate-90" viewBox="0 0 96 96">
                    <circle cx="48" cy="48" r="42" fill="none" stroke="#1e293b" strokeWidth="6" />
                    <circle
                      cx="48" cy="48" r="42" fill="none" stroke="#06b6d4" strokeWidth="6"
                      strokeDasharray={`${(timeRemaining / currentTask.duration_seconds) * 264} 264`}
                      strokeLinecap="round"
                      className="transition-all duration-1000"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xl font-mono text-white">{timeRemaining}s</span>
                  </div>
                </div>

                {/* Mini brain viz during recording */}
                <div className="w-full max-w-sm">
                  <BrainViz data={brainData} compact />
                </div>

                <p className="text-xs text-slate-500">
                  {timeRemaining > 2 ? "Recording..." : "Almost done..."}
                </p>
              </>
            ) : (
              <button
                onClick={startTask}
                className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-medium transition-colors"
              >
                Begin Recording
              </button>
            )}
          </>
        )}

        {state === "interpreting" && (
          <>
            {interpretation ? (
              <div className="max-w-md text-center">
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Claude&apos;s Interpretation</p>
                <p className="text-sm text-slate-300 italic leading-relaxed">&ldquo;{interpretation}&rdquo;</p>
                {currentTaskIndex < tasks.length - 1 ? (
                  <button
                    onClick={nextTask}
                    className="mt-4 px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-sm transition-colors"
                  >
                    Next Task
                  </button>
                ) : (
                  <button
                    onClick={finalizeExperiment}
                    className="mt-4 px-6 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm transition-colors"
                  >
                    Finalize &amp; Build Profile
                  </button>
                )}
              </div>
            ) : (
              <div className="text-center">
                <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                <p className="text-sm text-slate-400">Claude is analyzing your brain data...</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
