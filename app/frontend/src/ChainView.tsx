import { useCallback, useMemo, useRef } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { ChainView as ChainData } from "./api";
import { ChainFlowNode } from "./ChainFlowNode";
import { chainLayoutToFlow } from "./chainFlow";
import { chainLayoutFromElements } from "./chainGraph";

const nodeTypes = { chainBlock: ChainFlowNode };

type Props = {
  chain: ChainData | null;
  loading: boolean;
  detailLoading: boolean;
  error: string | null;
  onRefresh: () => void;
};

function ChainFlowCanvas({
  layout,
  detailLoading,
  loading,
  patchKey,
}: {
  layout: ReturnType<typeof chainLayoutFromElements>;
  detailLoading: boolean;
  loading: boolean;
  patchKey: string;
}) {
  const graph = useMemo(() => chainLayoutToFlow(layout, detailLoading), [layout, detailLoading]);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const onInit = useCallback((instance: {
    setViewport?: (viewport: { x: number; y: number; zoom: number }, opts?: { duration?: number }) => void;
    getViewport?: () => { x: number; y: number; zoom: number };
  }) => {
    if (graph.nodes.length === 0) {
      return;
    }
    // Default zoom should be readable even if it requires panning.
    // Start panned all the way left so the input side is visible.
    const DEFAULT_ZOOM = 1.25;
    const LEFT_PAD = 28;
    const NODE_H = 72;

    const minX = Math.min(...graph.nodes.map((node) => node.position.x));
    const minY = Math.min(...graph.nodes.map((node) => node.position.y));
    const maxY = Math.max(...graph.nodes.map((node) => node.position.y));

    const wrapHeight = wrapRef.current?.getBoundingClientRect().height ?? 0;
    // Node positions are top-left; include node height so we center the rendered boxes.
    const graphMidY = (minY + (maxY + NODE_H)) / 2;
    const viewMidY = wrapHeight > 0 ? wrapHeight / 2 : 120;

    // For ReactFlow viewport transform: node_screen = (node_world * zoom) + translate.
    // So to align left-most node at LEFT_PAD: translateX = LEFT_PAD - minX * zoom.
    const x = LEFT_PAD - minX * DEFAULT_ZOOM;
    // Vertically center the graph within the viewport at the chosen zoom.
    const y = viewMidY - graphMidY * DEFAULT_ZOOM;

    instance.setViewport?.({ x, y, zoom: DEFAULT_ZOOM }, { duration: 0 });
  }, [graph.nodes.length]);

  if (graph.nodes.length === 0) {
    return <p className="muted">{detailLoading ? "Reading signal chain…" : "No chain loaded yet."}</p>;
  }

  const showOverlay = loading || detailLoading;
  return (
    <div className="chain-flow-wrap" ref={wrapRef}>
      {showOverlay ? (
        <div className="chain-loading-overlay" aria-live="polite" aria-label="Loading signal chain">
          <div className="chain-spinner" />
        </div>
      ) : null}
      <ReactFlow
        key={patchKey}
        nodes={graph.nodes}
        edges={graph.edges}
        nodeTypes={nodeTypes}
        onInit={onInit}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        zoomOnScroll
        zoomOnPinch
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: "smoothstep" }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#2a3647" />
      </ReactFlow>
    </div>
  );
}

export function ChainView({ chain, loading, detailLoading, error, onRefresh }: Props) {
  const overview = chain?.overview;
  const hasOverview =
    Boolean(overview?.patchName) ||
    overview?.masterPatchLevel != null ||
    overview?.masterBPM != null ||
    Boolean(overview?.masterKey);

  const layout = chainLayoutFromElements(chain?.elements, {
    signalOrderElements: chain?.signalOrderElements,
    descriptionElements: chain?.descriptionElements,
    useDescriptionFilter: false,
  });

  const showDetailSpinner = detailLoading && !loading;
  const patchKey = overview?.patchName?.trim() || "current-patch";

  return (
    <section className="panel chain-panel">
      <header className="panel-header">
        <h2>Signal chain</h2>
        <button type="button" className="secondary" disabled={loading || detailLoading} onClick={onRefresh}>
          {loading ? "Reading…" : detailLoading ? "Preview…" : "From device"}
        </button>
      </header>
      {hasOverview ? (
        <div className="chain-patch-header">
          <h3 className="chain-patch-title">{overview?.patchName ?? "Current patch"}</h3>
          <p className="chain-patch-meta muted">
            {overview?.masterPatchLevel != null ? `Level ${overview.masterPatchLevel}` : null}
            {overview?.masterPatchLevel != null && overview?.masterBPM != null ? " · " : null}
            {overview?.masterBPM != null ? `${overview.masterBPM} BPM` : null}
            {(overview?.masterPatchLevel != null || overview?.masterBPM != null) && overview?.masterKey
              ? " · "
              : null}
            {overview?.masterKey ?? null}
          </p>
        </div>
      ) : null}
      {showDetailSpinner ? (
        <p className="chain-status muted">Loading block details from device…</p>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      <div className="chain-track">
        <ReactFlowProvider>
          <ChainFlowCanvas layout={layout} loading={loading} detailLoading={detailLoading} patchKey={patchKey} />
        </ReactFlowProvider>
      </div>
    </section>
  );
}
