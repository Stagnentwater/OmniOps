"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, User, X, Plus, MessageSquare, 
  BookOpen, FileText, ChevronRight, ImagePlus, Eye,
  Download, ShieldCheck, CheckCircle, AlertTriangle
} from "lucide-react";
import { ApiClient } from "@/services/api";
import { AgentActivityStream, AgentActivityItem } from "@/components/AgentActivityStream";
import { PIDThreeWayCheckCard } from "@/components/PIDThreeWayCheckCard";

export interface AttachedImageState {
  file?: File;
  previewUrl: string;
  base64: string;
  filename: string;
}

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: any[];
  created_at?: string;
  metadata?: any;
}

export interface ChatViewProps {
  // Attached Image state
  attachedImage?: AttachedImageState | null;
  onAttachedImageChange?: (image: AttachedImageState | null) => void;
  onPreviewImage?: (url: string, filename: string) => void;
  // Session state
  chatSessions: any[];
  activeSessionId: string | null;
  onLoadSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
  onNewChat: () => void;

  // Messages list (Full conversation history)
  messages: ChatMessageItem[];

  // Query state
  queryInput: string;
  onQueryInputChange: (value: string) => void;
  onQuerySubmit: (e: React.FormEvent) => void;
  mode: "idle" | "ingesting" | "querying" | "answered";
  activeQuery?: string;
  currentStage: string;
  activeMetadata: any | null;
  activeActivities?: AgentActivityItem[];

  // Answer + citations
  answer?: string;
  streamingAnswer?: string;
  citations: any[];
  hoveredCitationId: string | null;
  onHoveredCitationIdChange: (id: string | null) => void;
  onCitationClick: (citation: any) => void;
  onSelectMessageCitations?: (citations: any[]) => void;
  renderAnswerWithCitations: (text?: string, citations?: any[]) => React.ReactNode;

  // Documents (for citation display)
  documents: any[];

  // Deliverables navigation
  onNavigateToDeliverables?: () => void;
}

