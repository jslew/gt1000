import type { Edge, Node } from "@xyflow/react";
import { MarkerType, Position } from "@xyflow/react";
import type { ChainLayoutItem, ChainNode } from "./chainGraph";

export type ChainFlowNodeData = {
  node: ChainNode;
  detailLoading: boolean;
  role: "block" | "divider" | "mixer";
};

const NODE_W = 104;
const NODE_H = 72;
const ROUTING_W = 72;
const GAP_X = 36;
const ROW_GAP = 88;
const PAD = 24;

function flowNode(
  chainNode: ChainNode,
  position: { x: number; y: number },
  role: ChainFlowNodeData["role"],
  detailLoading: boolean,
): Node<ChainFlowNodeData> {
  return {
    id: chainNode.id,
    type: "chainBlock",
    position,
    data: { node: chainNode, detailLoading, role },
    draggable: false,
    selectable: false,
    connectable: false,
  };
}

function linearEdge(source: string, target: string, sourceHandle = "out", targetHandle = "in"): Edge {
  return {
    id: `e-${source}-${target}-${sourceHandle}-${targetHandle}`,
    source,
    target,
    sourceHandle,
    targetHandle,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: "#6f8198" },
    style: { stroke: "#6f8198", strokeWidth: 2 },
  };
}

function layoutPath(
  path: ChainNode[],
  startX: number,
  y: number,
  nodes: Node<ChainFlowNodeData>[],
  edges: Edge[],
  dividerId: string,
  mixerId: string,
  forkHandle: "fork-a" | "fork-b",
  mergeHandle: "merge-a" | "merge-b",
  detailLoading: boolean,
): { endX: number; lastId: string | null } {
  let x = startX;
  let lastId: string | null = null;
  for (const chainNode of path) {
    nodes.push(flowNode(chainNode, { x, y }, "block", detailLoading));
    if (lastId) {
      edges.push(linearEdge(lastId, chainNode.id));
    } else {
      edges.push(linearEdge(dividerId, chainNode.id, forkHandle, "in"));
    }
    lastId = chainNode.id;
    x += NODE_W + GAP_X;
  }
  if (lastId) {
    edges.push(linearEdge(lastId, mixerId, "out", mergeHandle));
  } else {
    edges.push(linearEdge(dividerId, mixerId, forkHandle, mergeHandle));
  }
  return { endX: path.length ? x : startX, lastId };
}

export type ChainFlowGraph = {
  nodes: Node<ChainFlowNodeData>[];
  edges: Edge[];
  width: number;
  height: number;
};

export function chainLayoutToFlow(
  layout: ChainLayoutItem[],
  detailLoading: boolean,
): ChainFlowGraph {
  const nodes: Node<ChainFlowNodeData>[] = [];
  const edges: Edge[] = [];
  const mainY = PAD + ROW_GAP;
  let x = PAD;
  let lastMainId: string | null = null;
  let maxY = mainY + NODE_H;
  let minY = mainY;

  const connectMain = (targetId: string) => {
    if (lastMainId) {
      edges.push(linearEdge(lastMainId, targetId));
    }
    lastMainId = targetId;
  };

  for (const item of layout) {
    if (item.kind === "arrow") {
      continue;
    }

    if (item.kind === "node") {
      const role = item.node.label.toUpperCase().includes("MIXER")
        ? "mixer"
        : item.node.routing || item.node.label.toUpperCase().includes("DIVIDER")
          ? "divider"
          : "block";
      nodes.push(flowNode(item.node, { x, y: mainY }, role, detailLoading));
      connectMain(item.node.id);
      x += (item.node.routing ? ROUTING_W : NODE_W) + GAP_X;
      continue;
    }

    const divId = item.divider.id;
    const mixId = item.mixer.id;
    nodes.push(flowNode(item.divider, { x, y: mainY }, "divider", detailLoading));
    connectMain(divId);
    const forkX = x + ROUTING_W + GAP_X;

    const pathAY = mainY - ROW_GAP;
    const pathBY = mainY + ROW_GAP;
    minY = Math.min(minY, pathAY);
    maxY = Math.max(maxY, pathBY + NODE_H);

    const resultA = layoutPath(item.pathA, forkX, pathAY, nodes, edges, divId, mixId, "fork-a", "merge-a", detailLoading);
    const resultB = layoutPath(item.pathB, forkX, pathBY, nodes, edges, divId, mixId, "fork-b", "merge-b", detailLoading);
    const mixX = Math.max(resultA.endX, resultB.endX, forkX);

    nodes.push(flowNode(item.mixer, { x: mixX, y: mainY }, "mixer", detailLoading));
    lastMainId = mixId;
    x = mixX + ROUTING_W + GAP_X;
  }

  const width = Math.max(x + PAD, 320);
  const height = Math.max(maxY - minY + PAD * 2, 220);
  return { nodes, edges, width, height };
}

export { NODE_W, NODE_H, Position };
