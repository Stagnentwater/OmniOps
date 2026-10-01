"use client";

import { AssetList, UploadZone } from "@/components/IngestionWorkspace";

interface IngestionViewProps {
  documents: any[];
  onDocumentAdded: () => void;
  onDocumentDeleted: () => void;
}

export function IngestionView({ documents, onDocumentAdded, onDocumentDeleted }: IngestionViewProps) {
  return (
    <div className="flex-1 h-full flex flex-col bg-[var(--color-surface)] overflow-hidden">
      {/* View Header */}
      <div className="h-14 border-b border-[var(--color-border)] flex items-center px-6 gap-3 shrink-0 bg-[var(--color-surface-elevated)]/50">
        <span className="font-bold text-sm tracking-wide text-[var(--color-text-primary)]">
          KNOWLEDGE INGESTION
        </span>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text-muted)] ml-auto"
        >
          {documents.length} INDEXED
        </span>
      </div>

      {/* Two-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Asset List */}
        <div className="w-[320px] shrink-0 border-r border-[var(--color-border)] p-5 overflow-y-auto">
          <AssetList documents={documents} onDeleteDocument={() => onDocumentDeleted()} />
        </div>

        {/* Right: Upload Zone */}
        <div className="flex-1 p-5 flex flex-col">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">Upload Documents</h2>
            <p className="text-xs text-[var(--color-text-muted)]">Upload technical documents to synthesize the industrial knowledge graph.</p>
          </div>
          <div className="flex-1">
            <UploadZone onDocumentAdded={onDocumentAdded} />
          </div>
        </div>
      </div>
    </div>
  );
}
