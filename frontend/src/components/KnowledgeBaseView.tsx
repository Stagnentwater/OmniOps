"use client";

import { RetrievalGraph, GraphData } from "@/components/RetrievalGraph";
import { Globe, Search } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface KnowledgeBaseViewProps {
  fullGraphData: GraphData | null;
  metadata: any | null;
  graphViewMode: "global" | "retrieval";
  hoveredCitationId: string | null;
  onGraphViewModeChange: (mode: "global" | "retrieval") => void;
  onRefreshGraph: () => void;
}

export function KnowledgeBaseView({
  fullGraphData,
  metadata,
  graphViewMode,
  hoveredCitationId,
  onGraphViewModeChange,
  onRefreshGraph,
}: KnowledgeBaseViewProps) {
  return (
    <div className="flex-1 h-full flex flex-col bg-[var(--color-surface)] overflow-hidden">
      {/* View Header */}
      <div className="h-14 border-b border-[var(--color-border)] flex items-center px-6 gap-3 shrink-0 bg-[var(--color-surface-elevated)]/50">
        <span className="font-bold text-sm tracking-wide text-[var(--color-text-primary)]">
          KNOWLEDGE BASE
        </span>

        {/* Graph mode toggle — integrated into the header */}
        <div className="flex items-center p-1 bg-[var(--color-surface)]/80 border border-[var(--color-border)] rounded-lg ml-4">
          <button
            onClick={() => onGraphViewModeChange("global")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              graphViewMode === "global"
                ? "bg-[var(--color-surface-elevated)] text-[var(--color-text-primary)] shadow-sm border border-[var(--color-border)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            Global
          </button>
          <button
            onClick={() => onGraphViewModeChange("retrieval")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              graphViewMode === "retrieval"
                ? "bg-[var(--color-surface-elevated)] text-indigo-400 shadow-sm border border-[var(--color-border)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Retrieval
          </button>
        </div>

        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text-muted)] ml-auto"
        >
          KNOWLEDGE GRAPH
        </span>
      </div>

      {/* Full-width graph */}
      <div className="flex-1 relative overflow-hidden">
        <RetrievalGraph
          fullGraphData={fullGraphData}
          metadata={metadata}
          mode={graphViewMode}
          hoveredCitationId={hoveredCitationId}
          onRefresh={onRefreshGraph}
        />
      </div>
    </div>
  );
}
