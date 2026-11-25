"use client";

import { useCallback, useEffect, useState, type ChangeEvent } from "react";
import { getSupabaseBrowserClient } from "@/lib/supabase";

interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

interface UploadValidationResponse {
  valid: boolean;
  safe_filename: string;
  display_filename: string;
  extension: string;
  mime_type: string;
  size_bytes: number;
  user_mode: string;
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
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadResult, setUploadResult] = useState<UploadValidationResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const supabaseConfigured = Boolean(getSupabaseBrowserClient());

  const handleRecheck = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await fetchBackendHealth();
      setHealth(data);
    } catch (err) {
      setHealth(null);
      setHealthError(
        err instanceof Error
          ? err.message
          : "Unable to reach the FastAPI backend."
      );
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchBackendHealth()
      .then((data) => {
        if (!cancelled) {
          setHealth(data);
          setHealthError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setHealth(null);
          setHealthError(
            err instanceof Error
              ? err.message
              : "Unable to reach the FastAPI backend."
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHealthLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;

    setUploading(true);
    setUploadResult(null);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch(`${API_URL}/api/v1/uploads/validate`, {
        method: "POST",
        body: formData,
      });

      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail ?? `Upload rejected (HTTP ${res.status})`);
      }

      setUploadResult(body as UploadValidationResponse);
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : "Upload validation failed."
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div className="max-w-xl w-full space-y-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-sky-400">
              Phase 2: Auth &amp; Upload Security
            </p>
            <h1 className="text-3xl font-bold tracking-tight mt-1">
              DocumentHub
            </h1>
          </div>
          <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-300">
            {supabaseConfigured ? "Auth Ready" : "Guest Mode"}
          </span>
        </div>

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

          {healthLoading && (
            <p className="text-sm text-slate-400">
              Checking {API_URL}/health...
            </p>
          )}

          {!healthLoading && health && (
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

          {!healthLoading && healthError && (
            <div className="space-y-1 text-sm">
              <p className="text-amber-400 font-medium">Backend Offline</p>
              <p className="text-slate-400">{healthError}</p>
            </div>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-200">
            Secure File Upload Validator
          </h2>
          <p className="text-xs text-slate-400">
            Tests server-side extension, MIME, size, and magic-byte validation
            (.pdf, .docx, .png, .jpg, .txt).
          </p>
          <input
            type="file"
            accept=".pdf,.docx,.png,.jpg,.jpeg,.txt"
            onChange={handleFileUpload}
            disabled={uploading}
            className="block w-full text-xs text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-200 hover:file:bg-slate-700"
          />

          {uploading && (
            <p className="text-xs text-sky-400">Validating file signature...</p>
          )}

          {uploadResult && (
            <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/30 p-3 text-xs space-y-1">
              <p className="font-semibold text-emerald-400">
                Upload Validated ({uploadResult.user_mode})
              </p>
              <p className="text-slate-300">
                Original: {uploadResult.display_filename} &rarr; Safe ID:{" "}
                <code>{uploadResult.safe_filename}</code>
              </p>
              <p className="text-slate-400">
                {uploadResult.mime_type} &middot; {uploadResult.size_bytes} bytes
              </p>
            </div>
          )}

          {uploadError && (
            <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-3 text-xs text-rose-300">
              Rejected: {uploadError}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
