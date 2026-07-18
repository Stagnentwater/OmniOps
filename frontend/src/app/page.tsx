"use client";

import { useEffect, useState, useRef } from "react";
import { ApiClient } from "@/services/api";

type DocumentStatus = {
  document_id: string;
  status: string;
  progress_percent: number;
  error_message?: string;
};

type DocumentItem = {
  id: string;
  filename: string;
  status: string;
  upload_time: string;
};

function StatusBadge({ docId, initialStatus }: { docId: string; initialStatus: string }) {
  const [status, setStatus] = useState(initialStatus);

  useEffect(() => {
    if (status === "COMPLETED" || status === "FAILED") return;
    
    const interval = setInterval(async () => {
      try {
        const res = await ApiClient.getDocumentStatus(docId);
        setStatus(res.status);
      } catch (err) {
        console.error("Status poll failed", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [docId, status]);

  const colors = {
    COMPLETED: "bg-green-100 text-green-800",
    FAILED: "bg-red-100 text-red-800",
    JOB_CREATED: "bg-yellow-100 text-yellow-800",
    DEFAULT: "bg-blue-100 text-blue-800"
  };

  const colorClass = colors[status as keyof typeof colors] || colors.DEFAULT;

  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

export default function DashboardPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = async () => {
    try {
      const res = await ApiClient.getDocuments();
      setDocuments(res.documents || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      await ApiClient.uploadDocument(file);
      await fetchDocs();
    } catch (err) {
      alert("Upload failed. See console.");
      console.error(err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure?")) return;
    try {
      await ApiClient.deleteDocument(id);
      setDocuments(docs => docs.filter(d => d.id !== id));
    } catch (err) {
      alert("Delete failed.");
    }
  };

  return (
    <div className="space-y-8">
      <section className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Upload Document</h2>
        <div className="flex items-center gap-4">
          <input 
            type="file" 
            accept=".pdf" 
            ref={fileInputRef}
            onChange={handleUpload}
            className="block w-full text-sm text-slate-500
              file:mr-4 file:py-2.5 file:px-4
              file:rounded-lg file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100 transition-colors
              cursor-pointer"
            disabled={isUploading}
          />
          {isUploading && <span className="text-sm text-slate-500 animate-pulse">Uploading...</span>}
        </div>
      </section>

      <section className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">Knowledge Base</h2>
        </div>
        <div className="divide-y divide-slate-100">
          {documents.length === 0 ? (
            <div className="p-8 text-center text-slate-500">No documents ingested yet.</div>
          ) : (
            documents.map(doc => (
              <div key={doc.id} className="p-6 flex items-center justify-between hover:bg-slate-50 transition-colors">
                <div className="flex flex-col gap-1">
                  <span className="font-medium text-slate-700">{doc.filename}</span>
                  <span className="text-xs text-slate-400 font-mono">{doc.id}</span>
                </div>
                <div className="flex items-center gap-4">
                  <StatusBadge docId={doc.id} initialStatus={doc.status} />
                  <button 
                    onClick={() => handleDelete(doc.id)}
                    className="text-red-500 hover:text-red-700 text-sm font-medium transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
