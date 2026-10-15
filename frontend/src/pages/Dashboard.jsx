import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/common";
import { api, fmtEUR } from "@/lib/api";

const MESI = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];

const Stat = ({ label, value, sub, accent, testid }) => (
  <Panel className="p-5" data-testid={testid}>
    <div className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className={`mt-2 text-2xl font-bold tabular-nums ${accent || ""}`}>{value}</div>
    {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
  </Panel>
);

export default function Dashboard() {
  const [anno, setAnno] = useState("tutti");
  const [years, setYears] = useState([]);
  const [stats, setStats] = useState(null);
  const [vat, setVat] = useState(null);

  useEffect(() => {
    api.get("/invoices/years").then((r) => setYears(r.data));
    api.get("/settings").then((r) => setVat(r.data.company_vat));
  }, []);
  useEffect(() => {
    api.get("/stats", { params: anno === "tutti" ? {} : { anno } }).then((r) => setStats(r.data));
  }, [anno]);

  const a = stats?.per_tipo?.attiva || { n: 0, totale: 0, imposta: 0 };
  const p = stats?.per_tipo?.passiva || { n: 0, totale: 0, imposta: 0 };
  const chart = (stats?.mensile || []).map((m, i) => ({ ...m, mese: MESI[i] }));

  return (
    <div>
      <PageHeader eyebrow="Panoramica" title="Dashboard">
        <Select value={String(anno)} onValueChange={setAnno}>
          <SelectTrigger className="w-36 bg-white" data-testid="dashboard-year-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="tutti">Tutti gli anni</SelectItem>
            {years.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button asChild data-testid="dashboard-upload-button"><Link to="/carica"><UploadCloud className="mr-2 h-4 w-4" />Carica fatture</Link></Button>
      </PageHeader>
      {vat === "" && (
        <div className="mb-6 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800" data-testid="dashboard-vat-warning">
          <AlertTriangle size={18} /> Imposta la P.IVA della tua azienda per distinguere fatture attive e passive.
          <Link to="/impostazioni" className="ml-auto font-semibold underline">Impostazioni</Link>
        </div>
      )}
      <div className="fade-up grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat testid="stat-attive" label="Fatture attive" value={fmtEUR(a.totale)} sub={`${a.n} documenti · IVA ${fmtEUR(a.imposta)}`} accent="text-emerald-700" />
        <Stat testid="stat-passive" label="Fatture passive" value={fmtEUR(p.totale)} sub={`${p.n} documenti · IVA ${fmtEUR(p.imposta)}`} accent="text-indigo-700" />
        <Stat testid="stat-saldo-iva" label="Saldo IVA stimato" value={fmtEUR(a.imposta - p.imposta)} sub="IVA vendite − IVA acquisti" />
        <Stat testid="stat-anagrafiche" label="Anagrafiche" value={`${stats?.n_clienti || 0} / ${stats?.n_fornitori || 0}`} sub="Clienti / Fornitori" />
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Panel className="p-5 xl:col-span-3" data-testid="dashboard-chart">
          <div className="mb-4 text-sm font-semibold">Andamento mensile (totale documenti)</div>
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="mese" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} width={70} />
                <Tooltip formatter={(v) => fmtEUR(v)} />
                <Legend />
                <Bar dataKey="attiva" name="Attive" fill="#059669" radius={[4, 4, 0, 0]} />
                <Bar dataKey="passiva" name="Passive" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel className="overflow-hidden xl:col-span-2" data-testid="dashboard-recent">
          <div className="border-b border-slate-200 p-5 text-sm font-semibold">Ultime fatture caricate</div>
          <RecentList items={stats?.recenti || []} />
        </Panel>
      </div>
    </div>
  );
}

const RecentList = ({ items }) => {
  if (!items.length) return <div className="p-8 text-center text-sm text-slate-500">Nessuna fattura ancora.</div>;
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((i) => (
        <li key={i.id}>
          <Link to={`/fatture/${i.id}`} className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-slate-50" data-testid={`recent-invoice-${i.id}`}>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{i.controparte_nome}</div>
              <div className="font-mono text-xs text-slate-500">N. {i.numero} · {i.anno}</div>
            </div>
            <div className="text-right">
              <div className={`text-sm font-semibold tabular-nums ${i.tipo === "attiva" ? "text-emerald-700" : "text-indigo-700"}`}>{fmtEUR(i.totale, i.divisa)}</div>
              <div className="text-[11px] uppercase text-slate-400">{i.tipo}</div>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
};
