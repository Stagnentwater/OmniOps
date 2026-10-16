"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  Download,
  ShieldCheck,
  ShieldAlert,
  CheckCircle,
  Clock,
  Search,
  Filter,
  Eye,
  X,
  FileCode,
  Layers,
  Sparkles,
  AlertTriangle,
  ExternalLink,
  ChevronRight,
  User,
  Building,
  Wrench,
  Check,
} from "lucide-react";
import { ApiClient } from "@/services/api";

export interface DeliverableItem {
  id: string;
  document_id?: string;
  permit_id?: string;
  title: string;
  file_name?: string;
  format: "docx" | "pdf" | "pptx" | "permit" | string;
  file_size_bytes?: number;
  created_at: string;
  session_id?: string;
  session_title?: string;
  status: string;
  type: "deliverable" | "permit";
  download_url?: string | null;
  equipment_tag?: string;
  facility_name?: string;
  authorized_by?: string | null;
  evidence_ledger?: any;
  permit_data?: any;
}

export interface DeliverablesViewProps {
  deliverables: DeliverableItem[];
  onRefresh?: () => void;
  onGoToChat?: (initialPrompt?: string) => void;
  onNavigateToChat?: (initialPrompt?: string) => void;
}

export function DeliverablesView({
  deliverables,
  onRefresh,
  onGoToChat,
  onNavigateToChat,
}: DeliverablesViewProps) {
  const handleChatNav = onNavigateToChat || onGoToChat;
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFormat, setSelectedFormat] = useState<string>("all");
  const [inspectingItem, setInspectingItem] = useState<DeliverableItem | null>(null);

  // Sign-off modal state
  const [signOffName, setSignOffName] = useState("");
  const [signOffRole, setSignOffRole] = useState("Senior Plant Safety Officer");
  const [signOffConfirmed, setSignOffConfirmed] = useState(false);
  const [isSigningOff, setIsSigningOff] = useState(false);
  const [signOffError, setSignOffError] = useState<string | null>(null);

  // Filtered deliverables
  const filteredDeliverables = useMemo(() => {
    return deliverables.filter((item) => {
      const matchesSearch =
        searchQuery === "" ||
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (item.file_name && item.file_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (item.equipment_tag && item.equipment_tag.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (item.session_title && item.session_title.toLowerCase().includes(searchQuery.toLowerCase()));

      if (!matchesSearch) return false;

      if (selectedFormat === "all") return true;
      if (selectedFormat === "permit") return item.type === "permit" || item.format === "permit";
      if (selectedFormat === "docx") return item.format === "docx";
      if (selectedFormat === "pdf") return item.format === "pdf";
      if (selectedFormat === "pptx") return item.format === "pptx";

      return true;
    });
  }, [deliverables, searchQuery, selectedFormat]);

  // Summary counts
  const stats = useMemo(() => {
    const total = deliverables.length;
    const permits = deliverables.filter((d) => d.type === "permit" || d.format === "permit").length;
    const wordDocs = deliverables.filter((d) => d.format === "docx").length;
    const pdfs = deliverables.filter((d) => d.format === "pdf").length;
    const presentations = deliverables.filter((d) => d.format === "pptx").length;
    return { total, permits, wordDocs, pdfs, presentations };
  }, [deliverables]);

  const handleSignOff = async (permitId: string) => {
    if (!signOffConfirmed) {
      setSignOffError("Please confirm the physical site inspection checklist.");
      return;
    }
    if (!signOffName.trim()) {
      setSignOffError("Please enter your name as authorizing officer.");
      return;
    }

    setIsSigningOff(true);
    setSignOffError(null);
    try {
      const res = await ApiClient.signOffPermit(permitId, {
        reviewer_name: signOffName.trim(),
        reviewer_role: signOffRole.trim(),
        signature_confirmed: true,
        is_automated_agent: false,
      });
      if (res.success && res.permit) {
        if (inspectingItem && (inspectingItem.permit_id === permitId || inspectingItem.id === permitId)) {
          setInspectingItem({
            ...inspectingItem,
            status: "AUTHORIZED_BY_HUMAN",
            authorized_by: res.permit.authorized_by,
            permit_data: res.permit,
          });
        }
        onRefresh?.();
      }
    } catch (err: any) {
      setSignOffError(err?.message || "Sign-off authorization failed.");
    } finally {
      setIsSigningOff(false);
    }
  };

  const getFormatBadge = (item: DeliverableItem) => {
    const fmt = item.format.toLowerCase();
    if (item.type === "permit" || fmt === "permit") {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
          <ShieldCheck className="w-3 h-3" /> PERMIT
        </span>
      );
    }
    if (fmt === "pdf") {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center gap-1">
          <FileText className="w-3 h-3" /> PDF
        </span>
      );
    }
    if (fmt === "pptx") {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-orange-500/10 text-orange-400 border border-orange-500/30 flex items-center gap-1">
          <Layers className="w-3 h-3" /> PPTX
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-blue-500/10 text-blue-400 border border-blue-500/30 flex items-center gap-1">
        <FileText className="w-3 h-3" /> DOCX
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "AUTHORIZED_BY_HUMAN":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> Authorized
          </span>
        );
      case "READY_FOR_REVIEW":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-500/10 text-blue-400 border border-blue-500/30 flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" /> Ready for Review
          </span>
        );
      case "VERIFIED":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> Verified
          </span>
        );
      case "VERIFICATION_INCOMPLETE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Gaps Detected
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-zinc-500/10 text-zinc-400 border border-zinc-500/30">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--color-surface)] overflow-hidden">
      {/* Top Header */}
      <div className="h-16 px-6 border-b border-[var(--color-border)] flex items-center justify-between shrink-0 bg-[var(--color-surface-elevated)]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-[var(--color-text-primary)] uppercase tracking-wider flex items-center gap-2">
              My Deliverables
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {stats.total} total
              </span>
            </h1>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
              Exported technical reports, presentations, and industrial work permits generated by your account.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-border)] text-xs text-[var(--color-text-secondary)] transition-colors"
            >
              Refresh
            </button>
          )}
          {onGoToChat && (
            <button
              onClick={() => onGoToChat("Generate a Word document report on ")}
              className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Generate in Chat</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* KPI Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-sm">
            <div className="text-[10px] font-mono uppercase text-[var(--color-text-muted)] tracking-wider">
              Total Deliverables
            </div>
            <div className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
              {stats.total}
            </div>
          </div>
          <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-sm">
            <div className="text-[10px] font-mono uppercase text-amber-400 tracking-wider flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" /> Work Permits
            </div>
            <div className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
              {stats.permits}
            </div>
          </div>
          <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-sm">
            <div className="text-[10px] font-mono uppercase text-blue-400 tracking-wider flex items-center gap-1">
              <FileText className="w-3 h-3" /> Word (.docx)
            </div>
            <div className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
              {stats.wordDocs}
            </div>
          </div>
          <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-sm">
            <div className="text-[10px] font-mono uppercase text-rose-400 tracking-wider flex items-center gap-1">
              <FileText className="w-3 h-3" /> PDF Reports
            </div>
            <div className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
              {stats.pdfs}
            </div>
          </div>
          <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-sm">
            <div className="text-[10px] font-mono uppercase text-orange-400 tracking-wider flex items-center gap-1">
              <Layers className="w-3 h-3" /> Slide Decks
            </div>
            <div className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
              {stats.presentations}
            </div>
          </div>
        </div>

        {/* Toolbar: Search & Format Filter */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-[var(--color-surface-elevated)] p-2.5 rounded-xl border border-[var(--color-border)]">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-[var(--color-text-muted)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title, equipment tag, or session..."
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500/50"
            />
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <button
              onClick={() => setSelectedFormat("all")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                selectedFormat === "all"
                  ? "bg-indigo-600 text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]"
              }`}
            >
              All ({deliverables.length})
            </button>
            <button
              onClick={() => setSelectedFormat("permit")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                selectedFormat === "permit"
                  ? "bg-amber-600 text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]"
              }`}
            >
              Permits ({stats.permits})
            </button>
            <button
              onClick={() => setSelectedFormat("docx")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                selectedFormat === "docx"
                  ? "bg-blue-600 text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]"
              }`}
            >
              Word ({stats.wordDocs})
            </button>
            <button
              onClick={() => setSelectedFormat("pdf")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                selectedFormat === "pdf"
                  ? "bg-rose-600 text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]"
              }`}
            >
              PDF ({stats.pdfs})
            </button>
            <button
              onClick={() => setSelectedFormat("pptx")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                selectedFormat === "pptx"
                  ? "bg-orange-600 text-white"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]"
              }`}
            >
              Slides ({stats.presentations})
            </button>
          </div>
        </div>

        {/* Deliverables List */}
        {filteredDeliverables.length === 0 ? (
          <div className="p-12 rounded-2xl bg-[var(--color-surface-elevated)] border border-dashed border-[var(--color-border)] text-center flex flex-col items-center justify-center">
            <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-3">
              <FileText className="w-7 h-7" />
            </div>
            <h3 className="text-sm font-bold text-[var(--color-text-primary)]">
              No Deliverables Found
            </h3>
            <p className="text-xs text-[var(--color-text-muted)] max-w-md mt-1 mb-4 leading-relaxed">
              {deliverables.length === 0
                ? "You haven't generated any documents or permits yet. Ask OmniOps in the Chat tab: 'Generate a Word document report on P-101A pump maintenance' or 'Draft a hot work permit' to generate real deliverables."
                : "No deliverables match the active search or format filter."}
            </p>
            {handleChatNav && (
              <button
                onClick={() => handleChatNav("Generate a Word document report on ")}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-md cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                <span>Generate Your First Deliverable in Chat</span>
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredDeliverables.map((item) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-indigo-500/40 transition-all flex flex-col justify-between shadow-sm group"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    {getFormatBadge(item)}
                    {getStatusBadge(item.status)}
                  </div>

                  {/* Title & Tag */}
                  <h3 className="text-xs font-bold text-[var(--color-text-primary)] line-clamp-2 group-hover:text-indigo-300 transition-colors">
                    {item.title}
                  </h3>

                  {item.equipment_tag && (
                    <div className="mt-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-zinc-300 border border-zinc-700">
                      <Wrench className="w-3 h-3 text-indigo-400" />
                      <span>{item.equipment_tag}</span>
                    </div>
                  )}

                  {/* Meta details */}
                  <div className="mt-3 pt-2.5 border-t border-[var(--color-border)] space-y-1 text-[11px] text-[var(--color-text-muted)]">
                    {item.file_name && (
                      <div className="truncate font-mono text-[10px] text-zinc-400">
                        {item.file_name}
                      </div>
                    )}
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3 h-3 shrink-0" />
                      <span>
                        {new Date(item.created_at).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                    {item.session_title && (
                      <div className="truncate text-[10px] text-zinc-500">
                        Session: {item.session_title}
                      </div>
                    )}
                    {item.authorized_by && (
                      <div className="text-[10px] text-emerald-400 flex items-center gap-1 font-semibold">
                        <Check className="w-3 h-3 shrink-0" />
                        <span className="truncate">By: {item.authorized_by}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Actions */}
                <div className="mt-4 pt-3 border-t border-[var(--color-border)] flex items-center justify-between gap-2">
                  <button
                    onClick={() => setInspectingItem(item)}
                    className="px-2.5 py-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-border)] text-xs text-[var(--color-text-secondary)] flex items-center gap-1 transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </button>

                  {item.download_url || item.document_id ? (
                    <a
                      href={
                        item.download_url
                          ? (item.download_url.startsWith("http")
                              ? item.download_url
                              : `http://127.0.0.1:8000${item.download_url}`)
                          : ApiClient.getArtifactDownloadUrl(item.document_id || item.id)
                      }
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download</span>
                    </a>
                  ) : null}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Inspection Drawer / Modal ───────────────────────────── */}
      <AnimatePresence>
        {inspectingItem && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 sm:p-6"
            onClick={() => setInspectingItem(null)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 15 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 15 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="w-full max-w-3xl max-h-[85vh] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="h-14 px-5 border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2.5 min-w-0">
                  {getFormatBadge(inspectingItem)}
                  <h2 className="text-xs font-bold text-[var(--color-text-primary)] truncate">
                    {inspectingItem.title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  {inspectingItem.download_url || inspectingItem.document_id ? (
                    <a
                      href={
                        inspectingItem.download_url
                          ? (inspectingItem.download_url.startsWith("http")
                              ? inspectingItem.download_url
                              : `http://127.0.0.1:8000${inspectingItem.download_url}`)
                          : ApiClient.getArtifactDownloadUrl(inspectingItem.document_id || inspectingItem.id)
                      }
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download</span>
                    </a>
                  ) : null}
                  <button
                    onClick={() => setInspectingItem(null)}
                    className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border)] transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Modal Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs text-[var(--color-text-secondary)]">
                {/* Status & Provenance */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
                  <div>
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">Status:</span>
                    <div className="mt-0.5">{getStatusBadge(inspectingItem.status)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">Asset Tag:</span>
                    <div className="mt-0.5 font-mono text-[var(--color-text-primary)] font-semibold">
                      {inspectingItem.equipment_tag || "General Asset"}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">Format:</span>
                    <div className="mt-0.5 uppercase font-mono font-bold text-indigo-400">
                      {inspectingItem.format}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">Created:</span>
                    <div className="mt-0.5 text-zinc-300">
                      {new Date(inspectingItem.created_at).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </div>
                  </div>
                </div>

                {/* If Permit: Isolation Schedule & Gas Limits */}
                {inspectingItem.permit_data && (
                  <div className="space-y-4">
                    <h3 className="text-xs font-bold text-[var(--color-text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-amber-400" />
                      Industrial Work Permit Specification
                    </h3>

                    {/* Work Scope */}
                    <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
                      <div className="text-[10px] font-mono text-zinc-500 uppercase mb-1">
                        Scope of Work
                      </div>
                      <p className="text-xs text-[var(--color-text-primary)] leading-relaxed whitespace-pre-wrap">
                        {inspectingItem.permit_data.work_description}
                      </p>
                    </div>

                    {/* Hazards & Precautions */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {inspectingItem.permit_data.hazards_identified?.length > 0 && (
                        <div className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
                          <div className="text-[10px] font-mono text-rose-400 uppercase mb-1.5 font-bold flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Identified Hazards
                          </div>
                          <ul className="list-disc pl-4 space-y-1 text-[11px] text-zinc-300">
                            {inspectingItem.permit_data.hazards_identified.map((h: string, i: number) => (
                              <li key={i}>{h}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {inspectingItem.permit_data.required_precautions?.length > 0 && (
                        <div className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
                          <div className="text-[10px] font-mono text-emerald-400 uppercase mb-1.5 font-bold flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> Mandatory Safety Precautions
                          </div>
                          <ul className="list-disc pl-4 space-y-1 text-[11px] text-zinc-300">
                            {inspectingItem.permit_data.required_precautions.map((p: string, i: number) => (
                              <li key={i}>{p}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Gas Limits if CSE / Hot Work */}
                    {inspectingItem.permit_data.gas_testing && (
                      <div className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
                        <div className="text-[10px] font-mono text-amber-400 uppercase mb-2 font-bold">
                          Atmospheric Gas Boundaries (OSHA Compliant)
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                          <div className="bg-[var(--color-surface)] p-2 rounded border border-[var(--color-border)]">
                            <span className="text-zinc-500">O₂ Range:</span>{" "}
                            <span className="text-zinc-200">
                              {inspectingItem.permit_data.gas_testing.oxygen_min_percent}% -{" "}
                              {inspectingItem.permit_data.gas_testing.oxygen_max_percent}%
                            </span>
                          </div>
                          <div className="bg-[var(--color-surface)] p-2 rounded border border-[var(--color-border)]">
                            <span className="text-zinc-500">Max LEL:</span>{" "}
                            <span className="text-zinc-200">
                              &le; {inspectingItem.permit_data.gas_testing.lel_max_percent}%
                            </span>
                          </div>
                          <div className="bg-[var(--color-surface)] p-2 rounded border border-[var(--color-border)]">
                            <span className="text-zinc-500">Max H₂S:</span>{" "}
                            <span className="text-zinc-200">
                              &le; {inspectingItem.permit_data.gas_testing.h2s_max_ppm || 10} ppm
                            </span>
                          </div>
                          <div className="bg-[var(--color-surface)] p-2 rounded border border-[var(--color-border)]">
                            <span className="text-zinc-500">Max CO:</span>{" "}
                            <span className="text-zinc-200">
                              &le; {inspectingItem.permit_data.gas_testing.co_max_ppm || 25} ppm
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* LOTO Isolation Schedule */}
                    {inspectingItem.permit_data.isolation_points?.length > 0 && (
                      <div className="p-3.5 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
                        <div className="text-[10px] font-mono text-indigo-400 uppercase mb-2 font-bold">
                          Lockout / Tagout (LOTO) Energy Isolation Schedule
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-[11px]">
                            <thead>
                              <tr className="border-b border-[var(--color-border)] text-zinc-500 font-mono">
                                <th className="pb-1.5">Tag</th>
                                <th className="pb-1.5">Type</th>
                                <th className="pb-1.5">Required Position</th>
                                <th className="pb-1.5">Location</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--color-border)] text-zinc-300">
                              {inspectingItem.permit_data.isolation_points.map((pt: any, i: number) => (
                                <tr key={i} className="font-mono">
                                  <td className="py-1.5 text-indigo-300 font-bold">{pt.tag}</td>
                                  <td className="py-1.5">{pt.isolation_type}</td>
                                  <td className="py-1.5 text-amber-300">{pt.status}</td>
                                  <td className="py-1.5 text-zinc-400">{pt.location}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Human Sign-Off Section */}
                    <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-500/5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-[var(--color-text-primary)] uppercase flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-indigo-400" />
                          Authorized Human Review & Countersign
                        </h4>
                        <span className="text-[10px] text-zinc-400 font-mono">
                          Safety Boundary Authority
                        </span>
                      </div>

                      {inspectingItem.status === "AUTHORIZED_BY_HUMAN" ? (
                        <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 shrink-0" />
                          <div>
                            <div className="font-bold">Permit Authorized for Live Plant Operations</div>
                            <div className="text-[10px] opacity-80 mt-0.5 font-mono">
                              Countersigned by: {inspectingItem.authorized_by}
                            </div>
                          </div>
                        </div>
                      ) : inspectingItem.status === "READY_FOR_REVIEW" ? (
                        <div className="space-y-3">
                          <p className="text-[11px] text-zinc-300">
                            This permit has passed deterministic safety rule checks and evidence grounding. As qualified safety officer, you may physical review and authorize below.
                          </p>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                            <div>
                              <label className="text-[10px] font-mono text-zinc-400 block mb-1">
                                Authorizing Officer Name
                              </label>
                              <input
                                type="text"
                                value={signOffName}
                                onChange={(e) => setSignOffName(e.target.value)}
                                placeholder="e.g. Sarah Jenkins"
                                className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)]"
                              />
                            </div>
                            <div>
                              <label className="text-[10px] font-mono text-zinc-400 block mb-1">
                                Role / Title
                              </label>
                              <input
                                type="text"
                                value={signOffRole}
                                onChange={(e) => setSignOffRole(e.target.value)}
                                placeholder="e.g. Plant Safety Officer"
                                className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)]"
                              />
                            </div>
                          </div>

                          <label className="flex items-start gap-2 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={signOffConfirmed}
                              onChange={(e) => setSignOffConfirmed(e.target.checked)}
                              className="mt-0.5 rounded border-zinc-700 text-indigo-600 focus:ring-0"
                            />
                            <span className="text-[11px] text-zinc-300">
                              I confirm physical verification of zero energy state, atmospheric gas calibration, and Lockout/Tagout isolation points.
                            </span>
                          </label>

                          {signOffError && (
                            <div className="text-[11px] text-rose-400 font-semibold bg-rose-500/10 p-2 rounded border border-rose-500/20">
                              {signOffError}
                            </div>
                          )}

                          <button
                            onClick={() =>
                              handleSignOff(inspectingItem.permit_id || inspectingItem.id)
                            }
                            disabled={isSigningOff}
                            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-2 transition-all shadow-md disabled:opacity-50"
                          >
                            <ShieldCheck className="w-4 h-4" />
                            <span>
                              {isSigningOff
                                ? "Recording Sign-Off..."
                                : "Authorize & Sign-Off Work Permit"}
                            </span>
                          </button>
                        </div>
                      ) : (
                        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 shrink-0" />
                          <div className="text-[11px]">
                            Permit has unresolved safety gaps or unverified claims. Resolve gaps before human sign-off can proceed.
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Evidence Ledger Section */}
                {inspectingItem.evidence_ledger && inspectingItem.evidence_ledger.entries?.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold text-[var(--color-text-primary)] uppercase tracking-wider flex items-center gap-1.5">
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                      Grounded Evidence Ledger ({inspectingItem.evidence_ledger.entries.length} Claims)
                    </h3>
                    <div className="overflow-x-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] p-2">
                      <table className="w-full text-left text-[11px]">
                        <thead>
                          <tr className="border-b border-[var(--color-border)] text-zinc-500 font-mono">
                            <th className="pb-1.5 px-2">ID</th>
                            <th className="pb-1.5 px-2">Claim Text</th>
                            <th className="pb-1.5 px-2">Source Document</th>
                            <th className="pb-1.5 px-2">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--color-border)] text-zinc-300">
                          {inspectingItem.evidence_ledger.entries.map((ent: any, i: number) => (
                            <tr key={i}>
                              <td className="py-2 px-2 font-mono text-indigo-400">{ent.claim_id}</td>
                              <td className="py-2 px-2 max-w-xs">{ent.claim_text}</td>
                              <td className="py-2 px-2 font-mono text-[10px] text-zinc-400">
                                {ent.source_document_id} (p.{ent.page_index})
                              </td>
                              <td className="py-2 px-2">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase ${
                                    ent.verification_status === "VERIFIED"
                                      ? "bg-emerald-500/10 text-emerald-400"
                                      : "bg-amber-500/10 text-amber-400"
                                  }`}
                                >
                                  {ent.verification_status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
