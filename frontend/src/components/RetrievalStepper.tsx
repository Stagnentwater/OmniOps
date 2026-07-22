"use client";

import { motion, AnimatePresence } from "framer-motion";
import { 
  Cpu, Search, Database, GitMerge, FileSearch, 
  BrainCircuit, CheckCircle2, Loader2, ShieldCheck
} from "lucide-react";

const PIPELINE_STAGES = [
  { key: "GENERATING_EMBEDDING", label: "Encoding Query", icon: BrainCircuit, description: "Converting your question into a semantic vector" },
  { key: "SEARCHING_VECTOR_DB", label: "Vector Search", icon: Search, description: "Finding semantically similar chunks in Qdrant" },
  { key: "EXPANDING_KNOWLEDGE_GRAPH", label: "Graph Expansion", icon: Database, description: "Traversing entity relationships in Neo4j" },
  { key: "RETRIEVED_CONTEXT", label: "Context Assembled", icon: GitMerge, description: "Merging vector and graph retrieval results" },
  { key: "BUILDING_PROMPT", label: "Building Prompt", icon: FileSearch, description: "Structuring the reasoning prompt with context" },
  { key: "GENERATING_RESPONSE", label: "Generating Answer", icon: Cpu, description: "LLM reasoning over grounded context" },
  { key: "VALIDATING_CITATIONS", label: "Citation Validation", icon: ShieldCheck, description: "Verifying every claim against source documents" },
];

interface RetrievalStepperProps {
  currentStage: string;
  metadata?: any;
}

export function RetrievalStepper({ currentStage, metadata }: RetrievalStepperProps) {
  const currentIdx = PIPELINE_STAGES.findIndex(s => s.key === currentStage);

  return (
    <div className="flex flex-col gap-0.5 py-2">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
        <span className="text-xs font-semibold uppercase tracking-widest text-indigo-400" style={{ fontFamily: 'var(--font-mono)' }}>
          Retrieval Pipeline
        </span>
      </div>

      {PIPELINE_STAGES.map((stage, idx) => {
        const isCompleted = idx < currentIdx;
        const isCurrent = idx === currentIdx;
        const isPending = idx > currentIdx;
        const Icon = stage.icon;

        return (
          <motion.div
            key={stage.key}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.04, duration: 0.25 }}
            className="flex items-start gap-3 relative"
          >
            {/* Connector line */}
            {idx < PIPELINE_STAGES.length - 1 && (
              <div className="absolute left-[13px] top-[28px] w-[2px] h-[calc(100%-4px)]"
                style={{
                  background: isCompleted ? 'var(--color-accent)' : 'var(--color-border)',
                  opacity: isCompleted ? 0.6 : 0.3,
                }}
              />
            )}

            {/* Icon */}
            <div className={`relative z-10 flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-300 ${
              isCompleted 
                ? 'bg-indigo-500/20 text-indigo-400' 
                : isCurrent 
                  ? 'bg-indigo-500/30 text-indigo-300 ring-1 ring-indigo-500/50' 
                  : 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]'
            }`}>
              {isCompleted ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : isCurrent ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Icon className="w-3.5 h-3.5" />
              )}
            </div>

            {/* Content */}
            <div className={`flex-1 pb-4 min-w-0 ${isPending ? 'opacity-30' : ''}`}>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-semibold ${
                  isCurrent ? 'text-[var(--color-text-primary)]' : isCompleted ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text-muted)]'
                }`}>
                  {stage.label}
                </span>
                {isCurrent && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-400"
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Active
                  </motion.div>
                )}
              </div>

              {/* Show metadata for completed retrieval stage */}
              {isCompleted && stage.key === "RETRIEVED_CONTEXT" && metadata && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="mt-1.5 flex gap-3"
                >
                  {metadata.retrieved_chunks && (
                    <span className="text-[11px] font-medium text-cyan-400" style={{ fontFamily: 'var(--font-mono)' }}>
                      {metadata.retrieved_chunks.length} chunks
                    </span>
                  )}
                  {metadata.retrieved_entities && (
                    <span className="text-[11px] font-medium text-violet-400" style={{ fontFamily: 'var(--font-mono)' }}>
                      {metadata.retrieved_entities.length} entities
                    </span>
                  )}
                  {metadata.retrieved_relationships && (
                    <span className="text-[11px] font-medium text-amber-400" style={{ fontFamily: 'var(--font-mono)' }}>
                      {metadata.retrieved_relationships.length} relationships
                    </span>
                  )}
                </motion.div>
              )}

              {isCurrent && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.1 }}
                  className="text-xs text-[var(--color-text-muted)] mt-0.5"
                >
                  {stage.description}
                </motion.p>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
