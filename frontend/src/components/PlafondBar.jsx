import { fmtEUR } from "@/lib/api";

const COLORS = {
  ok: ["bg-emerald-500", "text-emerald-700"],
  attenzione: ["bg-amber-500", "text-amber-700"],
  superato: ["bg-red-600", "text-red-700"],
};

export const LIVELLO_LABEL = { ok: "Regolare", attenzione: "In esaurimento", superato: "Plafond superato" };

export const PlafondBar = ({ d, compact = false }) => {
  const [bar, text] = COLORS[d.livello] || COLORS.ok;
  return (
    <div data-testid={`plafond-bar-${d.id}`}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="tabular-nums text-slate-600">{fmtEUR(d.utilizzato)} di {fmtEUR(d.plafond)}</span>
        <span className={`font-semibold tabular-nums ${text}`} data-testid={`plafond-perc-${d.id}`}>{d.percentuale}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-[width] duration-500 ${bar}`} style={{ width: `${Math.min(100, Math.max(0, d.percentuale))}%` }} />
      </div>
      {!compact && (
        <div className={`mt-1 text-xs ${d.residuo < 0 ? "text-red-700" : "text-slate-500"}`} data-testid={`plafond-residuo-${d.id}`}>
          {d.residuo < 0 ? `Superato di ${fmtEUR(-d.residuo)}` : `Residuo ${fmtEUR(d.residuo)}`}
        </div>
      )}
    </div>
  );
};
