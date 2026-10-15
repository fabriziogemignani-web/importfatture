export const TipoBadge = ({ tipo }) => (
  <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${tipo === "attiva" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-indigo-200 bg-indigo-50 text-indigo-700"}`}
    data-testid={`tipo-badge-${tipo}`}>
    {tipo === "attiva" ? "Attiva" : "Passiva"}
  </span>
);

export const PageHeader = ({ eyebrow, title, children }) => (
  <div className="fade-up mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div>
      {eyebrow && <div className="font-mono text-xs uppercase tracking-wider text-slate-500">{eyebrow}</div>}
      <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl" data-testid="page-title">{title}</h1>
    </div>
    {children && <div className="flex flex-wrap gap-2">{children}</div>}
  </div>
);

export const Panel = ({ children, className = "", ...rest }) => (
  <div className={`rounded-xl border border-slate-200 bg-white ${className}`} {...rest}>{children}</div>
);
