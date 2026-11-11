import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DocTypeBadge, PageHeader, Panel } from "@/components/common";
import { YearTabs } from "@/pages/Invoices";
import { DichiarazioneDialog } from "@/components/DichiarazioneDialog";
import { DichiarazioneDetail } from "@/components/DichiarazioneDetail";
import { LIVELLO_LABEL, PlafondBar } from "@/components/PlafondBar";
import { api, fmtDate, fmtEUR, formatApiError } from "@/lib/api";

const thisYear = new Date().getFullYear();
const BADGE = { ok: "border-emerald-200 bg-emerald-50 text-emerald-700", attenzione: "border-amber-200 bg-amber-50 text-amber-800", superato: "border-red-300 bg-red-50 text-red-700" };

const Stat = ({ label, value, accent, testid }) => (
  <Panel className="p-5" data-testid={testid}>
    <div className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className={`mt-2 text-2xl font-bold tabular-nums ${accent || ""}`}>{value}</div>
  </Panel>
);

const DichRow = ({ d, onOpen, onEdit, onDelete }) => (
  <tr className="cursor-pointer border-t border-slate-100 transition-colors hover:bg-slate-50" onClick={() => onOpen(d.id)} data-testid={`dich-row-${d.id}`}>
    <td className="px-4 py-3"><div className="font-medium">{d.cliente_nome}</div><div className="font-mono text-xs text-slate-500">{d.cliente_piva}</div></td>
    <td className="px-4 py-3"><div className="font-mono text-xs">{d.protocollo}</div><div className="text-xs text-slate-500">ricevuta {fmtDate(d.data)} · anno {d.anno}</div></td>
    <td className="w-64 px-4 py-3"><PlafondBar d={d} compact /></td>
    <td className="px-4 py-3 text-right tabular-nums">{fmtEUR(d.residuo)}</td>
    <td className="px-4 py-3">
      <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${BADGE[d.livello]}`} data-testid={`dich-livello-${d.id}`}>{d.data_revoca ? "Revocata" : LIVELLO_LABEL[d.livello]}</span>
    </td>
    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
      <Button size="icon" variant="ghost" onClick={() => onEdit(d)} data-testid={`dich-edit-${d.id}`}><Pencil className="h-4 w-4" /></Button>
      <Button size="icon" variant="ghost" onClick={() => onDelete(d)} data-testid={`dich-delete-${d.id}`}><Trash2 className="h-4 w-4" /></Button>
    </td>
  </tr>
);

const DichTable = ({ items, ...handlers }) => (
  <Panel className="overflow-x-auto">
    <table className="w-full min-w-[820px] text-sm" data-testid="dich-table">
      <thead className="bg-slate-50 text-left text-xs text-slate-500">
        <tr><th className="px-4 py-3">Cliente</th><th className="px-4 py-3">Protocollo</th><th className="px-4 py-3">Utilizzo plafond</th><th className="px-4 py-3 text-right">Residuo</th><th className="px-4 py-3">Stato</th><th /></tr>
      </thead>
      <tbody>
        {items.map((d) => <DichRow key={d.id} d={d} {...handlers} />)}
        {!items.length && <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-500" data-testid="dich-empty">Nessuna dichiarazione d'intento registrata per il periodo</td></tr>}
      </tbody>
    </table>
  </Panel>
);

const AnomalieTable = ({ items }) => (
  <Panel className="overflow-x-auto">
    <table className="w-full min-w-[820px] text-sm" data-testid="anomalie-table">
      <thead className="bg-slate-50 text-left text-xs text-slate-500">
        <tr><th className="px-4 py-3">Fattura</th><th className="px-4 py-3">Cliente</th><th className="px-4 py-3">Protocollo in fattura</th><th className="px-4 py-3 text-right">Importo N3.5</th><th className="px-4 py-3">Problema</th></tr>
      </thead>
      <tbody>
        {items.map((a) => (
          <tr key={`${a.invoice_id}-${a.codice}-${a.protocollo}`} className="border-t border-slate-100" data-testid={`anomalia-${a.codice}-${a.invoice_id}`}>
            <td className="px-4 py-3"><Link to={`/fatture/${a.invoice_id}`} className="font-medium hover:underline">{a.numero}</Link> <DocTypeBadge code={a.tipo_documento} /><div className="text-xs text-slate-500">{fmtDate(a.data)}</div></td>
            <td className="px-4 py-3">{a.controparte_nome}<div className="font-mono text-xs text-slate-500">{a.controparte_piva}</div></td>
            <td className="px-4 py-3 font-mono text-xs">{a.protocollo || "—"}</td>
            <td className="px-4 py-3 text-right tabular-nums">{fmtEUR(a.importo)}</td>
            <td className="px-4 py-3 text-red-700"><AlertTriangle className="mr-1 inline h-4 w-4" />{a.messaggio}</td>
          </tr>
        ))}
        {!items.length && <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500" data-testid="anomalie-empty">Nessuna fattura irregolare</td></tr>}
      </tbody>
    </table>
  </Panel>
);

export default function Dichiarazioni() {
  const [anno, setAnno] = useState(thisYear);
  const [data, setData] = useState(null);
  const [edit, setEdit] = useState(null);
  const [openId, setOpenId] = useState(null);
  const load = useCallback(() => {
    api.get("/dichiarazioni", { params: anno === "tutti" ? {} : { anno } }).then((r) => setData(r.data)).catch((e) => toast.error(formatApiError(e)));
  }, [anno]);
  useEffect(() => {
    load();
  }, [load]);

  const remove = async (d) => {
    if (!window.confirm(`Eliminare la dichiarazione ${d.protocollo}?`)) return;
    await api.delete(`/dichiarazioni/${d.id}`);
    toast.success("Dichiarazione eliminata");
    load();
  };
  const list = data?.dichiarazioni || [];
  const anomalie = data?.anomalie || [];
  const sum = (k) => list.reduce((s, d) => s + d[k], 0);
  const critiche = list.filter((d) => d.livello !== "ok").length;

  return (
    <div>
      <PageHeader eyebrow="Esportatori abituali · natura N3.5" title="Dichiarazioni d'intento">
        <Button onClick={() => setEdit({})} data-testid="dich-new-button"><Plus className="mr-2 h-4 w-4" />Nuova dichiarazione</Button>
      </PageHeader>
      <YearTabs years={[thisYear + 1, thisYear, thisYear - 1, thisYear - 2]} value={anno} onChange={setAnno} />
      <div className="fade-up mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Plafond totale" value={fmtEUR(sum("plafond"))} testid="dich-stat-plafond" />
        <Stat label="Utilizzato" value={fmtEUR(sum("utilizzato"))} testid="dich-stat-utilizzato" />
        <Stat label="In esaurimento / superate" value={critiche} accent={critiche ? "text-amber-600" : ""} testid="dich-stat-critiche" />
        <Stat label="Fatture irregolari" value={anomalie.length} accent={anomalie.length ? "text-red-600" : ""} testid="dich-stat-anomalie" />
      </div>
      <Tabs defaultValue="dichiarazioni" className="mt-6">
        <TabsList>
          <TabsTrigger value="dichiarazioni" data-testid="dich-tab-list">Dichiarazioni ({list.length})</TabsTrigger>
          <TabsTrigger value="anomalie" data-testid="dich-tab-anomalie">Fatture irregolari ({anomalie.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="dichiarazioni"><DichTable items={list} onOpen={setOpenId} onEdit={setEdit} onDelete={remove} /></TabsContent>
        <TabsContent value="anomalie"><AnomalieTable items={anomalie} /></TabsContent>
      </Tabs>
      <DichiarazioneDialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)} initial={edit?.id ? edit : null} onSaved={load} />
      <DichiarazioneDetail id={openId} onClose={() => setOpenId(null)} onChanged={load} />
    </div>
  );
}
