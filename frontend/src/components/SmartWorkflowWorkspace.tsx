"use client";

import { useState, type ChangeEvent } from "react";

interface WorkflowDocItem {
  id: string;
  original_filename: string;
  category: string;
  suggested_filename: string;
  suggested_position: number;
}

interface AnalyzeResponse {
  workflow_id: string;
  ai_used: boolean;
  ai_note: string;
  documents: WorkflowDocItem[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function SmartWorkflowWorkspace() {
  const [files, setFiles] = useState<File[]>([]);
  const [useAi, setUseAi] = useState<boolean>(true);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [docs, setDocs] = useState<WorkflowDocItem[]>([]);
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [outputName, setOutputName] = useState<string>("document_bundle.pdf");

  const [busy, setBusy] = useState<boolean>(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files ? Array.from(e.target.files) : []);
    setWorkflowId(null);
    setDocs([]);
    setAiNote(null);
    setProgress(null);
    setStatusMsg(null);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (files.length < 2) {
      setError("Please select at least 2 files for a Smart Workflow.");
      return;
    }
    setBusy(true);
    setError(null);
    setStatusMsg(null);

    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      formData.append("use_ai", String(useAi));

      const res = await fetch(`${API_URL}/api/v1/workflows/analyze`, {
        method: "POST",
        body: formData,
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail ?? `Analysis failed (HTTP ${res.status})`);
      }
      const data = body as AnalyzeResponse;
      setWorkflowId(data.workflow_id);
      setDocs(data.documents);
      setAiNote(data.ai_note);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workflow analysis failed.");
    } finally {
      setBusy(false);
    }
  };

  const moveDoc = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= docs.length) return;
    const copy = [...docs];
    [copy[index], copy[target]] = [copy[target], copy[index]];
    setDocs(copy);
  };

  const handleBuild = async () => {
    if (!workflowId || docs.length < 2) return;
    setBusy(true);
    setError(null);
    setProgress(0);
    setStatusMsg("Starting background merge...");

    try {
      const buildRes = await fetch(`${API_URL}/api/v1/workflows/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: workflowId,
          ordered_ids: docs.map((d) => d.id),
          output_filename: outputName,
        }),
      });
      const buildBody = await buildRes.json();
      if (!buildRes.ok) {
        throw new Error(buildBody.detail ?? "Could not start workflow job.");
      }

      const jobId: string = buildBody.job_id;
      let done = false;
      while (!done) {
        await new Promise((r) => setTimeout(r, 400));
        const stRes = await fetch(`${API_URL}/api/v1/workflows/jobs/${jobId}`);
        const st = await stRes.json();
        setProgress(st.progress ?? 0);
        if (st.status === "completed") {
          done = true;
          const dlRes = await fetch(`${API_URL}/api/v1/workflows/jobs/${jobId}/download`);
          if (!dlRes.ok) throw new Error("Failed to download completed PDF.");
          const blob = await dlRes.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = st.output_filename ?? outputName;
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
          setStatusMsg("Bundle ready and downloaded!");
        } else if (st.status === "failed") {
          throw new Error(st.error ?? "Background job failed.");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workflow build failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">
          Smart Document Workflows
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Upload mixed files (PDF, DOCX, PNG, JPG, TXT), review optional AI
          categories &amp; order, adjust manually, and merge into one PDF.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.png,.jpg,.jpeg,.txt"
          onChange={handleFileChange}
          disabled={busy}
          className="block flex-1 text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-200 hover:file:bg-slate-700"
        />
        <label className="flex items-center gap-1.5 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={useAi}
            onChange={(e) => setUseAi(e.target.checked)}
          />
          Use AI Suggestions
        </label>
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={busy || files.length < 2}
          className="rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-50 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
        >
          Analyze Files
        </button>
      </div>

      {aiNote && <p className="text-xs text-sky-300">{aiNote}</p>}

      {docs.length > 0 && (
        <div className="space-y-2">
          {docs.map((doc, idx) => (
            <div
              key={doc.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <p className="font-medium text-slate-200 truncate">
                  {idx + 1}. {doc.original_filename}
                </p>
                <p className="text-slate-400 truncate">
                  Category: {doc.category} &middot; Suggested:{" "}
                  {doc.suggested_filename}
                </p>
              </div>
              <div className="flex gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => moveDoc(idx, -1)}
                  disabled={idx === 0 || busy}
                  className="rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 px-2 py-1 text-xs text-slate-200"
                >
                  Up
                </button>
                <button
                  type="button"
                  onClick={() => moveDoc(idx, 1)}
                  disabled={idx === docs.length - 1 || busy}
                  className="rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 px-2 py-1 text-xs text-slate-200"
                >
                  Down
                </button>
              </div>
            </div>
          ))}

          <div className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={outputName}
              onChange={(e) => setOutputName(e.target.value)}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
              placeholder="document_bundle.pdf"
            />
            <button
              type="button"
              onClick={handleBuild}
              disabled={busy}
              className="rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-1.5 text-xs font-semibold text-white transition-colors"
            >
              {busy ? "Building..." : "Build Combined PDF"}
            </button>
          </div>
        </div>
      )}

      {progress !== null && (
        <p className="text-xs text-slate-300">Progress: {progress}%</p>
      )}
      {statusMsg && (
        <p className="rounded-lg border border-emerald-900/60 bg-emerald-950/30 p-2.5 text-xs text-emerald-300">
          {statusMsg}
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-2.5 text-xs text-rose-300">
          {error}
        </p>
      )}
    </section>
  );
}
