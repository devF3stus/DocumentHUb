"use client";

import { useEffect, useState } from "react";

type AiAction = "summarize" | "classify" | "extract" | "suggest-filename" | "compare";

interface AiStatus {
  provider: string;
  configured: boolean;
  model: string;
  privacy_disclosure: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AiAssistantWorkspace() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [action, setAction] = useState<AiAction>("summarize");
  const [textA, setTextA] = useState<string>("");
  const [textB, setTextB] = useState<string>("");
  const [running, setRunning] = useState<boolean>(false);
  const [resultJson, setResultJson] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/ai/status`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setStatus(data as AiStatus);
      })
      .catch(() => {});
  }, []);

  const handleRun = async () => {
    if (!textA.trim()) {
      setError("Please enter document text to analyze.");
      return;
    }
    if (action === "compare" && !textB.trim()) {
      setError("Please enter Document B text to compare.");
      return;
    }

    setRunning(true);
    setError(null);
    setResultJson(null);

    try {
      const payload =
        action === "compare"
          ? { text_a: textA, text_b: textB }
          : { text: textA };

      const res = await fetch(`${API_URL}/api/v1/ai/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail ?? `AI request failed (HTTP ${res.status})`);
      }

      setResultJson(JSON.stringify(body, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI request failed.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">
            AI Document Assistant (Optional)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Suggestions only—never required for PDF, Word, or OCR tools.
          </p>
        </div>
        {status && (
          <span className="rounded-full border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
            {status.provider} ({status.configured ? "ready" : "no key"})
          </span>
        )}
      </div>

      {status?.privacy_disclosure && (
        <p className="rounded-lg border border-sky-900/50 bg-sky-950/20 p-2.5 text-xs text-sky-300">
          {status.privacy_disclosure}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {(
          [
            ["summarize", "Summarize"],
            ["classify", "Classify"],
            ["extract", "Extract Info"],
            ["suggest-filename", "Suggest Filename"],
            ["compare", "Compare 2 Docs"],
          ] as [AiAction, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setAction(key)}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              action === key
                ? "bg-indigo-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <textarea
          rows={4}
          value={textA}
          onChange={(e) => setTextA(e.target.value)}
          placeholder="Paste extracted document text here..."
          className="w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-xs text-slate-100"
        />

        {action === "compare" && (
          <textarea
            rows={4}
            value={textB}
            onChange={(e) => setTextB(e.target.value)}
            placeholder="Paste Document B text to compare..."
            className="w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-xs text-slate-100"
          />
        )}

        <button
          type="button"
          onClick={handleRun}
          disabled={running}
          className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white transition-colors"
        >
          {running ? "Analyzing..." : "Get AI Suggestion"}
        </button>
      </div>

      {resultJson && (
        <pre className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-3 text-xs text-emerald-300 overflow-x-auto">
          {resultJson}
        </pre>
      )}

      {error && (
        <p className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-2.5 text-xs text-rose-300">
          {error}
        </p>
      )}
    </section>
  );
}
