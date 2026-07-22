"use client";

import { useState, useEffect, useCallback } from "react";
import { Activity, ShieldAlert, CheckCircle2, AlertTriangle, Loader2, Database, Network, GitCommit, Sparkles } from "lucide-react";
import { ApiClient } from "@/services/api";
import { motion, AnimatePresence, useSpring, useTransform } from "framer-motion";

function StatCard({ value, label, icon: Icon, colorClass }: { value: number, label: string, icon: any, colorClass: string }) {
  const spring = useSpring(0, { mass: 1, stiffness: 50, damping: 20 });
  const display = useTransform(spring, (current) => Math.round(current));
  
  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] shadow-sm">
      <div className={`w-8 h-8 rounded-lg mb-2 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] ${colorClass}`}>
        <Icon className="w-4 h-4" />
      </div>
      <motion.span className={`text-xl font-bold tabular-nums ${colorClass}`}>
        {display}
      </motion.span>
      <span className="text-[10px] font-medium text-[var(--color-text-muted)] mt-1 uppercase tracking-wider">{label}</span>
    </div>
  );
}

interface SystemStatusPanelProps {
  /** Incremented externally to trigger a stats-only refetch (e.g. after ingestion) */
  refreshToken?: number;
}

export function SystemStatusPanel({ refreshToken = 0 }: SystemStatusPanelProps) {
  const [statusText, setStatusText] = useState<string | null>(null);
  const [stats, setStats] = useState<{chunks: number, entities: number, relationships: number} | null>(null);
  const [isStatsLoading, setIsStatsLoading] = useState(true);
  const [isStatusLoading, setIsStatusLoading] = useState(false);
  const [hasGenerated, setHasGenerated] = useState(false);

  // Fetch only lightweight stats on mount (no LLM tokens consumed)
  useEffect(() => {
    fetchStats();
  }, []);

  // Refetch stats whenever refreshToken changes (e.g. after ingestion)
  useEffect(() => {
    if (refreshToken > 0) {
      fetchStats();
    }
  }, [refreshToken]);

  const fetchStats = async () => {
    setIsStatsLoading(true);
    try {
      const statsRes = await ApiClient.getKnowledgeStatistics();
      setStats({
        chunks: statsRes.chunks || 0,
        entities: statsRes.entities || 0,
        relationships: statsRes.relationships || 0,
      });
    } catch (err) {
      console.error("Failed to fetch knowledge statistics", err);
    } finally {
      setIsStatsLoading(false);
    }
  };

  const generateStatus = async () => {
    setIsStatusLoading(true);
    try {
      const statusRes = await ApiClient.getSystemStatus();
      setStatusText(statusRes.status);
      setHasGenerated(true);
    } catch (err) {
      console.error("Failed to fetch system status", err);
      setStatusText("Unable to assess system status. Please ensure the backend is reachable.");
      setHasGenerated(true);
    } finally {
      setIsStatusLoading(false);
    }
  };

  const renderStatus = () => {
    if (!statusText) return null;
    
    // Quick and dirty markdown rendering for bullet points and bold text
    let html = statusText;
    
    // Bold text
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--color-text-primary)] font-semibold">$1</strong>');
    
    // Bullet points (split by newline and process)
    const lines = html.split('\n');
    const processedLines = lines.map(line => {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const isWarning = trimmed.toLowerCase().includes('risk') || trimmed.toLowerCase().includes('critical') || trimmed.toLowerCase().includes('issue') || trimmed.toLowerCase().includes('warning') || trimmed.toLowerCase().includes('anomaly');
        const bulletColor = isWarning ? 'text-amber-500' : 'text-indigo-400';
        return `<li class="flex items-start gap-2 mb-2"><span class="${bulletColor} mt-1 flex-shrink-0">•</span><span>${trimmed.substring(2)}</span></li>`;
      }
      return trimmed ? `<p class="mb-3">${trimmed}</p>` : '';
    });
    
    // Wrap consecutive list items in <ul>
    let result = '';
    let inList = false;
    for (const line of processedLines) {
      if (line.startsWith('<li')) {
        if (!inList) {
          result += '<ul class="space-y-1 mb-4">';
          inList = true;
        }
        result += line;
      } else {
        if (inList) {
          result += '</ul>';
          inList = false;
        }
        result += line;
      }
    }
    if (inList) result += '</ul>';

    return <div dangerouslySetInnerHTML={{ __html: result }} className="text-sm text-[var(--color-text-secondary)] leading-relaxed" />;
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-surface)] border-r border-[var(--color-border)] relative z-10 shadow-2xl shrink-0 w-[32.5%] overflow-hidden">
      {/* Header */}
      <div className="h-14 border-b border-[var(--color-border)] flex items-center px-5 gap-3 shrink-0 bg-[var(--color-surface-elevated)]/50">
        <div className="w-6 h-6 rounded-md bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center">
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <span className="font-bold text-sm tracking-wide text-[var(--color-text-primary)]">SYSTEM STATUS</span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        
        {/* Stats Cards — always visible, lightweight fetch */}
        {stats && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-3 gap-3 mb-6"
          >
            <StatCard value={stats.chunks} label="Chunks" icon={Database} colorClass="text-cyan-400" />
            <StatCard value={stats.entities} label="Entities" icon={GitCommit} colorClass="text-violet-400" />
            <StatCard value={stats.relationships} label="Relations" icon={Network} colorClass="text-amber-400" />
          </motion.div>
        )}

        {isStatsLoading && !stats && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            {[0, 1, 2].map(i => (
              <div key={i} className="flex flex-col items-center justify-center p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)]">
                <div className="w-8 h-8 rounded-lg mb-2 bg-[var(--color-surface)] animate-pulse" />
                <div className="h-6 w-10 bg-[var(--color-surface)] animate-pulse rounded mb-1" />
                <div className="h-3 w-14 bg-[var(--color-surface)] animate-pulse rounded" />
              </div>
            ))}
          </div>
        )}

        {/* Operational Overview Section */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">Operational Overview</h2>
            <p className="text-xs text-[var(--color-text-muted)]">LLM-generated safety risk analysis</p>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {isStatusLoading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col gap-4"
            >
              <div className="flex items-center gap-3 p-4 rounded-xl border border-indigo-500/30 bg-indigo-500/5">
                <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                <span className="text-sm font-medium text-indigo-300">Synthesizing global context...</span>
              </div>
              
              <div className="space-y-3 mt-4">
                <div className="h-4 w-3/4 bg-[var(--color-surface-elevated)] animate-pulse rounded" />
                <div className="h-4 w-full bg-[var(--color-surface-elevated)] animate-pulse rounded" />
                <div className="h-4 w-5/6 bg-[var(--color-surface-elevated)] animate-pulse rounded" />
                <div className="h-4 w-1/2 bg-[var(--color-surface-elevated)] animate-pulse rounded mt-6" />
                <div className="h-4 w-full bg-[var(--color-surface-elevated)] animate-pulse rounded" />
              </div>
            </motion.div>
          ) : hasGenerated ? (
            <motion.div
              key="content"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col"
            >
              <div className="p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] shadow-sm">
                {renderStatus()}
              </div>

              {statusText && (statusText.toLowerCase().includes("risk") || statusText.toLowerCase().includes("issue")) && (
                <div className="mt-6 flex items-start gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10">
                  <ShieldAlert className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-amber-500">Safety Risks Detected</h4>
                    <p className="text-xs text-amber-500/80 mt-1 leading-relaxed">
                      The GraphRAG analysis identified potential operational risks based on recent knowledge base updates. Review the highlights above.
                    </p>
                  </div>
                </div>
              )}

              {/* Re-generate button */}
              <button
                onClick={generateStatus}
                className="mt-4 self-end flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-indigo-500/50 text-[var(--color-text-muted)] hover:text-indigo-400 transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Regenerate
              </button>
            </motion.div>
          ) : (
            <motion.div
              key="generate-prompt"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col items-center justify-center py-10"
            >
              <div className="w-14 h-14 rounded-2xl border border-dashed border-[var(--color-border)] flex items-center justify-center mb-4 opacity-40">
                <Sparkles className="w-6 h-6 text-[var(--color-text-muted)]" />
              </div>
              <p className="text-sm text-[var(--color-text-muted)] mb-1">No analysis generated yet</p>
              <p className="text-xs text-[var(--color-text-muted)] opacity-60 mb-5 text-center max-w-[220px]">
                Click below to run a safety risk analysis using GraphRAG over your knowledge base.
              </p>
              <button
                onClick={generateStatus}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-indigo-500/15 border border-indigo-500/40 text-indigo-400 hover:bg-indigo-500/25 hover:border-indigo-400 transition-all"
              >
                <Sparkles className="w-4 h-4" />
                Generate Analysis
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
