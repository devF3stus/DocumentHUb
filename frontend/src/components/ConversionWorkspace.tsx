"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";

type ConversionOp =
  | "docx-to-pdf"
  | "pdf-to-docx"
  | "docx-to-txt"
  | "docx-to-html"
  | "txt-to-docx"
  | "txt-to-pdf"
  | "images-to-pdf"
  | "merge-docx"
  | "generate-docx";

interface OpMeta {
  label: string;
  endpoint: string;
  accept: string;
  multiple: boolean;
  needsFile: boolean;
  outputName: string;
  description: string;
}

const OPS: Record<ConversionOp, OpMeta> = {
  "docx-to-pdf": {
    label: "DOCX -> PDF",
    endpoint: "/api/v1/convert/docx-to-pdf",
    accept: ".docx",
    multiple: false,
    needsFile: true,
    outputName: "converted.pdf",
    description: "Convert Word (.docx) to PDF via LibreOffice.",
  },
  "pdf-to-docx": {
    label: "PDF -> DOCX",
    endpoint: "/api/v1/convert/pdf-to-docx",
    accept: ".pdf",
    multiple: false,
    needsFile: true,
    outputName: "converted.docx",
    description: "Reconstruct digital PDFs into editable Word documents.",
  },
  "docx-to-txt": {
    label: "DOCX -> TXT",
    endpoint: "/api/v1/convert/docx-to-txt",
    accept: ".docx",
    multiple: false,
    needsFile: true,
    outputName: "extracted.txt",
    description: "Extract paragraphs and tables from Word into plain text.",
  },
  "docx-to-html": {
    label: "DOCX -> HTML",
    endpoint: "/api/v1/convert/docx-to-html",
    accept: ".docx",
    multiple: false,
    needsFile: true,
    outputName: "converted.html",
    description: "Convert Word documents into clean semantic HTML.",
  },
  "txt-to-docx": {
    label: "TXT -> DOCX",
    endpoint: "/api/v1/convert/txt-to-docx",
    accept: ".txt",
    multiple: false,
    needsFile: true,
    outputName: "converted.docx",
    description: "Wrap plain text into a formatted Word document.",
  },
  "txt-to-pdf": {
    label: "TXT -> PDF",
    endpoint: "/api/v1/convert/txt-to-pdf",
    accept: ".txt",
    multiple: false,
    needsFile: true,
    outputName: "converted.pdf",
    description: "Render plain text into a clean A4 PDF.",
  },
  "images-to-pdf": {
    label: "Images -> PDF",
    endpoint: "/api/v1/convert/images-to-pdf",
    accept: ".png,.jpg,.jpeg",
    multiple: true,
    needsFile: true,
    outputName: "images.pdf",
    description: "Combine one or more PNG/JPG images into a single PDF.",
  },
  "merge-docx": {
    label: "Merge DOCX",
    endpoint: "/api/v1/word/merge",
    accept: ".docx",
    multiple: true,
    needsFile: true,
    outputName: "merged.docx",
    description: "Merge 2 or more Word documents while preserving formatting.",
  },
  "generate-docx": {
    label: "Generate DOCX",
    endpoint: "/api/v1/word/generate",
    accept: "",
    multiple: false,
    needsFile: false,
    outputName: "generated.docx",
    description: "Create a new Word document from a title and text.",
  },
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ConversionWorkspace() {
  const [op, setOp] = useState<ConversionOp>("pdf-to-docx");
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [processing, setProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const meta = OPS[op];

  const handleOpChange = (nextOp: ConversionOp) => {
    setOp(nextOp);
    setFiles([]);
    setError(null);
    setSuccessMsg(null);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files ? Array.from(e.target.files) : []);
    setError(null);
    setSuccessMsg(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (meta.needsFile && files.length === 0) {
      setError("Please select the required file(s).");
      return;
    }
    if (op === "merge-docx" && files.length < 2) {
      setError("Please select at least 2 DOCX files to merge.");
      return;
    }
    if (!meta.needsFile && !text.trim()) {
      setError("Please enter document text.");
      return;
    }

    setProcessing(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      if (meta.needsFile) {
        if (meta.multiple) {
          files.forEach((f) => formData.append("files", f));
        } else {
          formData.append("file", files[0]);
        }
      }
      if (op === "txt-to-docx" && title.trim()) {
        formData.append("title", title.trim());
      }
      if (op === "generate-docx") {
        formData.append("text", text);
        if (title.trim()) formData.append("title", title.trim());
      }

      const res = await fetch(`${API_URL}${meta.endpoint}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail ?? `Conversion failed (HTTP ${res.status})`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = meta.outputName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setSuccessMsg(`Done! Downloaded ${meta.outputName}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Conversion failed.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">
          Document Conversion &amp; Word Studio
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">{meta.description}</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {(Object.keys(OPS) as ConversionOp[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => handleOpChange(key)}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              op === key
                ? "bg-violet-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {OPS[key].label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {meta.needsFile && (
          <input
            type="file"
            accept={meta.accept}
            multiple={meta.multiple}
            onChange={handleFileChange}
            disabled={processing}
            className="block w-full text-xs text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-medium file:text-slate-200 hover:file:bg-slate-700"
          />
        )}

        {(op === "txt-to-docx" || op === "generate-docx") && (
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Optional document title"
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100"
          />
        )}

        {op === "generate-docx" && (
          <textarea
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Enter document text..."
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-100"
          />
        )}

        <button
          type="submit"
          disabled={processing}
          className="w-full rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white transition-colors"
        >
          {processing ? "Converting..." : `Run ${meta.label}`}
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
