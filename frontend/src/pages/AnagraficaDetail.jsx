import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/common";
import { InvoiceTable } from "@/components/InvoiceTable";
import { api, downloadFile, fmtEUR } from "@/lib/api";

const Field = ({ label, value }) => value ? (
  <div><dt className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{label}</dt><dd className="mt-0.5 text-sm">{value}</dd></div>
) : null;

const RoleSwitch = ({ ruoli, ruolo, onChange }) => (
  <div className="flex gap-2">
    {ruoli.map((r) => (
      <button key={r} onClick={() => onChange(r)} data-testid={`anagrafica-role-${r}`}
        className={`rounded-md border px-2 py-0.5 text-xs capitalize transition-colors ${r === ruolo ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-400"}`}>
        {r}
      </button>
    ))}
  </div>
);

export default function AnagraficaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [a, setA] = useState(null);
  const [invoices, setInvoices] = useState([]);

  useEffect(() => {
    api.get(`/anagrafiche/${id}`).then((r) => setA(r.data));
  }, [id]);

  const ruolo = a && (a.ruoli.includes(params.get("ruolo")) ? params.get("ruolo") : a.ruoli[0]);
  const tipo = ruolo === "fornitore" ? "passiva" : "attiva";

  useEffect(() => {
    if (!ruolo) {
      return;
    }
    api.get("/invoices", { params: { anagrafica_id: id, tipo, order: "desc", limit: 200 } }).then((r) => setInvoices(r.data.items));
  }, [id, ruolo, tipo]);

  if (!a) return <div className="text-slate-500">Caricamento…</div>;
  const tot = a.riepilogo?.[tipo] || { n: 0, totale: 0 };
  const isCliente = ruolo === "cliente";

  return (
    <div className="fade-up">
      <button onClick={() => navigate(-1)} className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900" data-testid="anagrafica-back-button"><ArrowLeft size={16} /> Indietro</button>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <RoleSwitch ruoli={a.ruoli} ruolo={ruolo} onChange={(r) => setParams({ ruolo: r }, { replace: true })} />
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl" data-testid="anagrafica-name">{a.denominazione}</h1>
        </div>
        <Button variant="outline" onClick={() => downloadFile("/invoices/export", { anagrafica_id: id, tipo, order: "desc" }, "fatture.csv")} data-testid="anagrafica-export-csv"><Download className="mr-2 h-4 w-4" />Esporta CSV</Button>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel className="p-5 lg:col-span-2" data-testid="anagrafica-info">
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="P.IVA" value={a.piva && `${a.paese || ""}${a.piva}`} />
            <Field label="Codice fiscale" value={a.codice_fiscale} />
            <Field label="Indirizzo" value={a.indirizzo && `${a.indirizzo}, ${a.cap || ""} ${a.comune || ""} ${a.provincia ? `(${a.provincia})` : ""}`} />
            <Field label="Nazione" value={a.nazione} />
            <Field label="Codice destinatario SDI" value={a.codice_destinatario} />
            <Field label="PEC" value={a.pec} />
            <Field label="Email" value={a.email} />
            <Field label="Telefono" value={a.telefono} />
            <Field label="Regime fiscale" value={a.regime_fiscale} />
          </dl>
        </Panel>
        <Panel className="p-5" data-testid="anagrafica-totals">
          <div className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{isCliente ? "Fatture attive (vendite)" : "Fatture passive (acquisti)"}</div>
          <div className={`mt-1 text-2xl font-bold tabular-nums ${isCliente ? "text-emerald-700" : "text-indigo-700"}`} data-testid="anagrafica-total-amount">{fmtEUR(tot.totale)}</div>
          <div className="text-xs text-slate-500" data-testid="anagrafica-total-docs">{tot.n} fatture</div>
        </Panel>
      </div>
      <Panel className="mt-6 overflow-hidden">
        <div className="border-b border-slate-200 p-4 text-sm font-semibold">Storico fatture {isCliente ? "attive" : "passive"}</div>
        <InvoiceTable items={invoices} />
      </Panel>
    </div>
  );
}
