"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";

type PdfOperation =
  | "merge"
  | "split"
  | "extract"
  | "delete"
  | "rearrange"
  | "rotate"
  | "compress"
  | "to-images"
  | "protect"
  | "unlock";

interface OperationConfig {
  label: string;
  endpoint: string;
  multiple: boolean;
  outputName: string;
  description: string;
}

const OPERATIONS: Record<PdfOperation, OperationConfig> = {
  merge: {
    label: "Merge PDFs",
    endpoint: "/api/v1/pdf/merge",
    multiple: true,
    outputName: "merged.pdf",
    description: "Combine 2 or more PDFs into one document.",
  },
  split: {
    label: "Split PDF",
    endpoint: "/api/v1/pdf/split",
    multiple: false,
    outputName: "split_pdfs.zip",
    description: "Split page ranges (e.g. 1-2;3-4) into separate PDFs (ZIP).",
  },
  extract: {
    label: "Extract Pages",
    endpoint: "/api/v1/pdf/extract",
    multiple: false,
    outputName: "extracted.pdf",
    description: "Keep only selected pages (e.g. 1,3-4).",
  },
  delete: {
    label: "Delete Pages",
    endpoint: "/api/v1/pdf/delete",
    multiple: false,
    outputName: "updated.pdf",
    description: "Remove unwanted pages (e.g. 2,5).",
  },
  rearrange: {
    label: "Rearrange Pages",
    endpoint: "/api/v1/pdf/rearrange",
    multiple: false,
    outputName: "rearranged.pdf",
    description: "Reorder pages using 1-based numbers (e.g. 3,1,2).",
  },
  rotate: {
    label: "Rotate Pages",
    endpoint: "/api/v1/pdf/rotate",
    multiple: false,
    outputName: "rotated.pdf",
    description: "Rotate all or selected pages by 90, 180, or 270 degrees.",
  },
  compress: {
    label: "Compress PDF",
    endpoint: "/api/v1/pdf/compress",
    multiple: false,
    outputName: "compressed.pdf",
    description: "Reduce PDF file size while preserving pages.",
  },
  "to-images": {
    label: "PDF to Images",
    endpoint: "/api/v1/pdf/to-images",
    multiple: false,
    outputName: "pdf_images.zip",
    description: "Render every PDF page to PNG or JPG images (ZIP).",
  },
  protect: {
    label: "Protect PDF",
    endpoint: "/api/v1/pdf/protect",
    multiple: false,
    outputName: "protected.pdf",
    description: "Encrypt a PDF with an AES-256 password.",
  },
  unlock: {
    label: "Unlock PDF",
    endpoint: "/api/v1/pdf/unlock",
    multiple: false,
    outputName: "unlocked.pdf",
    description: "Remove password protection using your password.",
  },
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function PdfWorkspace() {
  const [operation, setOperation] = useState<PdfOperation>("merge");
  const [files, setFiles] = useState<File[]>([]);
  const [pagesInput, setPagesInput] = useState<string>("1");
  const [rangesInput, setRangesInput] = useState<string>("1-2;3-4");
  const [angle, setAngle] = useState<string>("90");
  const [imageFormat, setImageFormat] = useState<string>("png");
  const [password, setPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");

  const [processing, setProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const config = OPERATIONS[operation];

  const handleOperationChange = (op: PdfOperation) => {
    setOperation(op);
    setFiles([]);
    setError(null);
    setSuccessMsg(null);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files ? Array.from(e.target.files) : [];
    setFiles(selected);
    setError(null);
    setSuccessMsg(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (files.length === 0) {
      setError("Please select at least one PDF file.");
      return;
    }
    if (config.multiple && files.length < 2) {
      setError("Please select at least 2 PDF files to merge.");
      return;
    }

    setProcessing(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      if (config.multiple) {
        files.forEach((f) => formData.append("files", f));
      } else {
        formData.append("file", files[0]);
      }

      if (operation === "split") formData.append("ranges", rangesInput);
      if (operation === "extract" || operation === "delete") formData.append("pages", pagesInput);
      if (operation === "rearrange") formData.append("order", pagesInput);
      if (operation === "rotate") {
        formData.append("angle", angle);
        if (pagesInput.trim()) formData.append("pages", pagesInput);
      }
      if (operation === "to-images") {
        formData.append("image_format", imageFormat);
        formData.append("dpi", "150");
      }
      if (operation === "protect") {
        formData.append("new_password", newPassword);
        if (password) formData.append("current_password", password);
      } else if (operation === "unlock" || (operation !== "merge" && password)) {
        formData.append("password", password);
      }

      const res = await fetch(`${API_URL}${config.endpoint}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail ?? `Processing failed (HTTP ${res.status})`);
      }

      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = config.outputName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);

      setSuccessMsg(`Done! Downloaded ${config.outputName}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF processing failed.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Core PDF Engine</h2>
        <p className="text-xs text-slate-400 mt-0.5">{config.description}</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {(Object.keys(OPERATIONS) as PdfOperation[]).map((opKey) => (
          <button
            key={opKey}
            type="button"
            onClick={() => handleOperationChange(opKey)}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              operation === opKey
                ? "bg-sky-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {OPERATIONS[opKey].label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="file"
          accept=".pdf,application/pdf"
          multiple={config.multiple}
          onChange={handleFileChange}
          disabled={processing}
          className="block w-full text-xs text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-200 hover:file:bg-slate-700"
        />

        {operation === "split" && (
          <label className="block text-xs text-slate-300 space-y-1">
            <span>Split Ranges (semicolon-separated)</span>
            <input
              type="text"
              value={rangesInput}
              onChange={(e) => setRangesInput(e.target.value)}
              placeholder="1-2;3-4"
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
            />
          </label>
        )}

        {(operation === "extract" ||
          operation === "delete" ||
          operation === "rearrange" ||
          operation === "rotate") && (
          <label className="block text-xs text-slate-300 space-y-1">
            <span>
              {operation === "rearrange"
                ? "New Page Order (e.g. 3,1,2)"
                : operation === "rotate"
                ? "Pages to Rotate (optional, blank = all)"
                : "Pages (e.g. 1,3-4)"}
            </span>
            <input
              type="text"
              value={pagesInput}
              onChange={(e) => setPagesInput(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
            />
          </label>
        )}

        {operation === "rotate" && (
          <label className="block text-xs text-slate-300 space-y-1">
            <span>Rotation Angle</span>
            <select
              value={angle}
              onChange={(e) => setAngle(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
            >
              <option value="90">90°</option>
              <option value="180">180°</option>
              <option value="270">270°</option>
            </select>
          </label>
        )}

        {operation === "to-images" && (
          <label className="block text-xs text-slate-300 space-y-1">
            <span>Image Format</span>
            <select
              value={imageFormat}
              onChange={(e) => setImageFormat(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
            >
              <option value="png">PNG</option>
              <option value="jpg">JPG</option>
            </select>
          </label>
        )}

        {operation === "protect" && (
          <label className="block text-xs text-slate-300 space-y-1">
            <span>New Password (min 4 chars)</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={4}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
            />
          </label>
        )}

        {operation !== "merge" && (
          <label className="block text-xs text-slate-300 space-y-1">
            <span>
              {operation === "unlock"
                ? "PDF Password"
                : "Current PDF Password (if encrypted)"}
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required={operation === "unlock"}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
            />
          </label>
        )}

        <button
          type="submit"
          disabled={processing}
          className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white transition-colors"
        >
          {processing ? "Processing..." : `Run ${config.label}`}
        </button>
      </form>

      {successMsg && (
        <p className="rounded-lg border border-emerald-900/60 bg-emerald-950/30 p-2.5 text-xs text-emerald-300">
          {successMsg}
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
