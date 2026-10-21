import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DocTypeBadge, TipoBadge } from "@/components/common";
import { fmtDate, fmtEUR } from "@/lib/api";

export const InvoiceTable = ({ items, showTipo = false, loading = false }) => {
  const navigate = useNavigate();
  if (!loading && items.length === 0) {
    return <div className="p-10 text-center text-sm text-slate-500" data-testid="invoices-empty">Nessuna fattura trovata.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <Table data-testid="invoices-table">
        <TableHeader>
          <TableRow className="bg-slate-50">
            <TableHead className="font-mono text-[11px] uppercase">N. Protocollo</TableHead>
            <TableHead className="font-mono text-[11px] uppercase">Data</TableHead>
            {showTipo && <TableHead className="font-mono text-[11px] uppercase">Tipo</TableHead>}
            <TableHead className="font-mono text-[11px] uppercase">Cliente / Fornitore</TableHead>
            <TableHead className="font-mono text-[11px] uppercase">Tipo doc.</TableHead>
            <TableHead className="text-right font-mono text-[11px] uppercase">Imponibile</TableHead>
            <TableHead className="text-right font-mono text-[11px] uppercase">Totale</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((i) => (
            <TableRow key={i.id} onClick={() => navigate(`/fatture/${i.id}`)} className="cursor-pointer transition-colors hover:bg-slate-50"
              data-testid={`invoice-row-${i.id}`}>
              <TableCell className="font-mono font-medium">{i.numero}</TableCell>
              <TableCell className="whitespace-nowrap text-slate-600">{fmtDate(i.data)}</TableCell>
              {showTipo && <TableCell><TipoBadge tipo={i.tipo} /></TableCell>}
              <TableCell>
                <div className="font-medium">{i.controparte_nome || "—"}</div>
                <div className="font-mono text-xs text-slate-500">{i.controparte_piva}</div>
              </TableCell>
              <TableCell><DocTypeBadge code={i.tipo_documento} /></TableCell>
              <TableCell className="text-right tabular-nums text-slate-600">{fmtEUR(i.imponibile, i.divisa)}</TableCell>
              <TableCell className="text-right font-semibold tabular-nums">{fmtEUR(i.totale, i.divisa)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
