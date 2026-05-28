import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { ChainFlowNodeData } from "./chainFlow";

function roleForNode(node: ChainFlowNodeData["node"]): ChainFlowNodeData["role"] {
  const upper = node.label.toUpperCase();
  if (upper.includes("MIXER")) {
    return "mixer";
  }
  if (upper.includes("DIVIDER") || node.routing) {
    return "divider";
  }
  return "block";
}

export function ChainFlowNode({ data }: NodeProps<Node<ChainFlowNodeData>>) {
  const { node, detailLoading } = data;
  const role = data.role ?? roleForNode(node);
  const isRouting = role === "divider" || role === "mixer";

  return (
    <article
      className={[
        "chain-node",
        node.enabled === true ? "enabled" : "",
        node.enabled === false ? "disabled" : "",
        node.output ? "output" : "",
        isRouting ? "routing" : "",
        detailLoading && node.enabled == null && !isRouting ? "preview" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      title={node.detail ? `${node.label} — ${node.detail}` : node.label}
    >
      {role === "block" || role === "mixer" ? (
        <Handle type="target" position={Position.Left} id="in" className="chain-handle" />
      ) : null}

      {role === "divider" ? (
        <>
          <Handle type="target" position={Position.Left} id="in" className="chain-handle" />
          <Handle type="source" position={Position.Top} id="fork-a" className="chain-handle chain-handle-fork" />
          <Handle type="source" position={Position.Bottom} id="fork-b" className="chain-handle chain-handle-fork" />
        </>
      ) : null}

      {role === "mixer" ? (
        <>
          <Handle type="target" position={Position.Top} id="merge-a" className="chain-handle chain-handle-merge" />
          <Handle type="target" position={Position.Bottom} id="merge-b" className="chain-handle chain-handle-merge" />
          <Handle type="source" position={Position.Right} id="out" className="chain-handle" />
        </>
      ) : null}

      {role === "block" ? (
        <Handle type="source" position={Position.Right} id="out" className="chain-handle" />
      ) : null}

      <span className="chain-node-icon" aria-hidden>
        {node.icon}
      </span>
      <strong>{node.shortLabel}</strong>
      {node.detail ? <span className="chain-node-detail">{node.detail}</span> : null}
    </article>
  );
}
