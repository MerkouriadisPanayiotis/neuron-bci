"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/hooks/useApi";
import type { User } from "@/lib/types";

const AVATAR_COLORS = ["#6366f1", "#8b5cf6", "#06b6d4", "#22c55e", "#f59e0b", "#ef4444", "#ec4899"];

export default function LandingPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [selectedColor, setSelectedColor] = useState(AVATAR_COLORS[0]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<User[]>("/api/users")
      .then(setUsers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const createUser = async () => {
    if (!newName.trim()) return;
    try {
      const user = await api<User>("/api/users", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), avatar_color: selectedColor }),
      });
      router.push(`/dashboard/${user.id}`);
    } catch (e: unknown) {
      alert((e as Error).message);
    }
  };

  const phaseLabel = (phase: number) => {
    if (phase === 0) return "Not calibrated";
    if (phase <= 2) return "Learning...";
    if (phase === 3) return "Verified";
    return "Fully learned";
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      {/* Logo */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-bold tracking-wider mb-2">
          <span className="text-cyan-400">N</span>
          <span className="text-slate-300">E</span>
          <span className="text-slate-300">U</span>
          <span className="text-slate-300">R</span>
          <span className="text-slate-300">O</span>
          <span className="text-cyan-400">N</span>
        </h1>
        <p className="text-slate-500 text-sm tracking-widest uppercase">
          Brain-Computer Interface
        </p>
        <p className="text-slate-600 text-xs mt-1">
          Brainwaves in. Claude interprets. Creative artifacts out.
        </p>
      </div>

      {/* User grid */}
      {loading ? (
        <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-3xl w-full mb-8">
          {users.map((user) => (
            <button
              key={user.id}
              onClick={() => router.push(`/dashboard/${user.id}`)}
              className="group bg-slate-900/50 border border-slate-800 rounded-xl p-5 text-left hover:border-slate-600 transition-all glow-pulse"
            >
              <div className="flex items-center gap-3 mb-3">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-lg"
                  style={{ backgroundColor: user.avatar_color }}
                >
                  {user.name[0].toUpperCase()}
                </div>
                <div>
                  <div className="text-white font-medium">{user.name}</div>
                  <div className="text-[10px] text-slate-500">
                    {phaseLabel(user.learning_phase)}
                  </div>
                </div>
              </div>
              {user.confidence && Object.keys(user.confidence).length > 0 && (
                <div className="flex gap-2">
                  {Object.entries(user.confidence).map(([domain, conf]) => (
                    <div key={domain} className="flex-1 text-center">
                      <div className="text-xs font-mono text-slate-300">
                        {Math.round(conf * 100)}%
                      </div>
                      <div className="text-[9px] text-slate-600 capitalize">{domain}</div>
                    </div>
                  ))}
                </div>
              )}
              {user.learning_phase > 0 && (
                <div className="mt-2 w-full bg-slate-800 rounded-full h-1">
                  <div
                    className="h-1 rounded-full bg-cyan-500"
                    style={{ width: `${(user.learning_phase / 4) * 100}%` }}
                  />
                </div>
              )}
            </button>
          ))}

          {/* Create new */}
          {!creating ? (
            <button
              onClick={() => setCreating(true)}
              className="border-2 border-dashed border-slate-800 rounded-xl p-5 flex items-center justify-center text-slate-600 hover:border-slate-600 hover:text-slate-400 transition-all"
            >
              <span className="text-2xl mr-2">+</span>
              <span>New Profile</span>
            </button>
          ) : (
            <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-5 space-y-3">
              <input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createUser()}
                placeholder="Your name"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <div className="flex gap-2">
                {AVATAR_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setSelectedColor(color)}
                    className={`w-6 h-6 rounded-full transition-all ${
                      selectedColor === color ? "ring-2 ring-white ring-offset-2 ring-offset-slate-900" : ""
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={createUser}
                  className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg py-1.5 text-sm transition-colors"
                >
                  Create
                </button>
                <button
                  onClick={() => setCreating(false)}
                  className="px-3 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg py-1.5 text-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
