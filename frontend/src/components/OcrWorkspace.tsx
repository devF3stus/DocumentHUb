"use client";

import { useState, type ChangeEvent } from "react";

interface OcrPage {
  page_number: number;
  text: string;
  confidence: number;
}

interface OcrExtractResponse {
  language: string;
  average_confidence: number;
  full_text: string;
  pages: OcrPage[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function OcrWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [language, setLanguage] = useState<string>("eng");
  const [preprocess, setPreprocess] = useState<boolean>(true);

  const [running, setRunning] = useState<boolean>(false);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [editableText, setEditableText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(selected);
    setError(null);
    setConfidence(null);
    setEditableText("");

    if (selected && selected.type.startsWith("image/")) {
      setPreviewUrl(URL.createObjectURL(selected));
    } else {
      setPreviewUrl(null);
    }
  };

  const handleRunOcr = async () => {
    if (!file) {
      setError("Please select an image or scanned PDF.");
      return;
    }
    setRunning(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("language", language);
      formData.append("preprocess", String(preprocess));

      const res = await fetch(`${API_URL}/api/v1/ocr/extract`, {
        method: "POST",
        body: formData,
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail ?? `OCR failed (HTTP ${res.status})`);
      }

      const data = body as OcrExtractResponse;
      setEditableText(data.full_text);
      setConfidence(data.average_confidence);
    } catch (err) {
      setError(err instanceof Error ? err.message : "OCR extraction failed.");
    } finally {
      setRunning(false);
    }
  };

  const handleExport = async (format: "txt" | "docx") => {
    if (!editableText.trim()) return;
    setError(null);
    try {
      const formData = new FormData();
      formData.append("text", editableText);
      formData.append("export_format", format);

      const res = await fetch(`${API_URL}/api/v1/ocr/export`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail ?? "Export failed");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "txt" ? "ocr_result.txt" : "ocr_result.docx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  };

  const handleSearchablePdf = async () => {
    if (!file) return;
    setRunning(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("language", language);
      formData.append("preprocess", String(preprocess));

      const res = await fetch(`${API_URL}/api/v1/ocr/searchable-pdf`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail ?? "Searchable PDF generation failed");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "searchable.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Searchable PDF failed.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">OCR Studio</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Extract &amp; review printed text from PNG, JPG, TIFF, or scanned PDFs.
          </p>
        </div>
        {confidence !== null && (
          <span className="rounded-full bg-emerald-950 border border-emerald-800 px-2.5 py-1 text-xs text-emerald-300">
            Confidence: {confidence}%
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.tiff,.tif,.pdf"
          onChange={handleFileChange}
          disabled={running}
          className="block w-full text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-200 hover:file:bg-slate-700"
        />

        <div className="flex items-center gap-3">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="eng">English (eng)</option>
            <option value="fra">French (fra)</option>
            <option value="deu">German (deu)</option>
            <option value="spa">Spanish (spa)</option>
          </select>

          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={preprocess}
              onChange={(e) => setPreprocess(e.target.checked)}
            />
            Preprocess
          </label>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleRunOcr}
          disabled={running || !file}
          className="rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
        >
          {running ? "Running OCR..." : "Extract Text"}
        </button>

        <button
          type="button"
          onClick={handleSearchablePdf}
          disabled={running || !file}
          className="rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors"
        >
          Searchable PDF
        </button>
      </div>

      {(previewUrl || editableText) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 flex items-center justify-center min-h-[140px]">
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={previewUrl}
                alt="Uploaded scan preview"
                className="max-h-56 object-contain rounded"
              />
            ) : (
              <p className="text-xs text-slate-400">
                {file ? `Selected: ${file.name}` : "No image preview"}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <textarea
              rows={7}
              value={editableText}
              onChange={(e) => setEditableText(e.target.value)}
              placeholder="Extracted text appears here for review and correction..."
              className="w-full rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-xs text-slate-100"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleExport("txt")}
                disabled={!editableText.trim()}
                className="rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 px-3 py-1 text-xs text-slate-200"
              >
                Download TXT
              </button>
              <button
                type="button"
                onClick={() => handleExport("docx")}
                disabled={!editableText.trim()}
                className="rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 px-3 py-1 text-xs text-slate-200"
              >
                Download DOCX
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-2.5 text-xs text-rose-300">
          {error}
        </p>
      )}
    </section>
  );
}
