import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Code2, Download, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Panel, TipoBadge } from "@/components/common";
import { api, downloadFile, fmtDate, fmtEUR, formatApiError } from "@/lib/api";

const Party = ({ title, p, link, testid }) => (
  <Panel className="p-5" data-testid={testid}>
    <div className="font-mono text-[11px] uppercase tracking-wider text-slate-500">{title}</div>
    <div className="mt-2 text-lg font-semibold">{link ? <Link to={link} className="hover:underline">{p.denominazione}</Link> : p.denominazione}</div>
    <dl className="mt-3 grid grid-cols-[110px_1fr] gap-y-1 text-sm">
      {p.piva && <><dt className="text-slate-500">P.IVA</dt><dd className="font-mono">{p.paese}{p.piva}</dd></>}
      {p.codice_fiscale && <><dt className="text-slate-500">Cod. Fiscale</dt><dd className="font-mono">{p.codice_fiscale}</dd></>}
      {p.indirizzo && <><dt className="text-slate-500">Sede</dt><dd>{p.indirizzo}, {p.cap} {p.comune} {p.provincia && `(${p.provincia})`}</dd></>}
      {p.regime_fiscale && <><dt className="text-slate-500">Regime</dt><dd className="font-mono">{p.regime_fiscale}</dd></>}
      {p.codice_destinatario && <><dt className="text-slate-500">Cod. SDI</dt><dd className="font-mono">{p.codice_destinatario}</dd></>}
      {p.pec && <><dt className="text-slate-500">PEC</dt><dd>{p.pec}</dd></>}
      {p.email && <><dt className="text-slate-500">Email</dt><dd>{p.email}</dd></>}
    </dl>
  </Panel>
);

