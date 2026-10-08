"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Database,
  Cpu,
  Calculator,
  Eye,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  Check,
  Terminal,
  Layers,
  Sparkles,
} from "lucide-react";

export interface AgentActivityItem {
  id?: string;
  type: string;
  status: "running" | "completed" | "failed";
  message: string;
  tool?: string;
  metadata?: Record<string, any>;
  timestamp?: number;
}

interface AgentActivityStreamProps {
  activities: AgentActivityItem[];
  isLive?: boolean;
}

/**
 * Helper to pick an appropriate icon based on activity type or tool.
 */
function getActivityIcon(activity: AgentActivityItem) {
  const tool = activity.tool?.toLowerCase() || "";
  const type = activity.type?.toLowerCase() || "";

  if (tool === "calculate" || type.includes("code") || type.includes("calculate")) {
    return Calculator;
  }
  if (tool === "search_documents" || type.includes("vector") || type.includes("document")) {
    return Search;
  }
  if (tool === "search_knowledge_graph" || type.includes("graph")) {
    return Database;
  }
  if (tool === "analyze_image" || tool === "analyze_pid" || type.includes("vision") || type.includes("image")) {
    return Eye;
  }
  if (type.includes("reasoning") || type.includes("synthesiz")) {
    return BrainIcon;
  }
  return Cpu;
}

function BrainIcon(props: React.SVGProps<SVGSVGElement>) {
  return <Sparkles {...props} />;
}

