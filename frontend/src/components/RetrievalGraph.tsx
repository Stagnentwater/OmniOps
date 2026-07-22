"use client";

import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { LocateFixed, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const ENTITY_COLORS: Record<string, string> = {
  "Document": "#34d399",   // emerald
  "Asset": "#22d3ee",      // cyan
  "Location": "#a78bfa",   // violet
  "Procedure": "#fb923c",  // orange
  "Component": "#60a5fa",  // blue
  "Safety": "#f472b6",     // pink
};
const DEFAULT_COLOR = "#64748b"; // slate-500
function getEntityColor(type: string): string {
  return ENTITY_COLORS[type] || DEFAULT_COLOR;
}

// ─── Interfaces ──────────────────────────────────────────
export interface GraphNode {
  id: string;
  name: string;
  group: string;
  val: number;
  color: string;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}
export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
}
export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface RetrievalGraphProps {
  fullGraphData: GraphData | null;
  metadata: any | null;
  mode: "global" | "retrieval";
  hoveredCitationId?: string | null;
  onNodeHover?: (nodeId: string | null) => void;
  onRefresh?: () => void;
}

// ─── Math Utilities ──────────────────────────────────────
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function RetrievalGraph({ 
  fullGraphData,
  metadata,
  mode,
  hoveredCitationId,
  onNodeHover,
  onRefresh
}: RetrievalGraphProps) {
  
  // ─── Refs & State ─────────────────────────────────────────
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<any | null>(null);
  
  // Track simulation stability
  const [isStable, setIsStable] = useState(false);
  
  // We keep a single instance of the graph data structure for physics stability.
  const stableGraphData = useMemo(() => {
    if (!fullGraphData) return { nodes: [], links: [] };
    // Clone structurally once. Subsequent renders reuse these objects.
    return {
      nodes: fullGraphData.nodes.map(n => ({ ...n })),
      links: fullGraphData.links.map(l => ({ ...l }))
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullGraphData]);

  useEffect(() => { setMounted(true); }, []);

  // ─── Presentation Layer Computation ───────────────────────
  // We compute visibility states mathematically without altering graphData.
  const presentationState = useMemo(() => {
    const isRetrieval = mode === "retrieval";
    
    // Extracted directly retrieved entities and expanded entities from metadata
    const directlyRetrieved = new Set<string>();
    const expandedEntities = new Set<string>();
    const retrievedLinks = new Set<string>(); // "source_target"
    const retrievedDocuments = new Set<string>();
    let graphEntitiesFound = false;

    if (metadata) {
      if (metadata.retrieved_entities) {
        metadata.retrieved_entities.forEach((e: any) => {
          directlyRetrieved.add(e.id);
          graphEntitiesFound = true;
        });
      }
      if (metadata.retrieved_relationships) {
        metadata.retrieved_relationships.forEach((r: any) => {
          retrievedLinks.add(`${r.source}_${r.target}`);
          // Implicitly consider relationship endpoints as expanded if not already direct
          expandedEntities.add(r.source);
          expandedEntities.add(r.target);
        });
      }
      if (metadata.retrieved_chunks) {
        metadata.retrieved_chunks.forEach((c: any) => {
          if (c.document_id) {
            retrievedDocuments.add(c.document_name || c.document_id);
            directlyRetrieved.add(c.document_id); // Ensure the doc is highlighted
          }
        });
      }
    }

    // Determine hover/citation context
    const citationHighlightNodes = new Set<string>();
    if (hoveredCitationId && metadata?.retrieved_chunks) {
      const chunk = metadata.retrieved_chunks.find((c: any) => c.id === hoveredCitationId);
      if (chunk && chunk.document_id) {
        citationHighlightNodes.add(chunk.document_id);
        // Add all entities to the citation highlight context
        (metadata.retrieved_entities || []).forEach((e: any) => citationHighlightNodes.add(e.id));
      }
    }
    
    // Node hover context
    const hoverHighlightNodes = new Set<string>();
    if (hoveredNode) {
      hoverHighlightNodes.add(hoveredNode);
      stableGraphData.links.forEach((l: any) => {
        const sid = l.source.id || l.source;
        const tid = l.target.id || l.target;
        if (sid === hoveredNode || tid === hoveredNode) {
          hoverHighlightNodes.add(sid);
          hoverHighlightNodes.add(tid);
        }
      });
    }

    const hasHoverFocus = hoverHighlightNodes.size > 0 || citationHighlightNodes.size > 0;
    
    return {
      isRetrieval,
      directlyRetrieved,
      expandedEntities,
      retrievedLinks,
      hasHoverFocus,
      hoverHighlightNodes,
      citationHighlightNodes,
      retrievedDocuments,
      graphEntitiesFound,
      hoveredLink
    };
  }, [mode, metadata, hoveredCitationId, hoveredNode, hoveredLink, stableGraphData]);

  // ─── Camera Choreography ────────────────────────────────
  const fitCameraToSelection = useCallback((nodeIds: Set<string>) => {
    if (!graphRef.current || nodeIds.size === 0) return;
    
    const nodes = stableGraphData.nodes.filter(n => nodeIds.has(n.id) && typeof n.x === 'number' && typeof n.y === 'number');
    if (nodes.length === 0) return;

    if (nodes.length === 1) {
      // Don't isolate too aggressively, zoom with padding
      graphRef.current.centerAt(nodes[0].x, nodes[0].y, 600);
      graphRef.current.zoom(2, 600);
      return;
    }

    // Compute bounding box
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    nodes.forEach(n => {
      minX = Math.min(minX, n.x!);
      maxX = Math.max(maxX, n.x!);
      minY = Math.min(minY, n.y!);
      maxY = Math.max(maxY, n.y!);
    });

    const padding = 100;
    const width = maxX - minX + padding * 2;
    const height = maxY - minY + padding * 2;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;

    const graphWidth = containerRef.current?.clientWidth || 800;
    const graphHeight = containerRef.current?.clientHeight || 600;
    
    // Constrain zoom to comfortable bounds (e.g. 0.5 to 2.5)
    let zoom = Math.min(graphWidth / width, graphHeight / height);
    zoom = Math.max(0.5, Math.min(zoom, 2.5));

    graphRef.current.centerAt(cx, cy, 600);
    graphRef.current.zoom(zoom, 600);
  }, [stableGraphData.nodes]);

  const fitCameraToGlobal = useCallback(() => {
    if (graphRef.current) {
      const el = containerRef.current;
      if (el && el.clientWidth > 100 && el.clientHeight > 100) {
        graphRef.current.zoomToFit(600, 40); // 40px padding, 600ms transition
      } else {
        // Retry if container hasn't painted yet
        setTimeout(() => {
          if (graphRef.current) graphRef.current.zoomToFit(600, 40);
        }, 200);
      }
    }
  }, []);

  // Effect to handle mode switching camera behavior
  useEffect(() => {
    if (!isStable || !graphRef.current) return;
    
    if (mode === "global") {
      fitCameraToGlobal();
    } else if (mode === "retrieval") {
      // Extract directly from metadata to avoid depending on the volatile presentationState
      const focusIds = new Set<string>();
      if (metadata?.retrieved_entities) {
        metadata.retrieved_entities.forEach((e: any) => focusIds.add(e.id));
      }
      if (metadata?.retrieved_relationships) {
        metadata.retrieved_relationships.forEach((r: any) => {
          focusIds.add(r.source);
          focusIds.add(r.target);
        });
      }
      if (metadata?.retrieved_chunks) {
        metadata.retrieved_chunks.forEach((c: any) => {
          if (c.document_id) focusIds.add(c.document_id);
        });
      }
      
      if (focusIds.size > 0) {
        fitCameraToSelection(focusIds);
      }
    }
  }, [mode, isStable, metadata, fitCameraToGlobal, fitCameraToSelection]);

  // Handle citation hover camera movement
  useEffect(() => {
    if (!isStable || !graphRef.current || mode !== "retrieval") return;
    
    const citationHighlightNodes = new Set<string>();
    if (hoveredCitationId && metadata?.retrieved_chunks) {
      const chunk = metadata.retrieved_chunks.find((c: any) => c.id === hoveredCitationId);
      if (chunk && chunk.document_id) {
        citationHighlightNodes.add(chunk.document_id);
        (metadata.retrieved_entities || []).forEach((e: any) => citationHighlightNodes.add(e.id));
      }
    }

    if (hoveredCitationId && citationHighlightNodes.size > 0) {
      fitCameraToSelection(citationHighlightNodes);
    }
  }, [hoveredCitationId, isStable, mode, metadata, fitCameraToSelection]);


  // ─── Rendering Pipeline ──────────────────────────────────
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const { 
      isRetrieval, directlyRetrieved, expandedEntities, 
      hasHoverFocus, hoverHighlightNodes, citationHighlightNodes 
    } = presentationState;

    const isHoverFocused = hasHoverFocus && (hoverHighlightNodes.has(node.id) || citationHighlightNodes.has(node.id));
    const isDirect = directlyRetrieved.has(node.id);
    const isExpanded = expandedEntities.has(node.id);
    const isInRetrievalScope = isDirect || isExpanded;

    // Determine Opacity
    let targetAlpha = 0.85; // Global mode default
    if (isRetrieval) {
      targetAlpha = isInRetrievalScope ? 1 : 0.25;
    }
    if (hasHoverFocus) {
      targetAlpha = isHoverFocused ? 1 : 0.1;
    }
    
    // Smooth transition logic could be implemented here manually using a tick/timestamp, 
    // but for performance, we instantly swap alpha target and rely on React renders for state changes.
    const alpha = targetAlpha;

    const size = (node.val || 3.5);
    
    // Highlight Glow (Citation or Hover)
    if (isHoverFocused) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI, false);
      ctx.fillStyle = `${node.color}25`; // ~15% opacity glow
      ctx.fill();
    }

    // Main circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color || DEFAULT_COLOR;
    ctx.globalAlpha = alpha;
    ctx.fill();
    
    // Outlines for Explainability
    if (isRetrieval && isInRetrievalScope) {
      ctx.strokeStyle = node.color;
      ctx.lineWidth = isDirect ? 2 / globalScale : 1 / globalScale;
      ctx.globalAlpha = isDirect ? 1 : 0.7;
      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Labels
    const fontSize = Math.max(10 / globalScale, 2.5);
    // Hide text if extremely zoomed out or deeply dimmed
    if (globalScale > 0.8 && alpha > 0.2) {
      ctx.font = `500 ${fontSize}px 'JetBrains Mono', monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = `rgba(228, 228, 237, ${alpha})`; // text-primary with computed alpha
      ctx.fillText(node.name, node.x, node.y + size + fontSize + 1);
    }
  }, [presentationState]);

  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D) => {
    const { 
      isRetrieval, retrievedLinks, 
      hasHoverFocus, hoverHighlightNodes, citationHighlightNodes 
    } = presentationState;

    const sid = link.source.id || link.source;
    const tid = link.target.id || link.target;
    
    const isHoverFocused = hasHoverFocus && (
      (hoverHighlightNodes.has(sid) && hoverHighlightNodes.has(tid)) ||
      (citationHighlightNodes.has(sid) && citationHighlightNodes.has(tid))
    );
    
    const isRetrievedLink = retrievedLinks.has(`${sid}_${tid}`) || retrievedLinks.has(`${tid}_${sid}`);

    // Opacity
    let alpha = 0.3; // Global default
    let width = 0.8;
    let strokeStyle = 'rgba(100, 100, 130, 0.4)';

    if (isRetrieval) {
      if (isRetrievedLink) {
        alpha = 0.8;
        width = 1.5;
        strokeStyle = 'rgba(129, 140, 248, 0.8)'; // indigo-400
      } else {
        alpha = 0.15; // heavily dimmed
        width = 0.5;
      }
    }

    if (hasHoverFocus) {
      if (isHoverFocused) {
        alpha = 1;
        width = 2.0;
        strokeStyle = 'rgba(129, 140, 248, 1)'; 
      } else {
        alpha = 0.05;
      }
    }

    const start = link.source;
    const end = link.target;
    if (!start || !end || typeof start.x !== 'number') return;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = strokeStyle;
    ctx.lineWidth = width;
    ctx.stroke();
    
    // Draw label if hovered
    if (hoveredLink && link === hoveredLink && link.label) {
      const midX = (start.x + end.x) / 2;
      const midY = (start.y + end.y) / 2;
      const fontSize = 4;
      ctx.font = `500 ${fontSize}px 'JetBrains Mono', monospace`;
      
      const textWidth = ctx.measureText(link.label).width;
      const bckgDimensions = [textWidth + 2, fontSize + 2];

      ctx.fillStyle = 'rgba(43, 43, 54, 0.9)'; // background color (surface)
      ctx.fillRect(midX - bckgDimensions[0] / 2, midY - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);

      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(129, 140, 248, 1)'; // indigo-400
      ctx.fillText(link.label, midX, midY);
    }
    
    ctx.globalAlpha = 1;
  }, [presentationState]);

  // ─── Rendering Fallbacks ─────────────────────────────────
  if (!mounted) return <div className="w-full h-full bg-[var(--color-surface)] dot-grid" />;
  
  if (stableGraphData.nodes.length === 0) return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-[var(--color-surface)] dot-grid">
      <div className="flex flex-col items-center gap-3 opacity-40">
        <div className="w-16 h-16 rounded-2xl border border-dashed border-[var(--color-border)] flex items-center justify-center">
          <LocateFixed className="w-6 h-6 text-[var(--color-text-muted)]" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-[var(--color-text-muted)]">Knowledge Graph</p>
          <p className="text-xs text-[var(--color-text-muted)] mt-1 opacity-60">Upload documents to build the global graph.</p>
        </div>
      </div>
    </div>
  );

  // Identify empty retrieval state
  const isEmptyRetrieval = mode === "retrieval" && 
                           !presentationState.graphEntitiesFound && 
                           presentationState.retrievedDocuments.size > 0;

  return (
    <div ref={containerRef} className="w-full h-full bg-[var(--color-surface)] dot-grid relative overflow-hidden">
      
      {/* Empty Retrieval State Overlay */}
      <AnimatePresence>
        {isEmptyRetrieval && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 w-[400px]"
          >
            <div className="bg-[var(--color-surface-elevated)]/90 backdrop-blur-md border border-[var(--color-border)] rounded-xl p-5 shadow-2xl">
              <div className="flex items-center gap-3 mb-3 text-[var(--color-text-primary)]">
                <LocateFixed className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-semibold">Semantic Context Applied</h3>
              </div>
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed mb-4">
                Graph expansion found no connected entities. The answer was generated from semantic retrieval over the following documents:
              </p>
              <ul className="text-xs text-[var(--color-text-secondary)] space-y-1.5" style={{ fontFamily: 'var(--font-mono)' }}>
                {Array.from(presentationState.retrievedDocuments).map(docId => (
                  <li key={docId} className="flex items-start gap-2">
                    <span className="text-indigo-500/50">•</span> 
                    <span className="truncate">{docId}</span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <ForceGraph2D
        ref={graphRef}
        graphData={stableGraphData}
        nodeCanvasObject={paintNode}
        linkCanvasObjectMode={() => 'replace'}
        linkCanvasObject={paintLink}
        d3VelocityDecay={0.25}
        d3AlphaDecay={0.05} // allows it to cool down and stabilize
        onEngineStop={() => {
          if (!isStable) {
            setIsStable(true);
            // Once stable, lock the coordinates to prevent physics restart
            stableGraphData.nodes.forEach(n => {
              n.fx = n.x;
              n.fy = n.y;
            });
            // Frame it cleanly after layout paints
            setTimeout(() => {
              fitCameraToGlobal();
            }, 300);
          }
        }}
        onNodeHover={(node: any) => {
          setHoveredNode(node ? node.id : null);
          if (onNodeHover) onNodeHover(node ? node.id : null);
        }}
        onLinkHover={(link: any) => setHoveredLink(link)}
        linkHoverPrecision={4}
        cooldownTicks={150} // Let it run physics for 150 ticks then stop
        backgroundColor="transparent"
      />

      {/* UI Controls Overlay */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col gap-2">
        {onRefresh && (
          <button 
            onClick={onRefresh}
            className="bg-[var(--color-surface-elevated)]/80 backdrop-blur border border-[var(--color-border)] hover:border-indigo-500/50 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] p-2 rounded-lg shadow-sm transition-colors flex items-center justify-center group"
            title="Refresh Graph Data"
          >
            <RefreshCw className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" />
          </button>
        )}
        <button 
          onClick={fitCameraToGlobal}
          className="bg-[var(--color-surface-elevated)]/80 backdrop-blur border border-[var(--color-border)] hover:border-indigo-500/50 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] p-2 rounded-lg shadow-sm transition-colors flex items-center justify-center group"
          title="Reset View"
        >
          <LocateFixed className="w-4 h-4 group-hover:scale-110 transition-transform duration-200" />
        </button>
      </div>

      {/* Entity Type Legend */}
      <div className="absolute bottom-4 left-4 z-20 flex flex-wrap gap-2 pointer-events-none">
        {Object.keys(ENTITY_COLORS).map(type => (
          <div key={type} className="flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--color-surface-elevated)]/60 backdrop-blur-sm border border-[var(--color-border)]">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getEntityColor(type) }} />
            <span className="text-[10px] font-medium text-[var(--color-text-secondary)]" style={{ fontFamily: 'var(--font-mono)' }}>
              {type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
