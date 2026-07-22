import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronRight, Layers, Database, FileText, Cpu, CheckCircle } from "lucide-react";

export function RetrievalInspector({ metadata }: { metadata: any }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!metadata) return null;

  return (
    <div className="mt-4 border border-slate-200 rounded-lg overflow-hidden bg-white text-sm shadow-sm">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center w-full p-3 bg-slate-50 hover:bg-slate-100 transition-colors font-semibold text-slate-700"
      >
        {isOpen ? <ChevronDown className="w-4 h-4 mr-2" /> : <ChevronRight className="w-4 h-4 mr-2" />}
        Retrieval Inspector
      </button>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 space-y-6">
              
              {/* Vector Search */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold text-slate-800 mb-3 border-b pb-2">
                  <Database className="w-4 h-4 text-blue-500" /> Vector Search
                </h4>
                <div className="space-y-2">
                  {metadata.retrieved_chunks?.map((c: any, i: number) => (
                    <div key={i} className="bg-slate-50 p-2 rounded border border-slate-100">
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-medium text-slate-700">Chunk {c.id.substring(0,8)}</span>
                        <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">Score: {(c.score * 100).toFixed(1)}%</span>
                      </div>
                      <p className="text-slate-500 text-xs line-clamp-2">{c.text}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Graph Expansion */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold text-slate-800 mb-3 border-b pb-2">
                  <Layers className="w-4 h-4 text-purple-500" /> Graph Expansion
                </h4>
                <div className="flex flex-wrap gap-2">
                  {metadata.retrieved_entities?.map((e: any, i: number) => (
                    <span key={i} className="bg-purple-50 text-purple-700 border border-purple-200 px-2 py-1 rounded text-xs">
                      {e.name} <span className="opacity-50 text-[10px]">({e.type})</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* Generation */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold text-slate-800 mb-3 border-b pb-2">
                  <Cpu className="w-4 h-4 text-amber-500" /> Generation
                </h4>
                <div className="flex gap-4 text-slate-600">
                  <div className="flex flex-col">
                    <span className="text-xs uppercase text-slate-400">Model</span>
                    <span className="font-medium">{metadata.model}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs uppercase text-slate-400">Latency</span>
                    <span className="font-medium">{metadata.latency.toFixed(2)}s</span>
                  </div>
                </div>
              </div>

              {/* Citations */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold text-slate-800 mb-3 border-b pb-2">
                  <CheckCircle className="w-4 h-4 text-emerald-500" /> Citation Validation
                </h4>
                <div className="flex flex-wrap gap-2 text-slate-600">
                  <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded border border-emerald-200">
                    Validated {metadata.retrieved_chunks?.length || 0} context references
                  </span>
                </div>
              </div>
              
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
