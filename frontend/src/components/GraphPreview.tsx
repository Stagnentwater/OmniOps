"use client";

import { useEffect, useState, useRef } from "react";
import dynamic from "next/dynamic";
import { ApiClient } from "@/services/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export function GraphPreview() {
  const [mounted, setMounted] = useState(false);
  const [graphData, setGraphData] = useState<{nodes: any[], links: any[]} | null>(null);

  useEffect(() => {
    setMounted(true);
    const fetchGraph = async () => {
      try {
        const data = await ApiClient.getKnowledgeGraph();
        
        // Transform backend response to react-force-graph format
        const nodes = data.nodes.slice(0, 30).map((n: any) => ({
          id: n.entity_id,
          name: n.canonical_name || n.entity_id,
          val: n.entity_type === "Document" ? 4 : 3,
          color: n.entity_type === "Document" ? "#0f172a" : // slate-900
                 n.entity_type === "Asset" ? "#475569" :    // slate-600
                 n.entity_type === "Location" ? "#64748b" : // slate-500
                 "#94a3b8"                           // slate-400
        }));
        
        const nodeIds = new Set(nodes.map((n: any) => n.id));
        const links = data.edges
          .filter((e: any) => nodeIds.has(e.source_entity_id) && nodeIds.has(e.target_entity_id))
          .map((e: any) => ({
            source: e.source_entity_id,
            target: e.target_entity_id,
            label: e.relationship_type
          }));

        setGraphData({ nodes, links });
      } catch (err) {
        console.error("Failed to load graph preview", err);
      }
    };
    fetchGraph();
  }, []);

  if (!mounted || !graphData) return <div className="h-64 bg-slate-50 rounded-xl border border-slate-200 animate-pulse" />;

  return (
    <div className="h-64 bg-slate-50 rounded-xl border border-slate-200 overflow-hidden relative shadow-inner flex items-center justify-center">
      <div className="absolute inset-0 z-0">
        <ForceGraph2D
          graphData={graphData}
          width={600}
          height={300}
          nodeLabel="name"
          nodeColor="color"
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          enableZoomInteraction={false}
          enablePanInteraction={false}
          d3VelocityDecay={0.1}
          nodeRelSize={5}
        />
      </div>
      <div className="absolute bottom-3 right-3 bg-white/90 backdrop-blur-sm px-3 py-1 rounded-full text-[10px] font-bold tracking-wide shadow-sm text-slate-500 uppercase">
        Live Network Preview
      </div>
    </div>
  );
}
