import { useEffect, useState } from "react";
import { KeyRound, Trash2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { PageHeader, Panel } from "@/components/common";
import { NewUserDialog, PasswordDialog } from "@/components/UserDialogs";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { useCompany } from "@/context/CompanyContext";

const NONE = "__none__";

const VatSelect = ({ value, onChange, testid, allowNone }) => {
  const { companies } = useCompany();
  return (
    <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? "" : v)}>
      <SelectTrigger className="h-8 w-52" data-testid={testid}><SelectValue /></SelectTrigger>
      <SelectContent>
        {allowNone && <SelectItem value={NONE}>Nessuna</SelectItem>}
        {(companies || []).map((c) => <SelectItem key={c.company_vat} value={c.company_vat}>{c.company_name || c.company_vat} · {c.company_vat}</SelectItem>)}
      </SelectContent>
    </Select>
  );
};
export { VatSelect };

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [creating, setCreating] = useState(false);
  const [pwUser, setPwUser] = useState(null);

  const load = () => api.get("/users").then((r) => setUsers(r.data));
  useEffect(() => {
    load();
  }, []);

  const call = async (fn, ok) => {
    try {
      await fn();
      toast.success(ok);
      load();
      return true;
    } catch (e) {
      toast.error(formatApiError(e));
      return false;
    }
  };
  const create = async (form) => (await call(() => api.post("/users", form), "Utente creato")) && (setCreating(false), true);
  const update = (u, changes) => call(() => api.patch(`/users/${u.id}`, changes), "Utente aggiornato");
  const setPassword = async (pw) => (await call(() => api.post(`/users/${pwUser.id}/password`, { password: pw }), "Password aggiornata")) && (setPwUser(null), true);
  const remove = (u) => call(() => api.delete(`/users/${u.id}`), "Utente eliminato");

  return (
    <div>
      <PageHeader eyebrow="Amministrazione" title="Gestione utenti">
        <Button onClick={() => setCreating(true)} data-testid="new-user-button"><UserPlus className="mr-2 h-4 w-4" />Nuovo utente</Button>
      </PageHeader>
      <Panel className="fade-up overflow-x-auto">
        <Table data-testid="users-table">
          <TableHeader><TableRow className="bg-slate-50">
            <TableHead>Nome</TableHead><TableHead>Email</TableHead><TableHead>P.IVA</TableHead><TableHead>Ruolo</TableHead><TableHead>Attivo</TableHead><TableHead className="text-right">Azioni</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id} data-testid={`user-row-${u.email}`}>
                <TableCell className="font-medium">{u.name || "—"} {u.id === me?.id && <span className="ml-1 text-xs text-slate-400">(tu)</span>}</TableCell>
                <TableCell className="font-mono text-xs">{u.email}</TableCell>
                <TableCell><VatSelect value={u.company_vat} allowNone={u.role === "admin"} onChange={(company_vat) => update(u, { company_vat })} testid={`user-vat-select-${u.email}`} /></TableCell>
                <TableCell>
                  <Select value={u.role} onValueChange={(role) => update(u, { role })} disabled={u.id === me?.id}>
                    <SelectTrigger className="h-8 w-40" data-testid={`user-role-select-${u.email}`}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">Utente</SelectItem>
                      <SelectItem value="admin">Amministratore</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell><Switch checked={u.active} disabled={u.id === me?.id} onCheckedChange={(active) => update(u, { active })} data-testid={`user-active-switch-${u.email}`} /></TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="ghost" onClick={() => setPwUser(u)} data-testid={`user-password-button-${u.email}`}><KeyRound className="h-4 w-4" /></Button>
                  {u.id !== me?.id && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild><Button size="sm" variant="ghost" className="text-red-600" data-testid={`user-delete-button-${u.email}`}><Trash2 className="h-4 w-4" /></Button></AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader><AlertDialogTitle>Eliminare {u.email}?</AlertDialogTitle><AlertDialogDescription>L'utente non potrà più accedere. Le fatture restano in archivio.</AlertDialogDescription></AlertDialogHeader>
                        <AlertDialogFooter><AlertDialogCancel>Annulla</AlertDialogCancel><AlertDialogAction onClick={() => remove(u)} data-testid="user-delete-confirm">Elimina</AlertDialogAction></AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
      <NewUserDialog open={creating} onOpenChange={setCreating} onSubmit={create} />
      <PasswordDialog user={pwUser} onOpenChange={(o) => !o && setPwUser(null)} onSubmit={setPassword} />
    </div>
  );
}
