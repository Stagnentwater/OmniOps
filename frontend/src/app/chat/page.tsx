"use client";

import { useState } from "react";
import { ApiClient } from "@/services/api";

type Citation = {
  document_id: string;
  chunk_id: string;
  page_index: number;
  source_text: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  loading?: boolean;
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Document Viewer State
  const [activeDocUrl, setActiveDocUrl] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const query = input;
    setInput("");
    setIsLoading(true);

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: query };
    const loadingMsg: Message = { id: (Date.now() + 1).toString(), role: "assistant", content: "Reasoning over knowledge graph...", loading: true };
    
    setMessages(prev => [...prev, userMsg, loadingMsg]);

    try {
      const res = await ApiClient.query(query);
      setMessages(prev => prev.map(m => 
        m.id === loadingMsg.id 
          ? { ...m, content: res.answer, citations: res.citations, loading: false } 
          : m
      ));
    } catch (err) {
      setMessages(prev => prev.map(m => 
        m.id === loadingMsg.id 
          ? { ...m, content: "Error: Failed to connect to OmniOps backend.", loading: false } 
          : m
      ));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCitationClick = async (citation: Citation) => {
    try {
      const url = await ApiClient.getDocumentContentUrl(citation.document_id);
      // Append #page= to navigate the native browser PDF viewer directly to the page.
      // Note: page_index is usually 0-indexed in our backend, PDF viewer is 1-indexed.
      setActiveDocUrl(`${url}#page=${citation.page_index + 1}`);
    } catch (err) {
      console.error("Failed to load document", err);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      {/* Chat Window */}
      <div className="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-slate-400">
              Ask a question about your ingested documents.
            </div>
          ) : (
            messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl px-5 py-3.5 ${
                  msg.role === "user" 
                    ? "bg-blue-600 text-white shadow-md" 
                    : "bg-slate-100 text-slate-800"
                }`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  
                  {/* Citations block */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-300">
                      <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Sources</h4>
                      <div className="flex flex-wrap gap-2">
                        {msg.citations.map((c, i) => (
                          <button 
                            key={i}
                            onClick={() => handleCitationClick(c)}
                            className="text-xs bg-white border border-slate-300 hover:border-blue-400 hover:text-blue-600 px-2 py-1 rounded transition-colors"
                          >
                            [Context #{i + 1}] Page {c.page_index + 1}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {msg.loading && <span className="inline-block mt-2 h-1.5 w-1.5 bg-slate-400 rounded-full animate-ping" />}
                </div>
              </div>
            ))
          )}
        </div>
        
        {/* Input area */}
        <div className="p-4 border-t border-slate-100 bg-slate-50">
          <form onSubmit={handleSubmit} className="flex gap-4">
            <input 
              type="text" 
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask OmniOps..."
              className="flex-1 rounded-full border border-slate-300 px-6 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
              disabled={isLoading}
            />
            <button 
              type="submit"
              disabled={isLoading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-full px-8 py-3 font-medium transition-colors shadow-sm"
            >
              Send
            </button>
          </form>
        </div>
      </div>

      {/* Document Viewer Sidebar */}
      <div className="w-[45%] bg-slate-900 rounded-xl shadow-lg overflow-hidden border border-slate-800 flex flex-col">
        {activeDocUrl ? (
          <iframe 
            src={activeDocUrl} 
            className="w-full h-full border-none"
            title="Document Viewer"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-slate-500 p-8 text-center">
            <p>Click a citation in the chat to view the source document.</p>
          </div>
        )}
      </div>
    </div>
  );
}
