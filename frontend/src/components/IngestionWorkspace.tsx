"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, File, Trash2, CheckCircle2, Circle, Loader2, Database, Network, GitMerge } from "lucide-react";
import { ApiClient } from "@/services/api";

const STAGES = [
  "JOB_CREATED", "PARSED", "METADATA_EXTRACTED", "NORMALIZED",
  "CHUNKED", "ENTITY_EXTRACTED", "RELATIONSHIP_EXTRACTED",
  "KNOWLEDGE_RESOLVED", "GRAPH_PERSISTED", "VECTOR_PERSISTED", "COMPLETED"
];

const STAGE_LABELS: Record<string, string> = {
  "JOB_CREATED": "Uploading Document",
  "PARSED": "Parsing Contents",
  "METADATA_EXTRACTED": "Extracting Metadata",
  "NORMALIZED": "Normalizing Data",
  "CHUNKED": "Chunking Text",
  "ENTITY_EXTRACTED": "Extracting Entities",
  "RELATIONSHIP_EXTRACTED": "Discovering Relationships",
  "KNOWLEDGE_RESOLVED": "Resolving Knowledge Graph",
  "GRAPH_PERSISTED": "Persisting to Neo4j",
  "VECTOR_PERSISTED": "Persisting to Qdrant",
  "COMPLETED": "Knowledge Base Updated"
};

const STAGE_DESCRIPTIONS: Record<string, string> = {
  "ENTITY_EXTRACTED": "Identifying assets, components, and locations...",
  "RELATIONSHIP_EXTRACTED": "Mapping connections between entities...",
  "KNOWLEDGE_RESOLVED": "Merging duplicate entities into canonical nodes...",
  "GRAPH_PERSISTED": "Writing nodes and edges to Neo4j...",
  "VECTOR_PERSISTED": "Creating vector embeddings in Qdrant...",
};

interface IngestionWorkspaceProps {
  documents: any[];
  onDocumentAdded: () => void;
  onDocumentDeleted: () => void;
}

export function IngestionWorkspace({ documents, onDocumentAdded, onDocumentDeleted }: IngestionWorkspaceProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [activeUploadId, setActiveUploadId] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<string>("JOB_CREATED");
  const [failed, setFailed] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setFailed(false);
    setCurrentStage("JOB_CREATED");
    
    try {
      const res = await ApiClient.uploadDocument(file);
      const docId = res.document_id;
      setActiveUploadId(docId);
      onDocumentAdded(); // refresh list
    } catch (err) {
      alert("Upload failed. See console.");
      console.error(err);
      setIsUploading(false);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document and all its graph knowledge?")) return;
    try {
      await ApiClient.deleteDocument(id);
      onDocumentDeleted();
    } catch (err) {
      alert("Delete failed.");
    }
  };

  // SSE tracking for active upload
  useEffect(() => {
    if (!activeUploadId) return;
    
    const url = ApiClient.getDocumentStreamUrl(activeUploadId);
    const eventSource = new EventSource(url);

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.stage) {
          setCurrentStage(data.stage);
          if (data.stage === "COMPLETED") {
            eventSource.close();
            setTimeout(() => {
              setActiveUploadId(null);
              setIsUploading(false);
              onDocumentAdded();
            }, 2000);
          }
          if (data.stage === "FAILED") {
            setFailed(true);
            eventSource.close();
            setTimeout(() => {
              setActiveUploadId(null);
              setIsUploading(false);
            }, 3000);
          }
        }
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setFailed(true);
      setTimeout(() => {
        setActiveUploadId(null);
        setIsUploading(false);
      }, 3000);
    };

    return () => eventSource.close();
  }, [activeUploadId, onDocumentAdded]);


  if (activeUploadId) {
    const currentIndex = STAGES.indexOf(currentStage);
    
    return (
      <div className="flex flex-col bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4 pb-4 border-b border-[var(--color-border)]">
          <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-widest text-amber-400" style={{ fontFamily: 'var(--font-mono)' }}>
            Ingestion Pipeline Active
          </span>
        </div>

        {failed ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-6">
            <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-3">
              <span className="text-red-400 text-lg">✕</span>
            </div>
            <p className="text-sm font-medium text-red-400">Ingestion Failed</p>
          </motion.div>
        ) : (
          <div className="flex flex-col gap-1 py-2">
            {STAGES.map((stage, idx) => {
              const isCompleted = idx < currentIndex;
              const isCurrent = idx === currentIndex;
              const isPending = idx > currentIndex;

              return (
                <motion.div
                  key={stage}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.03, duration: 0.2 }}
                  className="flex items-start gap-3 relative"
                >
                  {idx < STAGES.length - 1 && (
                    <div className="absolute left-[11px] top-[22px] w-[2px] h-[calc(100%-2px)]"
                      style={{
                        background: isCompleted ? '#f59e0b' : 'var(--color-border)',
                        opacity: isCompleted ? 0.4 : 0.2,
                      }}
                    />
                  )}
                  <div className={`relative z-10 flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center transition-all duration-300 mt-0.5 ${
                    isCompleted
                      ? 'bg-amber-500/15 text-amber-400'
                      : isCurrent
                        ? 'bg-amber-500/25 text-amber-300 ring-1 ring-amber-500/40'
                        : 'bg-[var(--color-surface)] text-[var(--color-text-muted)]'
                  }`}>
                    {isCompleted ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : isCurrent ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Circle className="w-2.5 h-2.5" />
                    )}
                  </div>
                  <div className={`flex-1 pb-3 min-w-0 ${isPending ? 'opacity-30' : ''}`}>
                    <span className={`text-xs font-medium ${
                      isCurrent ? 'text-[var(--color-text-primary)]' : isCompleted ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text-muted)]'
                    }`}>
                      {STAGE_LABELS[stage] || stage}
                    </span>
                    {isCurrent && STAGE_DESCRIPTIONS[stage] && (
                      <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.1 }}
                        className="text-[10px] text-[var(--color-text-muted)] mt-0.5 leading-tight"
                      >
                        {STAGE_DESCRIPTIONS[stage]}
                      </motion.p>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Upload Zone */}
      <div 
        className="w-full border-2 border-dashed border-[var(--color-border)] rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all group"
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="w-10 h-10 rounded-full bg-[var(--color-surface-elevated)] border border-[var(--color-border)] flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
          <UploadCloud className="w-5 h-5 text-indigo-400" />
        </div>
        <p className="text-sm font-medium text-[var(--color-text-primary)]">Upload Knowledge Document</p>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">PDF, DOCX, CSV, XLSX supported</p>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleUpload} 
          className="hidden" 
          accept=".pdf,.docx,.csv,.xlsx,.xls"
          disabled={isUploading} 
        />
      </div>

      {/* Document List */}
      <div className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-1">Indexed Assets</h3>
        {documents.length === 0 ? (
          <div className="text-xs text-[var(--color-text-muted)] py-4 text-center bg-[var(--color-surface-elevated)] rounded-lg border border-[var(--color-border)] border-dashed">
            No documents indexed yet.
          </div>
        ) : (
          documents.map(doc => (
            <div key={doc.id} className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] group">
              <div className="flex items-center gap-3 overflow-hidden">
                <File className="w-4 h-4 text-emerald-400 shrink-0" />
                <div className="flex flex-col overflow-hidden">
                  <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">{doc.filename}</span>
                  <span className="text-[10px] text-[var(--color-text-muted)] font-mono truncate">{doc.id.substring(0, 12)}...</span>
                </div>
              </div>
              <button 
                onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                className="opacity-0 group-hover:opacity-100 p-1.5 text-red-400/70 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-all"
                title="Delete document"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
