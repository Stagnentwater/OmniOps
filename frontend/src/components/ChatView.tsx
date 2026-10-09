"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, User, X, Plus, MessageSquare, 
  BookOpen, FileText, ChevronRight, ImagePlus, Eye
} from "lucide-react";
import { AgentActivityStream, AgentActivityItem } from "@/components/AgentActivityStream";

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
            {/* Idle Placeholder */}
            {messages.length === 0 && mode === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 flex flex-col items-center justify-center text-center gap-4 my-auto"
              >
                <div className="w-16 h-16 rounded-2xl border border-dashed border-[var(--color-border)] flex items-center justify-center opacity-30">
                  <Search className="w-7 h-7 text-[var(--color-text-muted)]" />
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--color-text-muted)]">
                    Query the Knowledge Base
                  </p>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1 opacity-60 max-w-[280px]">
                    Ask questions about your industrial documents. The system will retrieve context from the knowledge graph and generate a grounded answer.
                  </p>
                </div>
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