export function AgentActivityStream({ activities, isLive = false }: AgentActivityStreamProps) {
  const [copiedCodeId, setCopiedCodeId] = useState<string | null>(null);
  const [expandedCodeIds, setExpandedCodeIds] = useState<Record<string, boolean>>({});
  const [isCollapsedInHistory, setIsCollapsedInHistory] = useState<boolean>(!isLive);

  if (!activities || activities.length === 0) {
    if (!isLive) return null;
    return (
      <div className="flex items-center gap-2 py-3 px-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-xs text-[var(--color-text-secondary)]">
        <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
        <span>Initializing agent runtime...</span>
      </div>
    );
  }

  const toggleCode = (id: string) => {
    setExpandedCodeIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopyCode = (code: string, id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(code);
    setCopiedCodeId(id);
    setTimeout(() => setCopiedCodeId(null), 2000);
  };

  return (
    <div className="flex flex-col gap-2 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] p-3.5 shadow-sm text-xs">
      {/* Header bar */}
      <div
        className={`flex items-center justify-between cursor-pointer select-none ${
          !isLive ? "pb-1" : "pb-2 border-b border-[var(--color-border)]"
        }`}
        onClick={() => !isLive && setIsCollapsedInHistory(!isCollapsedInHistory)}
      >
        <div className="flex items-center gap-2">
          {isLive ? (
            <div className="relative flex items-center justify-center w-2.5 h-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
            </div>
          ) : (
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
          )}
          <span
            className="font-semibold uppercase tracking-wider text-[var(--color-text-primary)]"
            style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}
          >
            {isLive ? "Agent Execution Stream" : `Agent Activity (${activities.length} steps)`}
          </span>
        </div>

        {!isLive && (
          <button
            type="button"
            className="flex items-center gap-1 text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors text-[11px]"
          >
            {isCollapsedInHistory ? "Show details" : "Hide details"}
            {isCollapsedInHistory ? (
              <ChevronRight className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        )}
      </div>

      {/* Activity steps list */}
      <AnimatePresence initial={false}>
        {(isLive || !isCollapsedInHistory) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-2 pt-1"
          >
            {activities.map((activity, idx) => {
              const isRunning = activity.status === "running";
              const isFailed = activity.status === "failed";
              const isCompleted = activity.status === "completed";
              const Icon = getActivityIcon(activity);
              const activityId = activity.id || `activity-${idx}`;

              // Extract any executable code artifact (from calculate or code_generated)
              const code =
                activity.metadata?.code ||
                (activity.type === "code_generated" ? activity.metadata?.code : null);
              const calcResult = activity.metadata?.result;
              const hasCode = typeof code === "string" && code.trim().length > 0;
              const isCodeExpanded = expandedCodeIds[activityId] ?? isLive;

              return (
                <motion.div
                  key={activityId}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex flex-col gap-1.5 rounded-lg bg-[var(--color-surface)]/60 border border-[var(--color-border)]/60 p-2.5"
                >
                  {/* Step row */}
                  <div className="flex items-start gap-2.5">
                    {/* Status badge */}
                    <div className="flex-shrink-0 mt-0.5">
                      {isRunning ? (
                        <div className="w-5 h-5 rounded-md flex items-center justify-center bg-indigo-500/10 text-indigo-400">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        </div>
                      ) : isFailed ? (
                        <div className="w-5 h-5 rounded-md flex items-center justify-center bg-rose-500/10 text-rose-400">
                          <AlertCircle className="w-3.5 h-3.5" />
                        </div>
                      ) : (
                        <div className="w-5 h-5 rounded-md flex items-center justify-center bg-emerald-500/10 text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        </div>
                      )}
                    </div>

                    {/* Step message & details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5">
                          <Icon className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                          <span
                            className={`font-medium ${
                              isRunning
                                ? "text-[var(--color-text-primary)]"
                                : isFailed
                                ? "text-rose-400"
                                : "text-[var(--color-text-secondary)]"
                            }`}
                          >
                            {activity.message}
                          </span>
                        </div>

                        {activity.metadata?.execution_time_ms && (
                          <span
                            className="text-[10px] text-[var(--color-text-muted)] shrink-0"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {Math.round(activity.metadata.execution_time_ms)}ms
                          </span>
                        )}
                      </div>

                      {/* Result metric badge if present */}
                      {calcResult !== undefined && calcResult !== null && (
                        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-emerald-400 font-mono">
                          <Terminal className="w-3 h-3 text-emerald-500" />
                          <span>Output: {String(calcResult)}</span>
                        </div>
                      )}

                      {/* Collapsible Python Code Block */}
                      {hasCode && (
                        <div className="mt-2 flex flex-col gap-1.5">
                          <button
                            type="button"
                            onClick={() => toggleCode(activityId)}
                            className="self-start inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--color-surface-hover)] hover:bg-[var(--color-border)] text-[11px] text-[var(--color-text-secondary)] transition-colors"
                          >
                            <Code2 className="w-3 h-3 text-amber-400" />
                            <span>{isCodeExpanded ? "Hide Python code" : "View Python code"}</span>
                            {isCodeExpanded ? (
                              <ChevronDown className="w-3 h-3 text-[var(--color-text-muted)]" />
                            ) : (
                              <ChevronRight className="w-3 h-3 text-[var(--color-text-muted)]" />
                            )}
                          </button>

                          <AnimatePresence>
                            {isCodeExpanded && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ duration: 0.15 }}
                                className="relative rounded-md bg-[#0d1117] border border-white/10 p-2.5 overflow-hidden"
                              >
                                <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-white/5 text-[10px] text-zinc-400 font-mono">
                                  <span>python (sandboxed)</span>
                                  <button
                                    type="button"
                                    onClick={(e) => handleCopyCode(code, activityId, e)}
                                    className="flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-colors"
                                  >
                                    {copiedCodeId === activityId ? (
                                      <>
                                        <Check className="w-3 h-3 text-emerald-400" />
                                        <span className="text-emerald-400">Copied</span>
                                      </>
                                    ) : (
                                      <>
                                        <Copy className="w-3 h-3" />
                                        <span>Copy</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                                <pre className="font-mono text-[11px] text-zinc-200 overflow-x-auto whitespace-pre leading-relaxed p-1">
                                  <code>{code}</code>
                                </pre>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