export function ChatView({
  chatSessions,
  activeSessionId,
  onLoadSession,
  onDeleteSession,
  onNewChat,
  messages,
  queryInput,
  onQueryInputChange,
  onQuerySubmit,
  mode,
  currentStage,
  activeMetadata,
  activeActivities,
  streamingAnswer,
  citations,
  hoveredCitationId,
  onHoveredCitationIdChange,
  onCitationClick,
  onSelectMessageCitations,
  renderAnswerWithCitations,
  documents,
  attachedImage,
  onAttachedImageChange,
  onPreviewImage,
  onNavigateToDeliverables,
}: ChatViewProps) {
  // ─── Scroll Container References & Detection ─────────────────
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isNearBottomRef = useRef<boolean>(true);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const handleFileChange = (file: File) => {
    if (!file) return;
    const isImg = /\.(png|jpe?g|tiff?)$/i.test(file.name) || file.type.startsWith("image/");
    if (!isImg) {
      alert("Please upload a valid image file (.png, .jpg, .jpeg, .tiff)");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const b64 = e.target?.result as string;
      const previewUrl = URL.createObjectURL(file);
      onAttachedImageChange?.({
        file,
        previewUrl,
        base64: b64,
        filename: file.name,
      });
    };
    reader.readAsDataURL(file);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) {
          handleFileChange(file);
          break;
        }
      }
    }
  };

  // Monitor user scrolling to determine if they're reading history
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    // If within 100px of bottom, consider user as "at bottom"
    isNearBottomRef.current = distanceFromBottom < 100;
  };

  // Auto-scroll to newest message ONLY when user is already near bottom
  useEffect(() => {
    if (isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, currentStage, streamingAnswer, mode, activeActivities]);

  // When switching or loading a session, jump to the latest message
  useEffect(() => {
    isNearBottomRef.current = true;
    messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
  }, [activeSessionId]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[var(--color-surface)] overflow-hidden">
      {/* View Header */}
      <div className="h-14 border-b border-[var(--color-border)] flex items-center px-6 gap-3 shrink-0 bg-[var(--color-surface-elevated)]/50">
        <span className="font-bold text-sm tracking-wide text-[var(--color-text-primary)]">
          CHAT WINDOW
        </span>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text-muted)] ml-auto"
        >
          {mode === "querying" ? "PROCESSING" : mode === "answered" ? "COMPLETE" : "READY"}
        </span>
      </div>

      {/* Three-column content */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* ─── Left: Session History ──────────────────────────── */}
        <div className="w-[260px] shrink-0 border-r border-[var(--color-border)] flex flex-col overflow-hidden">
          {/* New Chat button */}
          <div className="p-3 border-b border-[var(--color-border)]">
            <button
              onClick={onNewChat}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-semibold bg-indigo-500/15 border border-indigo-500/40 text-indigo-400 hover:bg-indigo-500/25 hover:border-indigo-400 transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              New Chat
            </button>
          </div>

          {/* Session list */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
            {chatSessions.length === 0 ? (
              <div className="text-xs text-[var(--color-text-muted)] py-4 text-center bg-[var(--color-surface-elevated)] rounded-lg border border-[var(--color-border)] border-dashed">
                No previous queries.
              </div>
            ) : (
              chatSessions.map(session => (
                <div
                  key={session.id}
                  onClick={() => onLoadSession(session.id)}
                  className={`flex flex-col gap-1 p-3 rounded-lg border cursor-pointer transition-colors group relative ${
                    activeSessionId === session.id
                      ? "bg-indigo-500/10 border-indigo-500/30"
                      : "bg-[var(--color-surface-elevated)] border-[var(--color-border)] hover:border-indigo-500/30"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2 min-w-0">
                      <MessageSquare className="w-3.5 h-3.5 text-[var(--color-text-muted)] mt-0.5 shrink-0" />
                      <span className="text-xs font-medium text-[var(--color-text-primary)] line-clamp-2">{session.title}</span>
                    </div>
                    <button
                      onClick={(e) => onDeleteSession(session.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-red-400/70 hover:text-red-400 hover:bg-red-400/10 rounded transition-all shrink-0"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <span className="text-[10px] text-[var(--color-text-muted)] font-mono pl-5">
                    {new Date(session.created_at).toLocaleString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ─── Middle: Active Thread (Scroll Container) ───────── */}
        <div className="flex-1 flex flex-col overflow-hidden border-r border-[var(--color-border)]">
          {/* Thread content scroll container */}
          <div 
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-5 flex flex-col gap-5 min-h-0"
          >
            {/* Idle Placeholder with Industrial Document & Query Starters */}
            {messages.length === 0 && mode === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex-1 flex flex-col items-center justify-center text-center gap-6 my-auto max-w-2xl mx-auto px-4 py-8"
              >
                <div className="flex flex-col items-center gap-2">
                  <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-lg shadow-indigo-500/5">
                    <FileText className="w-7 h-7" />
                  </div>
                  <h3 className="text-base font-semibold text-[var(--color-text-primary)]">
                    Industrial Knowledge & Document Intelligence
                  </h3>
                  <p className="text-xs text-[var(--color-text-muted)] max-w-md leading-relaxed">
                    Ask engineering questions, analyze P&IDs, or generate formal industrial deliverables (Word SOPs, slide presentations, PDFs, and work permits) directly through conversation.
                  </p>
                </div>

                {/* Prompt Starters */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
                  <button
                    type="button"
                    onClick={() => onQueryInputChange("Draft a Hot Work permit for welding on Vessel V-201 with gas testing requirements and LOTO isolation schedule")}
                    className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-amber-500/40 hover:bg-amber-500/5 transition-all text-left group flex items-start gap-2.5 cursor-pointer"
                  >
                    <ShieldCheck className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold text-[var(--color-text-primary)] group-hover:text-amber-300 transition-colors">
                        Draft Hot Work Permit
                      </div>
                      <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
                        Safety scope, LOTO isolation, and gas testing thresholds for Vessel V-201.
                      </div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => onQueryInputChange("Generate a formal Word report detailing the lockout tagout procedure and safety handover for Pump P-101A")}
                    className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-blue-500/40 hover:bg-blue-500/5 transition-all text-left group flex items-start gap-2.5 cursor-pointer"
                  >
                    <FileText className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold text-[var(--color-text-primary)] group-hover:text-blue-300 transition-colors">
                        Generate Technical Word Report
                      </div>
                      <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
                        Formal .docx handover report with evidence grounding and tables.
                      </div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => onQueryInputChange("Create a slide presentation on boiler feed water system failure modes, risk matrix, and mitigation actions")}
                    className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-orange-500/40 hover:bg-orange-500/5 transition-all text-left group flex items-start gap-2.5 cursor-pointer"
                  >
                    <FileText className="w-4 h-4 text-orange-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold text-[var(--color-text-primary)] group-hover:text-orange-300 transition-colors">
                        Create Slide Deck (.pptx)
                      </div>
                      <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
                        Executive PowerPoint presentation with structured slide cards.
                      </div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => onQueryInputChange("Generate a PDF document summarizing safety audit observations and equipment integrity checks")}
                    className="p-3 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-emerald-500/40 hover:bg-emerald-500/5 transition-all text-left group flex items-start gap-2.5 cursor-pointer"
                  >
                    <BookOpen className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-xs font-semibold text-[var(--color-text-primary)] group-hover:text-emerald-300 transition-colors">
                        Generate Safety PDF
                      </div>
                      <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
                        Audit observations and equipment integrity SOP in PDF format.
                      </div>
                    </div>
                  </button>
                </div>

                {onNavigateToDeliverables && (
                  <div className="flex items-center gap-2 text-[11px] text-[var(--color-text-muted)] bg-[var(--color-surface-elevated)] px-3 py-1.5 rounded-full border border-[var(--color-border)]">
                    <span>Generated deliverables are automatically cataloged in your account.</span>
                    <button
                      type="button"
                      onClick={onNavigateToDeliverables}
                      className="text-indigo-400 hover:text-indigo-300 font-semibold underline flex items-center gap-0.5"
                    >
                      Open Deliverables <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </motion.div>
            )}

            {/* Complete Chronological Message History */}
            {messages.map((message, idx) => {
              if (message.role === "user") {
                return (
                  <motion.div
                    key={message.id || `msg-${idx}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.15 }}
                    className="p-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] shadow-sm shrink-0"
                  >
                    <div className="flex items-start gap-3">
                      <User className="w-4 h-4 text-[var(--color-text-muted)] mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
                            Operator
                          </span>
                          {message.created_at && (
                            <span className="text-[10px] text-[var(--color-text-muted)] font-mono">
                              {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          )}
                        </div>
                        <p className="text-sm font-medium text-[var(--color-text-primary)] leading-relaxed whitespace-pre-wrap">
                          {message.content}
                        </p>

                        {/* Attached image preview if available */}
                        {(message.metadata?.image_base64 || message.metadata?.image_url) && (
                          <div className="mt-3">
                            <div
                              onClick={() => {
                                const rawUrl = message.metadata.image_url || message.metadata.image_base64;
                                const fullUrl = rawUrl.startsWith("http") || rawUrl.startsWith("blob:") || rawUrl.startsWith("data:") 
                                  ? rawUrl 
                                  : `http://127.0.0.1:8000${rawUrl}`;
                                onPreviewImage?.(fullUrl, message.metadata.image_filename || "Attached Image");
                              }}
                              className="inline-flex items-center gap-2.5 p-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-indigo-500/40 cursor-pointer transition-all group max-w-sm"
                            >
                              <img
                                src={
                                  message.metadata.image_url 
                                    ? (message.metadata.image_url.startsWith("http") || message.metadata.image_url.startsWith("blob:") || message.metadata.image_url.startsWith("data:")
                                        ? message.metadata.image_url
                                        : `http://127.0.0.1:8000${message.metadata.image_url}`)
                                    : message.metadata.image_base64
                                }
                                alt={message.metadata.image_filename || "Attached image"}
                                className="w-12 h-12 object-cover rounded-md border border-[var(--color-border)] shrink-0"
                              />
                              <div className="flex flex-col pr-2 overflow-hidden">
                                <span className="text-xs font-semibold text-[var(--color-text-primary)] truncate">
                                  {message.metadata.image_filename || "Attached Image"}
                                </span>
                                <span className="text-[10px] text-indigo-400 font-mono mt-0.5 flex items-center gap-1">
                                  <Eye className="w-3 h-3" /> Click to view
                                </span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              }

              // Assistant message
              return (
                <motion.div
                  key={message.id || `msg-${idx}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  onClick={() => {
                    if (message.citations && message.citations.length > 0 && onSelectMessageCitations) {
                      onSelectMessageCitations(message.citations);
                    }
                  }}
                  className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-xl p-5 shadow-sm shrink-0 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2 mb-4 pb-3 border-b border-[var(--color-border)]">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
                      <span className="text-xs font-bold tracking-wide uppercase text-[var(--color-text-primary)]">
                        OmniOps Intelligence
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      {message.citations && message.citations.length > 0 && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {message.citations.length} citation{message.citations.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {message.created_at && (
                        <span className="text-[10px] text-[var(--color-text-muted)] font-mono">
                          {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Historical agent activity accordion if present */}
                  {message.metadata?.activities && message.metadata.activities.length > 0 && (
                    <div className="mb-4">
                      <AgentActivityStream activities={message.metadata.activities} isLive={false} />
                    </div>
                  )}

                  {renderAnswerWithCitations(message.content, message.citations)}

                  {/* Version 4: Deliverable Download Card */}
                  {message.metadata?.artifact && (
                    <div className="mt-4 p-3.5 rounded-xl bg-[var(--color-surface)] border border-indigo-500/30 flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-bold text-xs uppercase shrink-0">
                          {message.metadata.artifact.format || "DOC"}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-[var(--color-text-primary)] truncate">
                            {message.metadata.artifact.title || message.metadata.artifact.file_name || "Generated Industrial Deliverable"}
                          </div>
                          <div className="text-[10px] text-[var(--color-text-muted)] flex items-center gap-2 mt-0.5">
                            <span className="truncate">{message.metadata.artifact.file_name}</span>
                            {message.metadata.artifact.file_size_bytes && (
                              <span>• {(message.metadata.artifact.file_size_bytes / 1024).toFixed(1)} KB</span>
                            )}
                            <span className="text-emerald-400 flex items-center gap-1 font-mono shrink-0">
                              <CheckCircle className="w-2.5 h-2.5" /> Evidence Verified
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {onNavigateToDeliverables && (
                          <button
                            type="button"
                            onClick={onNavigateToDeliverables}
                            className="px-2.5 py-1.5 rounded-lg bg-[var(--color-surface-elevated)] hover:bg-[var(--color-border)] text-indigo-400 hover:text-indigo-300 text-xs font-medium border border-indigo-500/20 transition-colors flex items-center gap-1 cursor-pointer"
                            title="View all your deliverables"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            <span>Deliverables Tab</span>
                          </button>
                        )}
                        <a
                          href={ApiClient.getArtifactDownloadUrl(message.metadata.artifact.document_id || message.metadata.document_id || message.id)}
                          download
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Download</span>
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Version 4: Industrial Permit Inspection & Review Card */}
                  {message.metadata?.permit && (
                    <div className="mt-4 p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex flex-col gap-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0" />
                          <span className="text-xs font-bold text-[var(--color-text-primary)] truncate">
                            {message.metadata.permit.title || "Industrial Work Permit"}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700 shrink-0">
                            {message.metadata.permit.permit_id}
                          </span>
                        </div>
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold shrink-0 ${
                          message.metadata.permit.status === 'AUTHORIZED_BY_HUMAN'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : message.metadata.permit.status === 'READY_FOR_REVIEW'
                            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        }`}>
                          {message.metadata.permit.status}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] text-[var(--color-text-muted)] bg-[var(--color-surface-elevated)] p-2.5 rounded-lg border border-[var(--color-border)]">
                        <div><span className="text-zinc-500">Asset Tag:</span> <span className="font-mono text-zinc-200">{message.metadata.permit.equipment_tag || "N/A"}</span></div>
                        <div><span className="text-zinc-500">Work Order:</span> <span className="font-mono text-zinc-200">{message.metadata.permit.work_order_number || "WO-PENDING"}</span></div>
                        {message.metadata.permit.gas_testing && (
                          <div className="col-span-2">
                            <span className="text-zinc-500">Gas Limits:</span>{" "}
                            <span className="font-mono text-zinc-200">
                              LEL &le; {message.metadata.permit.gas_testing.lel_max_percent}% | O₂ {message.metadata.permit.gas_testing.oxygen_min_percent}-{message.metadata.permit.gas_testing.oxygen_max_percent}%
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="flex items-center justify-between pt-1 border-t border-[var(--color-border)]">
                        {onNavigateToDeliverables ? (
                          <button
                            type="button"
                            onClick={onNavigateToDeliverables}
                            className="text-[11px] text-indigo-400 hover:text-indigo-300 underline font-medium flex items-center gap-1 cursor-pointer"
                          >
                            <span>Inspect & Countersign in Deliverables tab</span>
                            <ChevronRight className="w-3 h-3" />
                          </button>
                        ) : <div />}
                        {message.metadata.permit.status === 'AUTHORIZED_BY_HUMAN' && (
                          <div className="text-[11px] text-emerald-400 bg-emerald-500/5 px-2 py-1 rounded border border-emerald-500/20 flex items-center gap-1.5">
                            <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                            <span>Authorized By: {message.metadata.permit.authorized_by}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Version 4.1: P&ID 3-Way Verification Audit & Localized Symbol Card */}
                  {message.metadata?.three_way_checks && message.metadata.three_way_checks.length > 0 && (
                    <PIDThreeWayCheckCard
                      checks={message.metadata.three_way_checks}
                      onPreviewImage={onPreviewImage}
                    />
                  )}

                  {/* Version 4: Persistent Diagram Context Chip */}
                  {(message.metadata?.active_image_context || (idx === messages.length - 1 && activeMetadata?.active_image_context)) && (
                    <div className="mt-3 inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-[10px] text-indigo-300">
                      <Eye className="w-3 h-3 text-indigo-400 shrink-0" />
                      <span>Active Diagram Context: Persistent P&ID available for follow-up queries.</span>
                    </div>
                  )}
                </motion.div>
              );
            })}

            {/* Active querying indicator / live agent activity stream */}
            {mode === "querying" && (
              <motion.div 
                initial={{ opacity: 0, y: 6 }} 
                animate={{ opacity: 1, y: 0 }} 
                className="flex flex-col gap-4 shrink-0"
              >
                <AgentActivityStream activities={activeActivities || []} isLive={true} />

                {streamingAnswer ? (
                  <div className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-xl p-5 shadow-sm">
                    <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[var(--color-border)]">
                      <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.5)]" />
                      <span className="text-xs font-bold tracking-wide uppercase text-[var(--color-text-primary)]">
                        Generating Response...
                      </span>
                    </div>
                    {renderAnswerWithCitations(streamingAnswer)}
                  </div>
                ) : null}
              </motion.div>
            )}

            {/* Invisible anchor for auto-scroll target */}
            <div ref={messagesEndRef} className="h-0 shrink-0" />
          </div>

          {/* Input footer */}
          <div 
            className={`p-4 border-t border-[var(--color-border)] bg-[var(--color-surface)] shrink-0 transition-colors ${
              isDraggingOver ? "bg-indigo-500/5" : ""
            }`}
            onDragOver={(e) => { e.preventDefault(); setIsDraggingOver(true); }}
            onDragLeave={() => setIsDraggingOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDraggingOver(false);
              const file = e.dataTransfer.files?.[0];
              if (file && (file.type.startsWith("image/") || /\.(png|jpe?g|tiff?)$/i.test(file.name))) {
                handleFileChange(file);
              }
            }}
          >
            {/* Staged attachment preview */}
            <AnimatePresence>
              {attachedImage && (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 5 }}
                  className="mb-3 flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[var(--color-surface-elevated)] border border-indigo-500/40 w-fit shadow-sm"
                >
                  <img
                    src={attachedImage.previewUrl || attachedImage.base64}
                    alt={attachedImage.filename}
                    className="w-10 h-10 object-cover rounded-md border border-[var(--color-border)] shrink-0"
                  />
                  <div className="flex flex-col pr-1 min-w-0">
                    <span className="text-xs font-semibold text-[var(--color-text-primary)] max-w-[220px] truncate">
                      {attachedImage.filename}
                    </span>
                    <span className="text-[10px] text-indigo-400 font-mono">
                      Image attached for vision inspection
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onAttachedImageChange?.(null)}
                    className="p-1 rounded-md text-[var(--color-text-muted)] hover:text-red-400 hover:bg-red-400/10 transition-colors ml-1"
                    title="Remove attachment"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            <form onSubmit={onQuerySubmit} className="relative flex items-center gap-2">
              <input
                type="file"
                ref={fileInputRef}
                accept=".png,.jpg,.jpeg,.tif,.tiff,image/png,image/jpeg,image/tiff"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileChange(file);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={mode === "querying"}
                className={`p-3 rounded-lg border transition-all ${
                  attachedImage
                    ? "text-indigo-400 bg-indigo-500/15 border-indigo-500/40"
                    : "text-[var(--color-text-muted)] bg-[var(--color-surface-elevated)] border-[var(--color-border)] hover:text-indigo-400 hover:border-indigo-500/40"
                } disabled:opacity-50 shrink-0`}
                title="Attach equipment image or P&ID diagram"
              >
                <ImagePlus className="w-4 h-4" />
              </button>

              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)] pointer-events-none" />
                <input
                  type="text"
                  value={queryInput}
                  onChange={(e) => onQueryInputChange(e.target.value)}
                  onPaste={handlePaste}
                  placeholder={
                    attachedImage
                      ? "Ask about this image (e.g. 'Read the pressure gauge', 'Inspect for damage')..."
                      : "Query industrial knowledge base or attach an image..."
                  }
                  disabled={mode === "querying"}
                  className="w-full bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg pl-10 pr-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all disabled:opacity-50"
                />
              </div>
            </form>
          </div>
        </div>

        {/* ─── Right: Citations Panel ────────────────────────── */}
        <div className="w-[300px] shrink-0 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-[var(--color-border)] shrink-0">
            <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider flex items-center gap-2">
              <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
              Source Citations
            </h3>
          </div>

          {/* Citation cards */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
            {citations.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
                <div className="w-10 h-10 rounded-xl border border-dashed border-[var(--color-border)] flex items-center justify-center mb-3 opacity-30">
                  <FileText className="w-5 h-5 text-[var(--color-text-muted)]" />
                </div>
                <p className="text-xs text-[var(--color-text-muted)]">
                  Citations will appear here after a query is answered.
                </p>
              </div>
            ) : (
              citations.map((citation, idx) => {
                const doc = documents.find(d => d.id === citation.document_id);
                const isHovered = hoveredCitationId === citation.chunk_id;

                return (
                  <motion.div
                    key={citation.chunk_id || idx}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isHovered
                        ? "bg-indigo-500/15 border-indigo-500/40 shadow-sm"
                        : "bg-[var(--color-surface-elevated)] border-[var(--color-border)] hover:border-indigo-500/30"
                    }`}
                    onClick={() => onCitationClick(citation)}
                    onMouseEnter={() => onHoveredCitationIdChange(citation.chunk_id)}
                    onMouseLeave={() => onHoveredCitationIdChange(null)}
                  >
                    {/* Citation number badge */}
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                        [{idx + 1}]
                      </span>
                      <ChevronRight className="w-3 h-3 text-[var(--color-text-muted)]" />
                    </div>

                    {/* Source doc name */}
                    {doc && (
                      <p className="text-[11px] font-medium text-[var(--color-text-primary)] truncate mb-1">
                        {doc.filename}
                      </p>
                    )}

                    {/* Page number */}
                    {citation.page_index !== undefined && (
                      <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                        Page {citation.page_index + 1}
                      </span>
                    )}

                    {/* Preview of source text */}
                    {citation.source_text && (
                      <p className="text-[10px] text-[var(--color-text-muted)] mt-1.5 line-clamp-3 leading-relaxed">
                        {citation.source_text}
                      </p>
                    )}

                    {/* Confidence score */}
                    {citation.score !== undefined && (
                      <div className="mt-2 flex items-center gap-1.5">
                        <div className="flex-1 h-1 rounded-full bg-[var(--color-surface)] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-indigo-500/60"
                            style={{ width: `${Math.round(citation.score * 100)}%` }}
                          />
                        </div>
                        <span className="text-[9px] font-mono text-[var(--color-text-muted)]">
                          {(citation.score * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                  </motion.div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
