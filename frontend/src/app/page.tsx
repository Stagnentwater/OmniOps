"use client";

import { useState, useEffect, useMemo } from "react";
import { ApiClient } from "@/services/api";
import { GraphData } from "@/components/RetrievalGraph";
import { NavRail, ViewId } from "@/components/NavRail";
import { ChatView } from "@/components/ChatView";
import { KnowledgeBaseView } from "@/components/KnowledgeBaseView";
import { IngestionView } from "@/components/IngestionView";
import { OverviewView } from "@/components/OverviewView";
import { X, BookOpen, Download, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function UnifiedPage() {
  // ─── Navigation State ──────────────────────────────────────
  const [activeView, setActiveView] = useState<ViewId>("chat");

  // ─── Global State ─────────────────────────────────────────
  const [documents, setDocuments] = useState<any[]>([]);
  const [fullGraphData, setFullGraphData] = useState<GraphData | null>(null);
  const [statsRefreshToken, setStatsRefreshToken] = useState(0);
  
  // ─── Interaction State ────────────────────────────────────
  const [graphViewMode, setGraphViewMode] = useState<"global" | "retrieval">("global");
  const [activeDocViewer, setActiveDocViewer] = useState<{url: string, isPdf: boolean, filename: string} | null>(null);
  const [activeCitationPreview, setActiveCitationPreview] = useState<{source_text: string, document_id: string, page_index: number, chunk_id: string} | null>(null);
  const [hoveredCitationId, setHoveredCitationId] = useState<string | null>(null);

  // ─── View Modes ──────────────────────────────────────
  const [mode, setMode] = useState<"idle" | "ingesting" | "querying" | "answered">("idle");
  
  // ─── Session State ───────────────────────────────────────
  const [chatSessions, setChatSessions] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  
  // ─── Query State ─────────────────────────────────────────
  const [queryInput, setQueryInput] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [activeMetadata, setActiveMetadata] = useState<any | null>(null);
  const [currentStage, setCurrentStage] = useState<string>("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<any[]>([]);

  // ─── Load Initial Data ───────────────────────────────────
  useEffect(() => {
    fetchDocuments();
    fetchGraphData();
    fetchChatSessions();
  }, []);

  const fetchChatSessions = async () => {
    try {
      const res = await ApiClient.getChatSessions();
      setChatSessions(res);
    } catch (err) {
      console.error("Failed to load sessions", err);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await ApiClient.getDocuments();
      setDocuments(res.documents || []);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  const fetchGraphData = async () => {
    try {
      const data = await ApiClient.getKnowledgeGraph();
      // Transform backend response to react-force-graph format
      const nodes = data.nodes.map((n: any) => ({
        id: n.entity_id,
        name: n.canonical_name || n.entity_id,
        group: n.entity_type,
        val: n.entity_type === "Document" ? 5 : 3.5,
      }));
      
      const nodeIds = new Set(nodes.map((n: any) => n.id));
      const links = data.edges
        .filter((e: any) => nodeIds.has(e.source_entity_id) && nodeIds.has(e.target_entity_id))
        .map((e: any) => ({
          source: e.source_entity_id,
          target: e.target_entity_id,
          label: e.relationship_type
        }));

      setFullGraphData({ nodes, links });
    } catch (err) {
      console.error("Failed to load full graph", err);
    }
  };

  // ─── Query Execution ──────────────────────────────────────
  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim()) return;

    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      try {
        const res = await ApiClient.createChatSession();
        currentSessionId = res.session_id;
        setActiveSessionId(currentSessionId);
      } catch (err) {
        console.error("Failed to create session", err);
      }
    }

    const q = queryInput;
    setQueryInput("");
    setActiveQuery(q);
    setMode("querying");
    setCurrentStage("GENERATING_EMBEDDING");
    setAnswer("");
    setCitations([]);
    setActiveMetadata(null);
    setGraphViewMode("retrieval");

    try {
      await ApiClient.queryStream(q, null, currentSessionId, (event) => {
        if (event.stage) setCurrentStage(event.stage);
        
        if (event.stage === "COMPLETED") {
          setAnswer(event.result.answer);
          setCitations(event.result.citations || []);
          setActiveMetadata(event.result.metadata);
          setMode("answered");
          fetchChatSessions();
        } else if (event.stage === "FAILED") {
          setMode("idle");
          alert("Query failed: " + event.error);
        } else {
          if (event.metadata) {
            setActiveMetadata((prev: any) => ({ ...prev, ...event.metadata }));
          }
        }
      });
    } catch (err) {
      console.error(err);
      setMode("idle");
    }
  };

  // ─── Session Loading ──────────────────────────────────────
  const handleLoadSession = async (sessionId: string) => {
    try {
      const msgs = await ApiClient.getChatMessages(sessionId);
      if (msgs.length > 0) {
        const userMsg = msgs.slice().reverse().find(m => m.role === "user");
        const asstMsg = msgs.slice().reverse().find(m => m.role === "assistant");
        
        setActiveQuery(userMsg ? userMsg.content : "");
        setAnswer(asstMsg ? asstMsg.content : "");
        setCitations(asstMsg ? (asstMsg.citations || []) : []);
        setActiveMetadata(null);
        setActiveSessionId(sessionId);
        setCurrentStage("COMPLETED");
        setMode("answered");
        setGraphViewMode("global");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this chat session?")) return;
    try {
      await ApiClient.deleteChatSession(sessionId);
      if (activeSessionId === sessionId) {
        setMode("idle");
        setActiveSessionId(null);
      }
      fetchChatSessions();
    } catch (err) {
      console.error(err);
    }
  };

  const handleNewChat = () => {
    setMode("idle");
    setActiveQuery("");
    setAnswer("");
    setCitations([]);
    setActiveMetadata(null);
    setActiveSessionId(null);
    setGraphViewMode("global");
  };

  // ─── Citation & Document Viewing ────────────────────────
  const handleCitationClick = async (citation: any) => {
    setActiveCitationPreview({
      source_text: citation.source_text || "Source text not available.",
      document_id: citation.document_id,
      page_index: citation.page_index,
      chunk_id: citation.chunk_id,
    });
  };

  const handleOpenFullDocument = async () => {
    if (!activeCitationPreview) return;
    try {
      const doc = documents.find(d => d.id === activeCitationPreview.document_id);
      const filename = doc?.filename || "document";
      const isPdf = filename.toLowerCase().endsWith(".pdf");
      
      const url = await ApiClient.getDocumentContentUrl(activeCitationPreview.document_id);
      
      setActiveCitationPreview(null);
      
      setActiveDocViewer({
        url: isPdf ? `${url}#page=${activeCitationPreview.page_index + 1}` : url,
        isPdf,
        filename
      });
    } catch (err) {
      console.error("Failed to load document content", err);
    }
  };

  const renderAnswerWithCitations = () => {
    if (!answer) return null;
    let html = answer;
    
    // Simple markdown bold parsing
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--color-text-primary)] font-semibold">$1</strong>');
    
    // Pre-process: expand grouped citations like [Context #1, Context #2, Context #5]
    // into individual markers [Context #1][Context #2][Context #5]
    html = html.replace(/\[((?:Context\s*#\d+(?:\s*,\s*)?)+)\]/gi, (match, inner) => {
      const parts = inner.split(/\s*,\s*/);
      if (parts.length > 1) {
        return parts.map((p: string) => `[${p.trim()}]`).join('');
      }
      return match;
    });

    // Also handle grouped bare numbers like [1, 2, 5]
    html = html.replace(/\[((?:\d+(?:\s*,\s*)?){2,})\]/g, (match, inner) => {
      const parts = inner.split(/\s*,\s*/);
      return parts.map((p: string) => `[${p.trim()}]`).join('');
    });

    // Replace citation markers like [1], [2], or [Context #1] with interactive span elements
    html = html.replace(/\[(?:Context\s*#)?(\d+)\]/gi, (match, num) => {
      const idx = parseInt(num) - 1;
      const citation = citations[idx];
      if (!citation) return "";
      
      const chunkId = citation.chunk_id;
      return `<sup class="citation-marker cursor-pointer px-1 mx-0.5 rounded-sm bg-indigo-500/20 text-indigo-400 font-mono text-[10px] font-bold border border-indigo-500/30 hover:bg-indigo-500/40 hover:border-indigo-400 transition-colors" data-chunk-id="${chunkId}" data-idx="${idx}">[${num}]</sup>`;
    });

    return (
      <div 
        className="text-[var(--color-text-secondary)] text-sm leading-relaxed whitespace-pre-wrap"
        dangerouslySetInnerHTML={{ __html: html }}
        onMouseOver={(e) => {
          const target = e.target as HTMLElement;
          if (target.classList.contains('citation-marker')) {
            setHoveredCitationId(target.getAttribute('data-chunk-id'));
          }
        }}
        onMouseOut={(e) => {
          const target = e.target as HTMLElement;
          if (target.classList.contains('citation-marker')) {
            setHoveredCitationId(null);
          }
        }}
        onClick={(e) => {
          const target = (e.target as HTMLElement).closest('.citation-marker');
          if (target) {
            const idxStr = target.getAttribute('data-idx');
            if (idxStr !== null) {
              const citation = citations[parseInt(idxStr)];
              if (citation) handleCitationClick(citation);
            }
          }
        }}
      />
    );
  };

  // Map metadata document IDs to human readable names for the graph
  const activeMetadataWithNames = useMemo(() => {
    if (!activeMetadata) return null;
    const docMap = new Map(documents.map(d => [d.id, d.filename]));
    const metadata = { ...activeMetadata };
    
    if (metadata.retrieved_chunks) {
      metadata.retrieved_chunks = metadata.retrieved_chunks.map((c: any) => ({
        ...c,
        document_id: docMap.get(c.document_id) || c.document_id
      }));
    }
    return metadata;
  }, [activeMetadata, documents]);

  // ─── Ingestion callbacks ─────────────────────────────────
  const handleIngestionDocAdded = () => {
    fetchDocuments();
    fetchGraphData();
    setStatsRefreshToken(t => t + 1);
  };

  const handleIngestionDocDeleted = () => {
    fetchDocuments();
    fetchGraphData();
    setStatsRefreshToken(t => t + 1);
  };

  return (
    <div className="flex h-screen w-full bg-[var(--color-background)] overflow-hidden">
      
      {/* ─── Persistent Nav Rail ──────────────────────────────── */}
      <NavRail activeView={activeView} onViewChange={setActiveView} />

      {/* ─── Main Content Area ────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {activeView === "chat" && (
          <motion.div
            key="chat"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 flex overflow-hidden"
          >
            <ChatView
              chatSessions={chatSessions}
              activeSessionId={activeSessionId}
              onLoadSession={handleLoadSession}
              onDeleteSession={handleDeleteSession}
              onNewChat={handleNewChat}
              queryInput={queryInput}
              onQueryInputChange={setQueryInput}
              onQuerySubmit={handleQuerySubmit}
              mode={mode}
              activeQuery={activeQuery}
              currentStage={currentStage}
              activeMetadata={activeMetadata}
              answer={answer}
              citations={citations}
              hoveredCitationId={hoveredCitationId}
              onHoveredCitationIdChange={setHoveredCitationId}
              onCitationClick={handleCitationClick}
              renderAnswerWithCitations={renderAnswerWithCitations}
              documents={documents}
            />
          </motion.div>
        )}

        {activeView === "knowledge" && (
          <motion.div
            key="knowledge"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 flex overflow-hidden"
          >
            <KnowledgeBaseView
              fullGraphData={fullGraphData}
              metadata={activeMetadataWithNames}
              graphViewMode={graphViewMode}
              hoveredCitationId={hoveredCitationId}
              onGraphViewModeChange={setGraphViewMode}
              onRefreshGraph={fetchGraphData}
            />
          </motion.div>
        )}

        {activeView === "ingestion" && (
          <motion.div
            key="ingestion"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 flex overflow-hidden"
          >
            <IngestionView
              documents={documents}
              onDocumentAdded={handleIngestionDocAdded}
              onDocumentDeleted={handleIngestionDocDeleted}
            />
          </motion.div>
        )}

        {activeView === "overview" && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 flex overflow-hidden"
          >
            <OverviewView refreshToken={statsRefreshToken} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Citation Source Preview Modal ────────────────────── */}
      <AnimatePresence>
        {activeCitationPreview && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-8"
            onClick={() => setActiveCitationPreview(null)}
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="w-full max-w-3xl max-h-[75vh] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="h-12 border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)] flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-2 text-[var(--color-text-primary)]">
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                  <span className="text-sm font-semibold tracking-wide">Source Context</span>
                  <span className="text-[10px] font-mono text-[var(--color-text-muted)] bg-[var(--color-surface)] px-2 py-0.5 rounded border border-[var(--color-border)] ml-2">
                    Page {activeCitationPreview.page_index + 1}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button 
                    onClick={handleOpenFullDocument}
                    className="px-3 py-1.5 rounded-md text-xs font-medium text-indigo-400 bg-indigo-500/10 border border-indigo-500/30 hover:bg-indigo-500/20 transition-colors"
                  >
                    Open Full Document
                  </button>
                  <button 
                    onClick={() => setActiveCitationPreview(null)}
                    className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border)] transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {/* Modal Body */}
              <div className="flex-1 overflow-y-auto p-6">
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed whitespace-pre-wrap">
                  {activeCitationPreview.source_text}
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Document Viewer Modal ────────────────────── */}
      <AnimatePresence>
        {activeDocViewer && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-8"
            onClick={() => setActiveDocViewer(null)}
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="w-full max-w-5xl h-[85vh] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="h-12 border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)] flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-4 text-[var(--color-text-primary)]">
                  <a 
                    href={activeDocViewer.url} 
                    download={activeDocViewer.filename}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download File
                  </a>
                  
                  <div className="flex items-center gap-2 border-l border-[var(--color-border)] pl-4">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm font-semibold tracking-wide truncate max-w-[300px]">
                      {activeDocViewer.filename}
                    </span>
                  </div>
                </div>
                <button 
                  onClick={() => setActiveDocViewer(null)}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-border)] transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              
              {/* Modal Body */}
              <div className="flex-1 bg-[#2b2b2b] flex items-center justify-center relative">
                {activeDocViewer.isPdf ? (
                  <iframe 
                    src={activeDocViewer.url} 
                    className="w-full h-full border-none bg-white"
                    title="Document Viewer"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center text-center p-8">
                    <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center mb-4 shadow-lg">
                      <FileText className="w-8 h-8 text-[var(--color-text-muted)]" />
                    </div>
                    <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">Native Preview Not Supported</h3>
                    <p className="text-sm text-[var(--color-text-secondary)] max-w-md mx-auto mb-6 leading-relaxed">
                      This file format ({activeDocViewer.filename.split('.').pop()?.toUpperCase()}) cannot be displayed natively inside the browser.
                    </p>
                    <a 
                      href={activeDocViewer.url} 
                      download={activeDocViewer.filename}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-indigo-500/15 border border-indigo-500/40 text-indigo-400 hover:bg-indigo-500/25 hover:border-indigo-400 transition-all"
                    >
                      <Download className="w-4 h-4" />
                      Download {activeDocViewer.filename}
                    </a>
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
