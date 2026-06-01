import ReactFlow, { Background, Handle, Position } from "reactflow";

const nodeLabels = {
  HSS_HLR: "HSS/HLR",
  PCRF_PCF: "PCRF/PCF",
  OCS_BILLING: "OCS/Billing",
  SIM_PROVISIONING: "SIM Provisioning",
  NOTIFICATION: "Notification"
};

const statusClasses = {
  SUCCESS: "border-emerald-300 bg-emerald-50 text-emerald-900",
  FAILED: "border-red-300 bg-red-50 text-red-900",
  RUNNING: "border-cyan-300 bg-cyan-50 text-cyan-900",
  PENDING: "border-slate-300 bg-white text-slate-700"
};

function FlowNode({ data }) {
  return (
    <div className={`min-w-40 rounded border px-3 py-2 text-sm shadow-sm ${statusClasses[data.status] ?? statusClasses.PENDING}`}>
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <div className="font-semibold">{data.label}</div>
      <div className="mt-1 text-xs">{data.status}</div>
      {data.error ? <div className="mt-2 max-w-48 text-xs">{data.error}</div> : null}
      <Handle type="source" position={Position.Right} className="opacity-0" />
    </div>
  );
}

const nodeTypes = { activationNode: FlowNode };

function buildFlow(attempt) {
  const runs = attempt?.nodes ?? [];
  const nodes = runs.map((run, index) => ({
    id: run.node,
    type: "activationNode",
    position: { x: index * 210, y: index % 2 === 0 ? 35 : 135 },
    data: {
      label: nodeLabels[run.node] ?? run.node,
      status: run.status,
      error: run.error_message
    }
  }));
  const edges = runs.slice(0, -1).map((run, index) => ({
    id: `${run.node}-${runs[index + 1].node}`,
    source: run.node,
    target: runs[index + 1].node,
    animated: run.status === "SUCCESS" && runs[index + 1].status === "RUNNING",
    style: { stroke: run.status === "SUCCESS" ? "#059669" : "#94a3b8", strokeWidth: 2 }
  }));
  return { nodes, edges };
}

export function ActivationFlow({ attempt }) {
  if (!attempt) {
    return (
      <div className="rounded border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
        Activation workflow starts after seller KYC approval.
      </div>
    );
  }

  const { nodes, edges } = buildFlow(attempt);

  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Core Network Activation</h2>
          <p className="text-sm text-slate-500">
            Attempt #{attempt.id} - {attempt.status}
          </p>
        </div>
        {attempt.failure_reason ? <div className="text-sm text-alert">{attempt.failure_reason}</div> : null}
      </div>
      <div className="mt-4 h-72 min-w-0 overflow-hidden rounded border border-slate-100">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView nodesDraggable={false} nodesConnectable={false} zoomOnScroll={false} panOnScroll>
          <Background gap={18} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}
