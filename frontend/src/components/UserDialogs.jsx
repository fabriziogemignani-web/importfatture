import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { ChevronDown } from "lucide-react";
import { useCompany } from "@/context/CompanyContext";

const EMPTY = { email: "", name: "", role: "user", password: "", company_vats: [] };

export const VatMultiSelect = ({ value, onChange, testid, className = "" }) => {
  const { companies } = useCompany();
  const toggle = (vat) => onChange(value.includes(vat) ? value.filter((v) => v !== vat) : [...value, vat]);
  const label = value.length === 0 ? "Nessuna" : value.length === 1
    ? ((companies || []).find((c) => c.company_vat === value[0])?.company_name || value[0])
    : `${value.length} P.IVA`;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" className={`justify-between font-normal ${className}`} data-testid={testid}>
          <span className="truncate">{label}</span><ChevronDown className="ml-2 h-4 w-4 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-2" align="start">
        {(companies || []).length === 0 && <div className="p-2 text-sm text-slate-500">Nessuna P.IVA in archivio</div>}
        {(companies || []).map((c) => (
          <label key={c.company_vat} className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-slate-50">
            <Checkbox checked={value.includes(c.company_vat)} onCheckedChange={() => toggle(c.company_vat)} data-testid={`${testid}-option-${c.company_vat}`} />
            <span className="min-w-0">
              <span className="block truncate text-sm">{c.company_name || c.company_vat}</span>
              <span className="block font-mono text-[10px] text-slate-500">{c.company_vat}</span>
            </span>
          </label>
        ))}
      </PopoverContent>
    </Popover>
  );
};

export const NewUserDialog = ({ open, onOpenChange, onSubmit }) => {
  const [form, setForm] = useState(EMPTY);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target ? e.target.value : e });
  const submit = async (e) => {
    e.preventDefault();
    if (await onSubmit(form)) setForm(EMPTY);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="new-user-dialog">
        <DialogHeader><DialogTitle>Nuovo utente</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Nome</Label><Input value={form.name} onChange={set("name")} data-testid="new-user-name-input" /></div>
          <div className="space-y-2"><Label>Email</Label><Input type="email" required value={form.email} onChange={set("email")} data-testid="new-user-email-input" /></div>
          <div className="space-y-2">
            <Label>Ruolo</Label>
            <Select value={form.role} onValueChange={set("role")}>
              <SelectTrigger data-testid="new-user-role-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="user" data-testid="role-option-user">Utente</SelectItem>
                <SelectItem value="admin" data-testid="role-option-admin">Amministratore</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>P.IVA collegate {form.role === "admin" && "(facoltative)"}</Label>
            <VatMultiSelect value={form.company_vats} onChange={(company_vats) => setForm({ ...form, company_vats })} testid="new-user-vat-select" className="w-full" />
          </div>
          <div className="space-y-2"><Label>Password iniziale (min. 8 caratteri)</Label><Input type="password" required minLength={8} value={form.password} onChange={set("password")} data-testid="new-user-password-input" /></div>
          <DialogFooter><Button type="submit" data-testid="new-user-submit">Crea utente</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export const PasswordDialog = ({ user, onOpenChange, onSubmit }) => {
  const [pw, setPw] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (await onSubmit(pw)) setPw("");
  };
  return (
    <Dialog open={!!user} onOpenChange={onOpenChange}>
      <DialogContent data-testid="password-dialog">
        <DialogHeader><DialogTitle>Imposta password per {user?.email}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Nuova password (min. 8 caratteri)</Label><Input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} data-testid="set-password-input" /></div>
          <DialogFooter><Button type="submit" data-testid="set-password-submit">Salva</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
