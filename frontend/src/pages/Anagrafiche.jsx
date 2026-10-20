import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, Panel } from "@/components/common";
import { YearTabs } from "@/pages/Invoices";
import { api, fmtEUR } from "@/lib/api";

const Totals = ({ items, ruolo }) => (
  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3" data-testid="anagrafiche-totals">
    {[
      [ruolo === "cliente" ? "Clienti" : "Fornitori", items.length, "anagrafiche-total-count"],
      ["Documenti", items.reduce((s, a) => s + a.n_fatture, 0), "anagrafiche-total-docs"],
      ["Importo totale", fmtEUR(items.reduce((s, a) => s + a.totale_fatture, 0)), "anagrafiche-total-amount"],
    ].map(([label, value, id]) => (
      <Panel key={id} className="p-5">
        <div className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
        <div className={`mt-2 text-2xl font-bold tabular-nums ${ruolo === "cliente" ? "text-emerald-700" : "text-indigo-700"}`} data-testid={id}>{value}</div>
      </Panel>
    ))}
  </div>
);

export default function Anagrafiche() {
  const [ruolo, setRuolo] = useState("cliente");
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [years, setYears] = useState([]);
  const [anno, setAnno] = useState("tutti");
  const navigate = useNavigate();

  useEffect(() => {
    setAnno("tutti");
    api.get("/invoices/years", { params: { tipo: ruolo === "cliente" ? "attiva" : "passiva" } }).then((r) => setYears(r.data));
  }, [ruolo]);

  useEffect(() => {
    const t = setTimeout(() => {
      api.get("/anagrafiche", { params: { ruolo, ...(q && { q }), ...(anno !== "tutti" && { anno }) } }).then((r) => setItems(r.data));
    }, 250);
    return () => clearTimeout(t);
  }, [ruolo, q, anno]);

  return (
    <div>
      <PageHeader eyebrow="Registro" title="Anagrafiche" />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={ruolo} onValueChange={setRuolo}>
          <TabsList>
            <TabsTrigger value="cliente" data-testid="tab-clienti">Clienti</TabsTrigger>
            <TabsTrigger value="fornitore" data-testid="tab-fornitori">Fornitori</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative sm:w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} className="bg-white pl-9" placeholder="Cerca ragione sociale, P.IVA, comune…" data-testid="anagrafiche-search-input" />
        </div>
      </div>
      <div className="mt-5"><YearTabs years={years} value={anno} onChange={setAnno} /></div>
      <div className="mt-5"><Totals items={items} ruolo={ruolo} /></div>
      <Panel className="fade-up mt-5 overflow-x-auto">
        {items.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500" data-testid="anagrafiche-empty">Nessuna anagrafica trovata.</div>
        ) : (
          <Table data-testid="anagrafiche-table">
            <TableHeader><TableRow className="bg-slate-50">
              <TableHead>Ragione sociale</TableHead><TableHead>P.IVA / CF</TableHead><TableHead>Comune</TableHead>
              <TableHead className="text-right">Documenti</TableHead><TableHead className="text-right">Importo</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((a) => (
                <TableRow key={a.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/anagrafiche/${a.id}`)} data-testid={`anagrafica-row-${a.id}`}>
                  <TableCell className="font-medium">{a.denominazione}</TableCell>
                  <TableCell className="font-mono text-xs">{a.chiave}</TableCell>
                  <TableCell className="text-slate-600">{a.comune} {a.provincia && `(${a.provincia})`}</TableCell>
                  <TableCell className="text-right tabular-nums">{a.n_fatture}</TableCell>
                  <TableCell className="text-right font-semibold tabular-nums">{fmtEUR(a.totale_fatture)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </div>
  );
}
