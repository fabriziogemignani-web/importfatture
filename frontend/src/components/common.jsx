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

const DOC_TYPES = {
  TD01: ["Fattura", "border-slate-200 bg-slate-50 text-slate-700"],
  TD02: ["Acconto/anticipo su fattura", "border-sky-200 bg-sky-50 text-sky-700"],
  TD03: ["Acconto/anticipo su parcella", "border-sky-200 bg-sky-50 text-sky-700"],
  TD04: ["Nota di credito", "border-red-300 bg-red-50 text-red-700"],
  TD05: ["Nota di debito", "border-amber-200 bg-amber-50 text-amber-700"],
  TD06: ["Parcella", "border-violet-200 bg-violet-50 text-violet-700"],
  TD16: ["Integrazione reverse charge interno", "border-orange-200 bg-orange-50 text-orange-700"],
  TD17: ["Integrazione/autofattura servizi estero", "border-orange-200 bg-orange-50 text-orange-700"],
  TD18: ["Integrazione beni intracomunitari", "border-orange-200 bg-orange-50 text-orange-700"],
  TD19: ["Integrazione/autofattura beni art.17", "border-orange-200 bg-orange-50 text-orange-700"],
  TD20: ["Autofattura per regolarizzazione", "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700"],
  TD21: ["Autofattura per splafonamento", "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700"],
  TD24: ["Fattura differita (art.21 c.4 lett.a)", "border-teal-200 bg-teal-50 text-teal-700"],
  TD25: ["Fattura differita (art.21 c.4 lett.b)", "border-teal-200 bg-teal-50 text-teal-700"],
  TD26: ["Cessione beni ammortizzabili", "border-lime-200 bg-lime-50 text-lime-700"],
  TD27: ["Autoconsumo/cessioni gratuite", "border-lime-200 bg-lime-50 text-lime-700"],
  TD28: ["Acquisti da San Marino", "border-lime-200 bg-lime-50 text-lime-700"],
};
const DOC_FALLBACK = "border-indigo-200 bg-indigo-50 text-indigo-700";

export const DocTypeBadge = ({ code }) => {
  if (!code) return <span className="text-slate-400">—</span>;
  const [label, cls] = DOC_TYPES[code.toUpperCase()] || ["Altro documento", DOC_FALLBACK];
  return (
    <span title={label} className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-xs font-semibold ${cls}`}
      data-testid={`doc-type-badge-${code.toUpperCase()}`}>
      {code.toUpperCase()}
    </span>
  );
};
