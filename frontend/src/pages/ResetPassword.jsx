import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, formatApiError } from "@/lib/api";
import { AuthShell } from "@/pages/ForgotPassword";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) return setError("La password deve avere almeno 8 caratteri");
    if (password !== confirm) return setError("Le password non coincidono");
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      setDone(true);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold tracking-tight">Nuova password</h1>
      {done ? (
        <div className="mt-5 space-y-4" data-testid="reset-success">
          <div className="flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            <CheckCircle2 className="h-5 w-5 shrink-0" /> Password aggiornata. Ora puoi accedere.
          </div>
          <Button asChild className="w-full" data-testid="reset-go-login"><Link to="/login">Vai al login</Link></Button>
        </div>
      ) : !token ? (
        <p className="mt-4 text-sm text-red-700" data-testid="reset-missing-token">Link non valido. <Link to="/password-dimenticata" className="underline">Richiedine uno nuovo</Link>.</p>
      ) : (
        <form onSubmit={submit} className="mt-5 space-y-4" data-testid="reset-form">
          <div className="space-y-2">
            <Label htmlFor="pw">Nuova password</Label>
            <Input id="pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="reset-password-input" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pw2">Conferma password</Label>
            <Input id="pw2" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} data-testid="reset-confirm-input" />
          </div>
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="reset-error">{error}</div>}
          <Button type="submit" className="w-full" disabled={busy} data-testid="reset-submit-button">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Salva password
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
