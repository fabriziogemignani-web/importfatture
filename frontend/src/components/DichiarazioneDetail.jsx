import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Download, FileUp, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { DocTypeBadge } from "@/components/common";
import { PlafondBar } from "@/components/PlafondBar";
import { api, downloadFile, fmtDate, fmtEUR, formatApiError } from "@/lib/api";

const KINDS = [["dichiarazione", "Dichiarazione d'intento"], ["ricevuta", "Ricevuta telematica"]];

const Allegato = ({ d, kind, label, onChange }) => {
  const input = useRef(null);
  const name = d.files?.[kind];
  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/dichiarazioni/${d.id}/files/${kind}`, fd);
      toast.success("PDF caricato");
      onChange();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  const remove = async () => {
    await api.delete(`/dichiarazioni/${d.id}/files/${kind}`);
    onChange();
  };
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3" data-testid={`dich-file-${kind}`}>
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        <div className="truncate text-xs text-slate-500">{name || "Nessun PDF allegato"}</div>
      </div>
      <input ref={input} type="file" accept="application/pdf,.pdf" className="hidden" onChange={upload} data-testid={`dich-file-input-${kind}`} />
      <div className="flex shrink-0 gap-1">
        {name && <Button size="icon" variant="ghost" onClick={() => downloadFile(`/dichiarazioni/${d.id}/files/${kind}`, {}, name)} data-testid={`dich-file-download-${kind}`}><Download className="h-4 w-4" /></Button>}
        {name && <Button size="icon" variant="ghost" onClick={remove} data-testid={`dich-file-delete-${kind}`}><Trash2 className="h-4 w-4" /></Button>}
        <Button size="sm" variant="outline" onClick={() => input.current?.click()} data-testid={`dich-file-upload-${kind}`}><FileUp className="mr-1 h-4 w-4" />{name ? "Sostituisci" : "Carica PDF"}</Button>
      </div>
    </div>
  );
};

const FattureList = ({ fatture }) => (
  <div className="overflow-hidden rounded-lg border border-slate-200">
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-left text-xs text-slate-500">
        <tr><th className="px-3 py-2">Fattura</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2 text-right">Importo</th><th className="px-3 py-2 text-right">Progressivo</th></tr>
      </thead>
      <tbody>
        {fatture.map((f) => (
          <tr key={`${f.invoice_id}-${f.progressivo}`} className="border-t border-slate-100" data-testid={`dich-fattura-${f.invoice_id}`}>
            <td className="px-3 py-2"><Link to={`/fatture/${f.invoice_id}`} className="font-medium hover:underline">{f.numero}</Link><div className="text-xs text-slate-500">{fmtDate(f.data)}</div></td>
            <td className="px-3 py-2"><DocTypeBadge code={f.tipo_documento} /></td>
            <td className={`px-3 py-2 text-right tabular-nums ${f.importo < 0 ? "text-red-600" : ""}`}>{fmtEUR(f.importo)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{fmtEUR(f.progressivo)}</td>
          </tr>
        ))}
        {!fatture.length && <tr><td colSpan={4} className="px-3 py-6 text-center text-slate-500">Nessuna fattura collegata a questo protocollo</td></tr>}
      </tbody>
    </table>
  </div>
);

export const DichiarazioneDetail = ({ id, onClose, onChanged }) => {
  const [d, setD] = useState(null);
  const load = useCallback(() => {
    if (id) api.get(`/dichiarazioni/${id}`).then((r) => setD(r.data)).catch(() => setD(null));
  }, [id]);
  useEffect(() => {
    setD(null);
    load();
  }, [load]);
  const refresh = () => {
    load();
    onChanged();
  };
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl" data-testid="dich-detail">
        <SheetHeader><SheetTitle>{d?.cliente_nome || "Dichiarazione"}</SheetTitle></SheetHeader>
        {d && (
          <div className="mt-4 space-y-6">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><div className="text-xs text-slate-500">Protocollo</div><div className="font-mono text-xs" data-testid="dich-detail-protocollo">{d.protocollo}</div></div>
              <div><div className="text-xs text-slate-500">Ricevuta del</div>{fmtDate(d.data)}</div>
              <div><div className="text-xs text-slate-500">P.IVA cliente</div><span className="font-mono">{d.cliente_piva}</span></div>
              <div><div className="text-xs text-slate-500">Anno</div>{d.anno}{d.data_revoca && <span className="ml-2 text-red-600">revocata dal {fmtDate(d.data_revoca)}</span>}</div>
            </div>
            <PlafondBar d={d} />
            <div className="space-y-2">{KINDS.map(([k, l]) => <Allegato key={k} d={d} kind={k} label={l} onChange={refresh} />)}</div>
            <div>
              <div className="mb-2 text-sm font-semibold">Fatture che erodono il plafond ({d.n_fatture})</div>
              <FattureList fatture={d.fatture} />
            </div>
            {d.note && <p className="whitespace-pre-wrap text-sm text-slate-600">{d.note}</p>}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
