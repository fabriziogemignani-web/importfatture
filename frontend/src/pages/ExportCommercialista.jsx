import { useEffect, useState } from "react";
import { Archive, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { PageHeader, Panel } from "@/components/common";
import { api, downloadFile, fmtEUR, formatApiError } from "@/lib/api";

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const presets = () => {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  const q = Math.floor(m / 3);
  return [
    ["Mese scorso", iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))],
    ["Mese in corso", iso(new Date(y, m, 1)), iso(now)],
    ["Trimestre scorso", iso(new Date(y, (q - 1) * 3, 1)), iso(new Date(y, q * 3, 0))],
    ["Anno scorso", `${y - 1}-01-01`, `${y - 1}-12-31`],
    ["Anno in corso", `${y}-01-01`, iso(now)],
  ];
};

const useCounts = (dal, al) => {
  const [counts, setCounts] = useState(null);
  useEffect(() => {
    if (!dal || !al || dal > al) {
      setCounts(null);
      return;
    }
    let alive = true;
    Promise.all(["attiva", "passiva"].map((tipo) => api.get("/invoices", { params: { tipo, dal, al, limit: 1 } })))
      .then(([a, p]) => alive && setCounts({ attiva: a.data, passiva: p.data }))
      .catch(() => alive && setCounts(null));
    return () => {
      alive = false;
    };
  }, [dal, al]);
  return counts;
};

const TipoCheck = ({ id, label, checked, onChange, info }) => (
  <label className="flex flex-1 cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-4 transition-colors hover:border-slate-400">
    <Checkbox checked={checked} onCheckedChange={onChange} data-testid={`export-check-${id}`} />
    <div>
      <div className="text-sm font-semibold">{label}</div>
      <div className="text-xs text-slate-500" data-testid={`export-count-${id}`}>
        {info ? `${info.total} ${info.total === 1 ? "fattura" : "fatture"} · ${fmtEUR(info.somma_totale)}` : "—"}
      </div>
    </div>
  </label>
);

export default function ExportCommercialista() {
  const [first] = useState(presets);
  const [dal, setDal] = useState(first[0][1]);
  const [al, setAl] = useState(first[0][2]);
  const [tipi, setTipi] = useState({ attiva: true, passiva: true });
  const [busy, setBusy] = useState(false);
  const counts = useCounts(dal, al);
  const toggle = (k) => setTipi((t) => ({ ...t, [k]: !t[k] }));
  const selected = Object.keys(tipi).filter((k) => tipi[k]);
  const total = counts ? selected.reduce((s, k) => s + counts[k].total, 0) : 0;

  const download = async () => {
    setBusy(true);
    try {
      const params = { dal, al, ...(selected.length === 1 && { tipo: selected[0] }) };
      await downloadFile("/invoices/export-zip", params, `fatture_${dal}_${al}.zip`);
      toast.success("Archivio ZIP scaricato");
    } catch (e) {
      toast.error(e?.response?.status === 404 ? "Nessuna fattura nel periodo selezionato" : formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader eyebrow="Invio al commercialista" title="Esportazione massiva" />
      <Panel className="fade-up max-w-3xl space-y-6 p-6" data-testid="export-panel">
        <div>
          <div className="mb-2 text-sm font-semibold">Periodo</div>
          <div className="flex flex-wrap gap-2">
            {first.map(([label, d, a]) => (
              <button key={label} onClick={() => { setDal(d); setAl(a); }} data-testid={`export-preset-${label.replace(/\s+/g, "-").toLowerCase()}`}
                className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${dal === d && al === a ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-400"}`}>
                {label}
              </button>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="dal">Dal</Label><Input id="dal" type="date" value={dal} onChange={(e) => setDal(e.target.value)} data-testid="export-date-from" /></div>
            <div className="space-y-2"><Label htmlFor="al">Al</Label><Input id="al" type="date" value={al} onChange={(e) => setAl(e.target.value)} data-testid="export-date-to" /></div>
          </div>
          {dal > al && <p className="mt-2 text-sm text-red-600" data-testid="export-date-error">La data iniziale deve precedere quella finale.</p>}
        </div>
        <div>
          <div className="mb-2 text-sm font-semibold">Fatture da includere</div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <TipoCheck id="attive" label="Fatture attive" checked={tipi.attiva} onChange={() => toggle("attiva")} info={counts?.attiva} />
            <TipoCheck id="passive" label="Fatture passive" checked={tipi.passiva} onChange={() => toggle("passiva")} info={counts?.passiva} />
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-slate-500">Lo ZIP contiene le cartelle <span className="font-mono">attive/</span> e <span className="font-mono">passive/</span> con gli XML originali e un <span className="font-mono">riepilogo.csv</span>.</p>
          <Button onClick={download} disabled={busy || !selected.length || dal > al || total === 0} data-testid="export-zip-button">
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
            Scarica ZIP ({total})
          </Button>
        </div>
      </Panel>
    </div>
  );
}
