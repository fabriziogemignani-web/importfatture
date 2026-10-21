import { useEffect, useState } from "react";
import { ArrowDownWideNarrow, ArrowUpNarrowWide, Download, Search } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel, docTypeLabel } from "@/components/common";
import { InvoiceTable } from "@/components/InvoiceTable";
import { api, downloadFile, fmtEUR, formatApiError } from "@/lib/api";

const LIMIT = 50;

export const YearTabs = ({ years, value, onChange }) => (
  <div className="flex flex-wrap gap-2" data-testid="year-tabs">
    {["tutti", ...years].map((y) => (
      <button key={y} onClick={() => onChange(y)} data-testid={`year-tab-${y}`}
        className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${String(value) === String(y) ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-400"}`}>
        {y === "tutti" ? "Tutti" : y}
      </button>
    ))}
  </div>
);

export default function Invoices({ tipo }) {
  const [years, setYears] = useState([]);
  const [anno, setAnno] = useState("tutti");
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [order, setOrder] = useState("asc");
  const [docType, setDocType] = useState("tutti");
  const [docTypes, setDocTypes] = useState([]);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, somma_totale: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAnno("tutti");
    setQ("");
    setDocType("tutti");
    api.get("/invoices/years", { params: { tipo } }).then((r) => {
      setYears(r.data);
      if (r.data.length) setAnno(r.data[0]);
    });
  }, [tipo]);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    api.get("/invoices/doc-types", { params: { tipo, ...(anno !== "tutti" && { anno }) } }).then((r) => setDocTypes(r.data));
  }, [tipo, anno]);
  useEffect(() => {
    setPage(1);
  }, [anno, debounced, order, tipo, docType]);

  const params = { tipo, order, ...(anno !== "tutti" && { anno }), ...(debounced && { q: debounced }), ...(docType !== "tutti" && { tipo_documento: docType }) };
  const key = JSON.stringify({ ...params, page });
  useEffect(() => {
    setLoading(true);
    api.get("/invoices", { params: { ...JSON.parse(key), limit: LIMIT } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [key]);

  const exportCsv = () => downloadFile("/invoices/export", params, "fatture.csv").catch((e) => toast.error(formatApiError(e)));
  const pages = Math.max(1, Math.ceil(data.total / LIMIT));
  const isAttiva = tipo === "attiva";

  return (
    <div>
      <PageHeader eyebrow={isAttiva ? "Fatture emesse · clienti" : "Fatture ricevute · fornitori"} title={isAttiva ? "Fatture Attive" : "Fatture Passive"}>
        <Button variant="outline" onClick={exportCsv} data-testid="export-csv-button"><Download className="mr-2 h-4 w-4" />Esporta CSV</Button>
      </PageHeader>
      <YearTabs years={years} value={anno} onChange={setAnno} />
      <Panel className="fade-up mt-5 overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" placeholder="Cerca per numero, cliente/fornitore, P.IVA, descrizione…" data-testid="invoice-search-input" />
          </div>
          <Select value={docType} onValueChange={setDocType}>
            <SelectTrigger className="sm:w-64" data-testid="doc-type-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="tutti" data-testid="doc-type-option-tutti">Tutti i tipi documento</SelectItem>
              {docType !== "tutti" && !docTypes.some((d) => d.code === docType) && (
                <SelectItem value={docType}>{docType} · {docTypeLabel(docType)} (0)</SelectItem>
              )}
              {docTypes.map((d) => (
                <SelectItem key={d.code} value={d.code} data-testid={`doc-type-option-${d.code}`}>{d.code} · {docTypeLabel(d.code)} ({d.n})</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => setOrder(order === "asc" ? "desc" : "asc")} data-testid="sort-order-button">
            {order === "asc" ? <ArrowUpNarrowWide className="mr-2 h-4 w-4" /> : <ArrowDownWideNarrow className="mr-2 h-4 w-4" />}
            Protocollo {order === "asc" ? "crescente" : "decrescente"}
          </Button>
        </div>
        <div className="flex items-center justify-between bg-slate-50/60 px-4 py-2 text-xs text-slate-500">
          <span data-testid="invoices-count">{data.total} fatture</span>
          <span data-testid="invoices-sum">Totale: <b className="text-slate-900">{fmtEUR(data.somma_totale)}</b></span>
        </div>
        <InvoiceTable items={data.items} loading={loading} />
        {pages > 1 && (
          <div className="flex items-center justify-end gap-2 border-t border-slate-200 p-3 text-sm">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="page-prev">Precedente</Button>
            <span data-testid="page-indicator">{page} / {pages}</span>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)} data-testid="page-next">Successiva</Button>
          </div>
        )}
      </Panel>
    </div>
  );
}
