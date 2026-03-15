"use client";

import { useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useBrainSocket } from "@/hooks/useBrainSocket";
import ExperimentFlow from "@/components/ExperimentFlow";
import type { WSMessage } from "@/lib/types";

export default function ExperimentPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.userId as string;

  // ExperimentFlow registers its handler here; WS messages are forwarded to it
  const experimentHandlerRef = useRef<((msg: WSMessage) => void) | null>(null);

  const handleMessage = useCallback((msg: WSMessage) => {
    experimentHandlerRef.current?.(msg);
  }, []);

  const registerHandler = useCallback((handler: (msg: WSMessage) => void) => {
    experimentHandlerRef.current = handler;
  }, []);

  const { brainData } = useBrainSocket({ userId, onMessage: handleMessage });

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
        <h1 className="text-sm font-medium text-white">Brain Learning Experiment</h1>
        <div />
      </header>
      <div className="flex-1">
        <ExperimentFlow
          userId={userId}
          brainData={brainData}
          onRegisterHandler={registerHandler}
          onComplete={() => router.push(`/dashboard/${userId}`)}
        />
      </div>
    </div>
  );
}
