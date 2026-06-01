export function TextInput({ label, value, onChange, type = "text", required = true, min, max }) {
  return (
    <label className="grid gap-2 text-sm">
      {label}
      <input
        className="rounded border border-slate-300 px-3 py-2"
        type={type}
        value={value}
        min={min}
        max={max}
        required={required}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
