export function MetricTile({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/70">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
        <div className="h-2 w-2 rounded-full bg-signal" />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-normal text-ink">{value}</div>
    </div>
  );
}