const Lines = ({ inv }) => (
  <Panel className="mt-6 overflow-x-auto" data-testid="invoice-lines">
    <div className="border-b border-slate-200 p-4 text-sm font-semibold">Dettaglio righe</div>
    <Table>
      <TableHeader><TableRow className="bg-slate-50">
        <TableHead>#</TableHead><TableHead>Descrizione</TableHead><TableHead className="text-right">Q.tà</TableHead>
        <TableHead className="text-right">Prezzo unit.</TableHead><TableHead className="text-right">IVA %</TableHead><TableHead className="text-right">Totale</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {inv.righe.map((r, i) => (
          <TableRow key={i}>
            <TableCell className="font-mono text-xs">{r.numero_linea}</TableCell>
            <TableCell className="max-w-md">{r.descrizione}</TableCell>
            <TableCell className="text-right tabular-nums">{r.quantita} {r.unita_misura}</TableCell>
            <TableCell className="text-right tabular-nums">{fmtEUR(r.prezzo_unitario, inv.divisa)}</TableCell>
            <TableCell className="text-right tabular-nums">{r.natura || `${r.aliquota_iva}%`}</TableCell>
            <TableCell className="text-right font-medium tabular-nums">{fmtEUR(r.prezzo_totale, inv.divisa)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </Panel>
);

const Summary = ({ inv }) => (
  <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
    <Panel className="p-5" data-testid="invoice-vat-summary">
      <div className="mb-3 text-sm font-semibold">Riepilogo IVA</div>
      {inv.riepilogo.map((r, i) => (
        <div key={i} className="flex justify-between border-b border-dashed border-slate-200 py-2 text-sm">
          <span>{r.natura ? `Natura ${r.natura}` : `Aliquota ${r.aliquota_iva}%`}</span>
          <span className="tabular-nums">{fmtEUR(r.imponibile, inv.divisa)} + IVA {fmtEUR(r.imposta, inv.divisa)}</span>
        </div>
      ))}
      <div className="mt-3 flex justify-between text-sm"><span className="text-slate-500">Imponibile</span><span className="tabular-nums">{fmtEUR(inv.imponibile, inv.divisa)}</span></div>
      <div className="flex justify-between text-sm"><span className="text-slate-500">IVA</span><span className="tabular-nums">{fmtEUR(inv.imposta, inv.divisa)}</span></div>
      <div className="mt-2 flex justify-between border-t border-slate-200 pt-2 text-lg font-bold"><span>Totale documento</span><span className="tabular-nums" data-testid="invoice-total">{fmtEUR(inv.totale, inv.divisa)}</span></div>
    </Panel>
    <Panel className="p-5" data-testid="invoice-payments">
      <div className="mb-3 text-sm font-semibold">Pagamento</div>
      {inv.pagamenti.length === 0 && <div className="text-sm text-slate-500">Nessun dato di pagamento.</div>}
      {inv.pagamenti.map((p, i) => (
        <dl key={i} className="grid grid-cols-[110px_1fr] gap-y-1 border-b border-dashed border-slate-200 py-2 text-sm last:border-0">
          <dt className="text-slate-500">Modalità</dt><dd className="font-mono">{p.modalita} {p.condizioni && `· ${p.condizioni}`}</dd>
          {p.scadenza && <><dt className="text-slate-500">Scadenza</dt><dd>{fmtDate(p.scadenza)}</dd></>}
          <dt className="text-slate-500">Importo</dt><dd className="tabular-nums">{fmtEUR(p.importo, inv.divisa)}</dd>
          {p.iban && <><dt className="text-slate-500">IBAN</dt><dd className="font-mono text-xs">{p.iban}</dd></>}
          {p.istituto && <><dt className="text-slate-500">Banca</dt><dd>{p.istituto}</dd></>}
        </dl>
      ))}
    </Panel>
  </div>
);

export default function InvoiceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [inv, setInv] = useState(null);
  const [showXml, setShowXml] = useState(false);

  useEffect(() => {
    api.get(`/invoices/${id}`).then((r) => setInv(r.data)).catch((e) => toast.error(formatApiError(e)));
  }, [id]);

  if (!inv) return <div className="text-slate-500" data-testid="invoice-loading">Caricamento…</div>;
  const isAttiva = inv.tipo === "attiva";
  const link = inv.controparte_id && `/anagrafiche/${inv.controparte_id}`;
  const remove = async () => {
    await api.delete(`/invoices/${id}`);
    toast.success("Fattura eliminata");
    navigate(isAttiva ? "/attive" : "/passive");
  };

  return (
    <div className="fade-up">
      <button onClick={() => navigate(-1)} className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900" data-testid="invoice-back-button"><ArrowLeft size={16} /> Indietro</button>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2"><TipoBadge tipo={inv.tipo} /><span className="font-mono text-xs text-slate-500">{inv.tipo_documento} · {inv.divisa}</span></div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl" data-testid="invoice-number">Fattura n. {inv.numero}</h1>
          <div className="mt-1 text-sm text-slate-500">del {fmtDate(inv.data)} · anno {inv.anno} · file <span className="font-mono">{inv.filename}</span></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setShowXml(!showXml)} data-testid="toggle-xml-button"><Code2 className="mr-2 h-4 w-4" />{showXml ? "Vista leggibile" : "XML"}</Button>
          <Button variant="outline" onClick={() => downloadFile(`/invoices/${id}/xml`, {}, "fattura.xml")} data-testid="download-xml-button"><Download className="mr-2 h-4 w-4" />Scarica XML</Button>
          <AlertDialog>
            <AlertDialogTrigger asChild><Button variant="outline" className="text-red-600 hover:text-red-700" data-testid="delete-invoice-button"><Trash2 className="h-4 w-4" /></Button></AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader><AlertDialogTitle>Eliminare la fattura?</AlertDialogTitle><AlertDialogDescription>La fattura n. {inv.numero} verrà rimossa dall'archivio.</AlertDialogDescription></AlertDialogHeader>
              <AlertDialogFooter><AlertDialogCancel data-testid="delete-cancel">Annulla</AlertDialogCancel><AlertDialogAction onClick={remove} data-testid="delete-confirm">Elimina</AlertDialogAction></AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
      {showXml ? (
        <pre className="max-h-[70vh] overflow-auto rounded-xl bg-slate-900 p-5 text-xs leading-relaxed text-slate-100" data-testid="invoice-raw-xml">{inv.xml}</pre>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Party title="Cedente / Prestatore" p={inv.cedente} link={!isAttiva && link} testid="invoice-cedente" />
            <Party title="Cessionario / Committente" p={inv.cessionario} link={isAttiva && link} testid="invoice-cessionario" />
          </div>
          {inv.causale && <Panel className="mt-6 p-5 text-sm"><span className="font-mono text-[11px] uppercase text-slate-500">Causale</span><p className="mt-1">{inv.causale}</p></Panel>}
          <Lines inv={inv} />
          <Summary inv={inv} />
        </>
      )}
    </div>
  );
}
