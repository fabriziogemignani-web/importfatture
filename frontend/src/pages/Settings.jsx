import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader, Panel } from "@/components/common";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function Settings() {
  const { user } = useAuth();
  const readOnly = user?.role !== "admin";
  const [vat, setVat] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => {
      setVat(r.data.company_vat);
      setName(r.data.company_name);
    });
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.put("/settings", { company_vat: vat, company_name: name });
      setVat(data.company_vat);
      toast.success("Impostazioni salvate");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader eyebrow="Configurazione" title="Impostazioni" />
      <Panel className="fade-up max-w-xl p-6">
        <form onSubmit={save} className="space-y-5" data-testid="settings-form">
          {readOnly && <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800" data-testid="settings-readonly">Solo un amministratore può modificare le impostazioni.</div>}
          <fieldset disabled={readOnly} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="name">Ragione sociale azienda</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} data-testid="settings-company-name-input" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="vat">P.IVA azienda</Label>
            <Input id="vat" required value={vat} onChange={(e) => setVat(e.target.value)} className="font-mono" placeholder="es. 01234567890" data-testid="settings-vat-input" />
            <p className="text-xs text-slate-500">Se la tua azienda è il cedente/prestatore la fattura è <b>attiva</b>, altrimenti è <b>passiva</b>. La classificazione si applica alle fatture caricate da ora in poi.</p>
          </div>
          <Button type="submit" disabled={busy} data-testid="settings-save-button">Salva</Button>
          </fieldset>
        </form>
      </Panel>
    </div>
  );
}
