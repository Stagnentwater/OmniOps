"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { ApiClient } from "@/services/api";
import { RetrievalGraph, GraphData } from "@/components/RetrievalGraph";
import { RetrievalStepper } from "@/components/RetrievalStepper";
import { IngestionWorkspace } from "@/components/IngestionWorkspace";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { 
  Terminal, Search, Database, Share2, 
  Settings, User, Code2, Globe, FileText, X, BookOpen, Download
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function UnifiedPage() {
  // ─── Global State ─────────────────────────────────────────
  const [documents, setDocuments] = useState<any[]>([]);
  const [fullGraphData, setFullGraphData] = useState<GraphData | null>(null);
  const [statsRefreshToken, setStatsRefreshToken] = useState(0);
  
  // ─── Interaction State ────────────────────────────────────
  const [graphViewMode, setGraphViewMode] = useState<"global" | "retrieval">("global");
  const [activeDocViewer, setActiveDocViewer] = useState<{url: string, isPdf: boolean, filename: string} | null>(null);
  const [activeCitationPreview, setActiveCitationPreview] = useState<{source_text: string, document_id: string, page_index: number, chunk_id: string} | null>(null);
  const [hoveredCitationId, setHoveredCitationId] = useState<string | null>(null);

  // ─── View Modes (Left Panel) ──────────────────────────────
  const [mode, setMode] = useState<"idle" | "ingesting" | "querying" | "answered">("idle");
  const [idleTab, setIdleTab] = useState<"ingestion" | "history">("history");
  
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
    setGraphViewMode("retrieval"); // Enter retrieval mode immediately

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
          // As progressive metadata streams in, update activeMetadata
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
        setActiveMetadata(null); // Metadata isn't persisted in standard chat msgs
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

  // ─── Citation & Document Viewing ────────────────────────
  const handleCitationClick = async (citation: any) => {
    // Show a source text preview panel with the citation's text
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
      
      // Close the preview panel and open the full document viewer
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
    
    // Replace citation markers like [1], [2], or [Context #1] with interactive span elements
    html = html.replace(/\[(?:Context\s*#)?(\d+)\]/gi, (match, num) => {
      const idx = parseInt(num) - 1;
      const citation = citations[idx];
      // If it's a hallucinated/invalid citation (because context is empty), just remove it from the UI
      if (!citation) return "";
      
      const chunkId = citation.chunk_id;
      // We encode the chunk ID in the data attribute and let event delegation handle interaction
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

  // Map metadata document IDs to human readable names for the graph empty state
  // We attach this directly to activeMetadata so RetrievalGraph can use it.
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

  return (
    <div className="flex h-screen w-full bg-[var(--color-background)] overflow-hidden">
      
      {/* ─── Column 1: System Status ────────────────────────────── */}
      <SystemStatusPanel refreshToken={statsRefreshToken} />

      {/* ─── Column 2: Workspace ────────────────────────────── */}
      <div className="w-[32.5%] flex flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] relative z-10 shadow-2xl shrink-0">
        
        {/* Header */}
        <div className="h-14 border-b border-[var(--color-border)] flex items-center px-5 gap-3 shrink-0 bg-[var(--color-surface-elevated)]/50">
          <div className="w-6 h-6 rounded-md bg-indigo-500/20 border border-indigo-500/50 flex items-center justify-center">
            <Terminal className="w-3.5 h-3.5 text-indigo-400" />
          </div>
          <span className="font-bold text-sm tracking-wide text-[var(--color-text-primary)]">OMNIOPS V3</span>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text-muted)] ml-auto">
            WORKSPACE
          </span>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-5 flex flex-col gap-6">
          
          <AnimatePresence mode="wait">
            {mode === "idle" && (
              <motion.div 
                key="idle"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex-1"
              >
                <div className="flex items-center gap-4 border-b border-[var(--color-border)] pb-3 mb-5">
                  <button 
                    onClick={() => setIdleTab("history")}
                    className={`text-sm font-semibold transition-colors ${idleTab === "history" ? "text-indigo-400" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"}`}
                  >
                    Query History
                  </button>
                  <button 
                    onClick={() => setIdleTab("ingestion")}
                    className={`text-sm font-semibold transition-colors ${idleTab === "ingestion" ? "text-indigo-400" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"}`}
                  >
                    Knowledge Ingestion
                  </button>
                </div>

                {idleTab === "ingestion" ? (
                  <>
                    <div className="mb-6">
                      <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">Knowledge Ingestion</h2>
                      <p className="text-xs text-[var(--color-text-muted)]">Upload technical documents to synthesize the industrial graph.</p>
                    </div>
                    <IngestionWorkspace 
                      documents={documents}
                      onDocumentAdded={() => {
                        fetchDocuments();
                        fetchGraphData();
                        setStatsRefreshToken(t => t + 1);
                      }}
                      onDocumentDeleted={() => {
                        fetchDocuments();
                        fetchGraphData();
                        setStatsRefreshToken(t => t + 1);
                      }}
                    />
                  </>
                ) : (
                  <div className="flex flex-col gap-3 flex-1 overflow-y-auto pr-2">
                    {chatSessions.length === 0 ? (
                      <div className="text-xs text-[var(--color-text-muted)] py-4 text-center bg-[var(--color-surface-elevated)] rounded-lg border border-[var(--color-border)] border-dashed">
                        No previous queries found.
                      </div>
                    ) : (
                      chatSessions.map(session => (
                        <div 
                          key={session.id} 
                          onClick={() => handleLoadSession(session.id)}
                          className="flex flex-col gap-1.5 p-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] hover:border-indigo-500/50 cursor-pointer transition-colors group relative"
                        >
                          <div className="flex items-start justify-between">
                            <span className="text-sm font-medium text-[var(--color-text-primary)] line-clamp-2 pr-8">{session.title}</span>
                            <button 
                              onClick={(e) => handleDeleteSession(session.id, e)}
                              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1.5 text-red-400/70 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-all"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                          <span className="text-[10px] text-[var(--color-text-muted)] font-mono">{new Date(session.created_at).toLocaleString()}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </motion.div>
            )}

            {(mode === "querying" || mode === "answered") && (
              <motion.div 
                key="query-active"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex-1 flex flex-col"
              >
                {/* Active Query Header */}
                <div className="p-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] mb-6 shadow-sm">
                  <div className="flex items-start gap-3">
                    <User className="w-4 h-4 text-[var(--color-text-muted)] mt-0.5" />
                    <p className="text-sm font-medium text-[var(--color-text-primary)] leading-relaxed">
                      {activeQuery}
                    </p>
                  </div>
                </div>

                {/* Pipeline Stepper */}
                <div className="mb-6">
                  <RetrievalStepper currentStage={currentStage} metadata={activeMetadata} />
                </div>

                {/* Answer Display */}
                {mode === "answered" && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="flex-1 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-xl p-5 shadow-sm"
                  >
                    <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[var(--color-border)]">
                      <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
                      <span className="text-xs font-bold tracking-wide uppercase text-[var(--color-text-primary)]">Synthesis Complete</span>
                    </div>
                    {renderAnswerWithCitations()}
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input Footer */}
        <div className="p-5 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
          <form onSubmit={handleQuerySubmit} className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)] pointer-events-none" />
            <input
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="Query industrial knowledge base..."
              disabled={mode === "querying"}
              className="w-full bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg pl-10 pr-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all disabled:opacity-50"
            />
          </form>
          
          {mode === "answered" && (
            <div className="mt-4 flex justify-center">
              <button
                onClick={() => {
                  setMode("idle");
                  setActiveQuery("");
                  setActiveMetadata(null);
                  setGraphViewMode("global");
                  setActiveSessionId(null);
                }}
                className="text-[10px] uppercase font-bold tracking-wider text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
              >
                Start New Query
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ─── Column 3: Knowledge Graph (35%) ────────────── */}
      <div className="w-[35%] flex-1 relative bg-[var(--color-surface)]">
        {/* Graph Modes Toggle (Top Left overlay on Graph) */}
        <AnimatePresence>
          {(mode === "querying" || mode === "answered") && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute top-4 left-4 z-20"
            >
              <div className="flex items-center p-1 bg-[var(--color-surface-elevated)]/80 backdrop-blur-md border border-[var(--color-border)] rounded-lg shadow-sm">
                <button
                  onClick={() => setGraphViewMode("global")}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    graphViewMode === "global" 
                      ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-sm border border-[var(--color-border)]" 
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  Global Network
                </button>
                <button
                  onClick={() => setGraphViewMode("retrieval")}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    graphViewMode === "retrieval" 
                      ? "bg-[var(--color-surface)] text-indigo-400 shadow-sm border border-[var(--color-border)]" 
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
                  }`}
                >
                  <Search className="w-3.5 h-3.5" />
                  Retrieval Context
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <RetrievalGraph 
          fullGraphData={fullGraphData}
          metadata={activeMetadataWithNames} 
          mode={graphViewMode}
          hoveredCitationId={hoveredCitationId}
          onRefresh={fetchGraphData}
        />
      </div>

      {/* ─── Citation Source Preview Panel ────────────────────── */}
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
                  {/* Option to download on the top left corner */}
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
