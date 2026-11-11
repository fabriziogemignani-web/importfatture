import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, formatApiError } from "@/lib/api";

const EMPTY = { cliente_piva: "", cliente_nome: "", protocollo: "", data: "", anno: new Date().getFullYear(), plafond: "", data_revoca: "", note: "" };

const Field = ({ id, label, children }) => (
  <div className="space-y-1.5"><Label htmlFor={id}>{label}</Label>{children}</div>
);

const useClienti = (open) => {
  const [clienti, setClienti] = useState([]);
  useEffect(() => {
    if (open) {
      api.get("/anagrafiche", { params: { ruolo: "cliente" } }).then((r) => setClienti(r.data)).catch(() => setClienti([]));
    }
  }, [open]);
  return clienti;
};

export const DichiarazioneDialog = ({ open, onOpenChange, initial, onSaved }) => {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const clienti = useClienti(open);
  useEffect(() => {
    if (open) {
      setF(initial ? { ...EMPTY, ...initial, data_revoca: initial.data_revoca || "" } : EMPTY);
    }
  }, [open, initial]);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  const pickCliente = (id) => {
    const c = clienti.find((x) => x.id === id);
    if (c) setF((s) => ({ ...s, cliente_piva: c.chiave, cliente_nome: c.denominazione }));
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const body = { ...f, anno: Number(f.anno), plafond: Number(String(f.plafond).replace(",", ".")), data_revoca: f.data_revoca || null };
      if (initial?.id) await api.put(`/dichiarazioni/${initial.id}`, body);
      else await api.post("/dichiarazioni", body);
      toast.success("Dichiarazione salvata");
      onSaved();
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="dich-dialog">
        <DialogHeader><DialogTitle>{initial?.id ? "Modifica dichiarazione" : "Nuova dichiarazione d'intento"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field id="cliente-pick" label="Cliente in anagrafica (facoltativo)">
              <Select onValueChange={pickCliente}>
                <SelectTrigger id="cliente-pick" data-testid="dich-cliente-select"><SelectValue placeholder="Scegli un cliente per compilare i dati" /></SelectTrigger>
                <SelectContent>
                  {clienti.map((c) => <SelectItem key={c.id} value={c.id} data-testid={`dich-cliente-option-${c.chiave}`}>{c.denominazione} · {c.chiave}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
          </div>
          <Field id="cliente_nome" label="Ragione sociale cliente"><Input id="cliente_nome" required value={f.cliente_nome} onChange={set("cliente_nome")} data-testid="dich-cliente-nome" /></Field>
          <Field id="cliente_piva" label="P.IVA cliente"><Input id="cliente_piva" required value={f.cliente_piva} onChange={set("cliente_piva")} data-testid="dich-cliente-piva" /></Field>
          <div className="sm:col-span-2">
            <Field id="protocollo" label="Protocollo di ricezione (Agenzia delle Entrate)">
              <Input id="protocollo" required className="font-mono" placeholder="24010312345678901-000001" value={f.protocollo} onChange={set("protocollo")} data-testid="dich-protocollo" />
            </Field>
          </div>
          <Field id="data" label="Data ricevuta telematica"><Input id="data" type="date" required value={f.data} onChange={set("data")} data-testid="dich-data" /></Field>
          <Field id="anno" label="Anno di validità"><Input id="anno" type="number" required value={f.anno} onChange={set("anno")} data-testid="dich-anno" /></Field>
          <Field id="plafond" label="Importo plafond (€)"><Input id="plafond" required inputMode="decimal" value={f.plafond} onChange={set("plafond")} data-testid="dich-plafond" /></Field>
          <Field id="data_revoca" label="Data revoca (se revocata)"><Input id="data_revoca" type="date" value={f.data_revoca} onChange={set("data_revoca")} data-testid="dich-data-revoca" /></Field>
          <div className="sm:col-span-2"><Field id="note" label="Note"><Textarea id="note" value={f.note} onChange={set("note")} data-testid="dich-note" /></Field></div>
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="dich-cancel">Annulla</Button>
            <Button type="submit" disabled={busy} data-testid="dich-save">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Salva</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
