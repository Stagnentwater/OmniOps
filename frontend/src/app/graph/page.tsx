"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";
import { ApiClient } from "@/services/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const ENTITY_COLORS: Record<string, string> = {
  "Document": "#34d399",
  "Asset": "#22d3ee",
  "Location": "#a78bfa",
  "Procedure": "#fb923c",
  "Component": "#60a5fa",
  "Safety": "#f472b6",
};

function getEntityColor(type: string): string {
  return ENTITY_COLORS[type] || "#64748b";
}

export default function GraphPage() {
  const [mounted, setMounted] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [graphData, setGraphData] = useState<{nodes: any[], links: any[]} | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setMounted(true);
    setDimensions({ width: window.innerWidth, height: window.innerHeight });
    const handleResize = () => setDimensions({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const data = await ApiClient.getKnowledgeGraph();
        const nodes = data.nodes.map((n: any) => ({
          id: n.entity_id,
          name: n.canonical_name || n.entity_id,
          val: 4,
          group: n.entity_type,
          color: getEntityColor(n.entity_type),
        }));
        const nodeIds = new Set(nodes.map((n: any) => n.id));
        const links = data.edges
          .filter((e: any) => nodeIds.has(e.source_entity_id) && nodeIds.has(e.target_entity_id))
          .map((e: any) => ({
            source: e.source_entity_id,
            target: e.target_entity_id,
            label: e.relationship_type,
          }));
        setGraphData({ nodes, links });
      } catch (err) {
        console.error("Failed to load graph", err);
      } finally {
        setLoading(false);
      }
    };
    fetchGraph();
  }, []);

  if (!mounted) return <div className="h-screen bg-[var(--color-surface)] dot-grid" />;

  return (
    <div className="h-screen bg-[var(--color-surface)] dot-grid relative">
      {/* Back link */}
      <a href="/" className="absolute top-4 left-4 z-20 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--color-surface-elevated)]/80 backdrop-blur-sm border border-[var(--color-border)] text-xs font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors" style={{ fontFamily: 'var(--font-mono)' }}>
        ← OmniOps
      </a>

      {/* Title */}
      <div className="absolute top-4 right-4 z-20 px-3 py-1.5 rounded-lg bg-[var(--color-surface-elevated)]/80 backdrop-blur-sm border border-[var(--color-border)]">
        <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-widest" style={{ fontFamily: 'var(--font-mono)' }}>
          Full Knowledge Graph
        </span>
      </div>

      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="w-6 h-6 text-indigo-500 animate-spin" />
        </div>
      ) : graphData && graphData.nodes.length > 0 ? (
        <>
          <ForceGraph2D
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            nodeLabel="name"
            nodeColor="color"
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            nodeRelSize={5}
            d3VelocityDecay={0.3}
            backgroundColor="transparent"
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const size = node.val || 4;
              ctx.beginPath();
              ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
              ctx.fillStyle = node.color;
              ctx.globalAlpha = 0.85;
              ctx.fill();
              ctx.globalAlpha = 1;

              const fontSize = Math.max(10 / globalScale, 2.5);
              ctx.font = `600 ${fontSize}px 'JetBrains Mono', monospace`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#c4c4d4';
              ctx.fillText(node.name, node.x, node.y + size + fontSize + 1);
            }}
            linkCanvasObjectMode={() => 'replace'}
            linkCanvasObject={(link: any, ctx: CanvasRenderingContext2D) => {
              const start = link.source;
              const end = link.target;
              if (!start || !end || typeof start.x !== 'number') return;
              ctx.beginPath();
              ctx.moveTo(start.x, start.y);
              ctx.lineTo(end.x, end.y);
              ctx.strokeStyle = 'rgba(100, 100, 130, 0.25)';
              ctx.lineWidth = 0.8;
              ctx.stroke();
            }}
          />

          {/* Legend */}
          <div className="absolute bottom-4 left-4 z-20 flex flex-wrap gap-2">
            {Object.entries(ENTITY_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--color-surface)]/80 backdrop-blur-sm border border-[var(--color-border)]">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[10px] font-medium text-[var(--color-text-secondary)]" style={{ fontFamily: 'var(--font-mono)' }}>{type}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-[var(--color-text-muted)]">
          <p className="text-sm">No graph data. Upload documents first.</p>
        </div>
      )}
    </div>
  );
}
