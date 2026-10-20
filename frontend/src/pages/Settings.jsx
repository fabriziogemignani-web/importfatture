import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader, Panel } from "@/components/common";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useCompany } from "@/context/CompanyContext";

const CompanyForm = ({ onDone }) => {
  const [vat, setVat] = useState("");
  const [name, setName] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/companies", { company_vat: vat, company_name: name });
      toast.success("P.IVA aggiunta");
      setVat("");
      setName("");
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row" data-testid="company-form">
      <Input required value={vat} onChange={(e) => setVat(e.target.value)} placeholder="P.IVA (es. 01234567890)" className="font-mono sm:w-56" data-testid="company-vat-input" />
      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ragione sociale" className="flex-1" data-testid="company-name-input" />
      <Button type="submit" data-testid="company-add-button"><Plus className="mr-2 h-4 w-4" />Aggiungi</Button>
    </form>
  );
};

const CompanyRow = ({ c, onDone }) => {
  const [name, setName] = useState(c.company_name);
  const [editing, setEditing] = useState(false);
  const act = async (fn, ok) => {
    try {
      await fn();
      toast.success(ok);
      setEditing(false);
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };
  return (
    <TableRow data-testid={`company-row-${c.company_vat}`}>
      <TableCell className="font-mono">{c.company_vat}</TableCell>
      <TableCell>
        {editing
          ? <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8" data-testid={`company-rename-input-${c.company_vat}`} />
          : c.company_name || "—"}
      </TableCell>
      <TableCell className="text-right">
        {editing
          ? <Button size="sm" onClick={() => act(() => api.patch(`/companies/${c.company_vat}`, { company_name: name }), "Ragione sociale aggiornata")} data-testid={`company-rename-save-${c.company_vat}`}>Salva</Button>
          : <Button size="sm" variant="ghost" onClick={() => setEditing(true)} data-testid={`company-rename-${c.company_vat}`}><Pencil className="h-4 w-4" /></Button>}
        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => act(() => api.delete(`/companies/${c.company_vat}`), "P.IVA eliminata")} data-testid={`company-delete-${c.company_vat}`}><Trash2 className="h-4 w-4" /></Button>
      </TableCell>
    </TableRow>
  );
};

export default function Settings() {
  const { user } = useAuth();
  const { companies, current, reload } = useCompany();
  const isAdmin = user?.role === "admin";

  return (
    <div>
      <PageHeader eyebrow="Configurazione" title="Impostazioni" />
      {isAdmin ? (
        <Panel className="fade-up overflow-hidden" data-testid="companies-panel">
          <div className="p-4">
            <div className="text-sm font-semibold">P.IVA gestite</div>
            <p className="mt-1 text-xs text-slate-500">Ogni utente è collegato a una P.IVA e vede solo i suoi dati. Se la P.IVA è il cedente la fattura è <b>attiva</b>, se è il cessionario è <b>passiva</b>; altrimenti viene scartata.</p>
          </div>
          <CompanyForm onDone={reload} />
          <Table>
            <TableHeader><TableRow className="bg-slate-50"><TableHead>P.IVA</TableHead><TableHead>Ragione sociale</TableHead><TableHead className="text-right">Azioni</TableHead></TableRow></TableHeader>
            <TableBody>{(companies || []).map((c) => <CompanyRow key={c.company_vat} c={c} onDone={reload} />)}</TableBody>
          </Table>
        </Panel>
      ) : (
        <Panel className="fade-up max-w-xl p-6" data-testid="settings-readonly">
          <div className="font-mono text-[11px] uppercase tracking-wider text-slate-500">La tua azienda</div>
          <div className="mt-2 text-lg font-semibold">{current?.company_name || "—"}</div>
          <div className="font-mono text-sm">P.IVA {current?.company_vat || "non assegnata"}</div>
          <p className="mt-4 text-xs text-slate-500">La P.IVA è assegnata dall'amministratore.</p>
        </Panel>
      )}
    </div>
  );
}
