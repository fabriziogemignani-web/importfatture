import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useCompany } from "@/context/CompanyContext";

const EMPTY = { email: "", name: "", role: "user", password: "", company_vat: "" };

export const NewUserDialog = ({ open, onOpenChange, onSubmit }) => {
  const { companies } = useCompany();
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
            <Label>P.IVA collegata {form.role === "admin" && "(facoltativa)"}</Label>
            <Select value={form.company_vat || "__none__"} onValueChange={(v) => setForm({ ...form, company_vat: v === "__none__" ? "" : v })}>
              <SelectTrigger data-testid="new-user-vat-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Seleziona…</SelectItem>
                {(companies || []).map((c) => <SelectItem key={c.company_vat} value={c.company_vat} data-testid={`new-user-vat-option-${c.company_vat}`}>{c.company_name || c.company_vat} · {c.company_vat}</SelectItem>)}
              </SelectContent>
            </Select>
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
