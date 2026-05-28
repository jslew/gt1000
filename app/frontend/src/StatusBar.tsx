import type { DeviceStatus } from "./api";

type Props = {
  status: DeviceStatus | null;
  wsConnected: boolean;
  lastEvent: string | null;
};

export function StatusBar({ status, wsConnected, lastEvent }: Props) {
  let label = "Idle";
  let tone = "idle";
  if (status?.blocked_reason) {
    label = "MIDI blocked";
    tone = "error";
  } else if (status?.busy) {
    label = "Talking to GT-1000…";
    tone = "busy";
  } else if (status?.last_error) {
    label = "Device error";
    tone = "error";
  } else if (!status?.ok) {
    label = "Unavailable";
    tone = "error";
  }

  return (
    <header className="status-bar">
      <div>
        <strong>GT-1000</strong>
        <span className={`status-pill ${tone}`}>{label}</span>
        <span className={`status-pill ${wsConnected ? "ok" : "muted"}`}>
          {wsConnected ? "Events connected" : "Events disconnected"}
        </span>
      </div>
      <div className="status-meta">
        {lastEvent ? <span>Last event: {lastEvent}</span> : null}
        {status?.blocked_reason ? <span>{status.blocked_reason}</span> : null}
        {status?.last_error ? <span>{status.last_error}</span> : null}
      </div>
    </header>
  );
}
