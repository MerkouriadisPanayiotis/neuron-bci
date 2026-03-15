"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/hooks/useApi";
import ModeIndicator from "@/components/ModeIndicator";
import type { User, NeuralProfile, Experiment } from "@/lib/types";

export default function ProfilePage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.userId as string;

  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<NeuralProfile | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);

  useEffect(() => {
    api<User>(`/api/users/${userId}`).then(setUser).catch(() => {});
    api<NeuralProfile>(`/api/experiments/${userId}/profile`).then(setProfile).catch(() => {});
    api<Experiment[]>(`/api/experiments/${userId}`).then(setExperiments).catch(() => {});
  }, [userId]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800/50">
        <button
          onClick={() => router.push(`/dashboard/${userId}`)}
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          &larr; Dashboard
        </button>
        <h1 className="text-sm font-medium text-white">Neural Profile</h1>
        <div />
      </header>

      <div className="flex-1 p-6 max-w-3xl mx-auto w-full space-y-6">
        {/* User info */}
        <div className="flex items-center gap-4">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-2xl"
            style={{ backgroundColor: user.avatar_color }}
          >
            {user.name[0].toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{user.name}</h2>
            <p className="text-sm text-slate-500">
              Learning phase: {profile?.learning_phase || 0}/4
            </p>
          </div>
        </div>

        {/* Confidence scores */}
        {profile?.confidence && Object.keys(profile.confidence).length > 0 && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
            <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-3">Confidence Scores</h3>
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(profile.confidence).map(([domain, conf]) => (
                <div key={domain} className="text-center">
                  <ModeIndicator mode={domain} confidence={conf} large />
                  <div className="mt-2 w-full bg-slate-800 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${conf * 100}%`,
                        backgroundColor:
                          domain === "code" ? "#3b82f6" : domain === "art" ? "#a855f7" : "#ec4899",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Discrimination summary */}
        {profile?.discrimination_summary && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
            <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-3">
              Discrimination Summary
            </h3>
            <p className="text-sm text-slate-300 italic leading-relaxed">
              &ldquo;{profile.discrimination_summary}&rdquo;
            </p>
          </div>
        )}

        {/* Domain baselines */}
        {profile?.domain_baselines && Object.keys(profile.domain_baselines).length > 0 && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
            <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-3">
              Domain Baselines
            </h3>
            <div className="space-y-3">
              {Object.entries(profile.domain_baselines).map(([domain, bands]) => (
                <div key={domain}>
                  <div className="text-xs text-slate-300 capitalize mb-1">{domain}</div>
                  <div className="flex gap-2 flex-wrap">
                    {Object.entries(bands).map(([band, stats]) => (
                      <div
                        key={band}
                        className="bg-slate-800/50 rounded px-2 py-1 text-[10px] font-mono text-slate-400"
                      >
                        {band}: {typeof stats === "object" && stats !== null && "mean" in stats
                          ? (stats as { mean: number }).mean.toFixed(3)
                          : typeof stats === "number"
                          ? (stats as number).toFixed(3)
                          : "—"}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Claude observations */}
        {profile?.claude_observations && profile.claude_observations.length > 0 && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
            <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-3">
              Claude&apos;s Observations
            </h3>
            <div className="space-y-2">
              {profile.claude_observations.map((obs, i) => (
                <div key={i} className="border-l-2 border-slate-700 pl-3">
                  <div className="text-[10px] text-slate-500 uppercase">{obs.task_type}</div>
                  <p className="text-xs text-slate-400 italic">{obs.observation}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Experiment history */}
        {experiments.length > 0 && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
            <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-3">
              Experiment History
            </h3>
            <div className="space-y-2">
              {experiments.map((exp) => (
                <div
                  key={exp.id}
                  className="flex items-center justify-between py-2 border-b border-slate-800/50 last:border-0"
                >
                  <div>
                    <span className="text-xs text-slate-300">Phase {exp.phase}</span>
                    <span className="text-xs text-slate-600 ml-2">
                      {exp.completed_tasks}/{exp.total_tasks} tasks
                    </span>
                  </div>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full ${
                      exp.status === "completed"
                        ? "bg-green-900/30 text-green-400"
                        : exp.status === "active"
                        ? "bg-cyan-900/30 text-cyan-400"
                        : "bg-slate-800 text-slate-500"
                    }`}
                  >
                    {exp.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {(!profile || profile.learning_phase === 0) && (
          <div className="text-center py-12">
            <div className="text-4xl mb-3 opacity-30">&#x25CB;</div>
            <p className="text-slate-500 mb-4">No neural profile yet</p>
            <button
              onClick={() => router.push(`/experiment/${userId}`)}
              className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-sm transition-colors"
            >
              Start Brain Learning
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
