"use client";

import { useCallback, useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchBackendHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) {
    throw new Error(`Backend responded with status ${res.status}`);
  }
  return (await res.json()) as HealthResponse;
}

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const handleRecheck = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBackendHealth();
      setHealth(data);
    } catch (err) {
      setHealth(null);
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reach the FastAPI backend."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchBackendHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setHealth(null);
          setError(
            err instanceof Error
              ? err.message
              : "Unable to reach the FastAPI backend."
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div className="max-w-xl w-full rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <div className="flex items-center justify-between gap-4 mb-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-sky-400">
              Phase 1 Foundation
            </p>
            <h1 className="text-3xl font-bold tracking-tight mt-1">
              DocumentHub
            </h1>
          </div>
          <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-300">
            Free &amp; Privacy-First
          </span>
        </div>

        <p className="text-slate-300 text-sm leading-relaxed mb-6">
          Intelligent, browser-based document processing platform combining
          traditional PDF/Word tools, OCR, and an optional independent AI
          assistant.
        </p>

        <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-200">
              Backend API Connection
            </h2>
            <button
              type="button"
              onClick={handleRecheck}
              className="rounded-lg bg-sky-600 hover:bg-sky-500 px-3 py-1.5 text-xs font-medium text-white transition-colors"
            >
              Re-check
            </button>
          </div>

          {loading && (
            <p className="text-sm text-slate-400">
              Checking {API_URL}/health...
            </p>
          )}

          {!loading && health && (
            <div className="space-y-1 text-sm">
              <p className="text-emerald-400 font-medium">
                Connected ({health.status.toUpperCase()})
              </p>
              <p className="text-slate-400">
                Service: <span className="text-slate-200">{health.service}</span>{" "}
                &middot; v{health.version} ({health.environment})
              </p>
            </div>
          )}

          {!loading && error && (
            <div className="space-y-1 text-sm">
              <p className="text-amber-400 font-medium">Backend Offline</p>
              <p className="text-slate-400">{error}</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
