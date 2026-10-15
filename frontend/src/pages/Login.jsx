import { useState } from "react";
import { Navigate } from "react-router-dom";
import { FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="grid-bg relative hidden flex-col justify-between bg-slate-50 p-12 lg:flex">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-slate-900 text-white"><FileText size={18} /></div>
          <span className="font-extrabold">Archivio Fatture</span>
        </div>
        <div className="max-w-md">
          <div className="font-mono text-xs uppercase tracking-wider text-slate-500">FatturaPA · XML · P7M · ZIP</div>
          <h1 className="mt-3 text-5xl font-bold leading-tight tracking-tight">Le tue fatture elettroniche, ordinate per protocollo.</h1>
          <p className="mt-4 text-slate-600">Attive e passive divise per anno, anagrafiche clienti e fornitori generate automaticamente, ricerca istantanea.</p>
        </div>
        <div className="font-mono text-xs text-slate-400">Accesso riservato</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="fade-up w-full max-w-sm space-y-5" data-testid="login-form">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Accedi</h2>
            <p className="mt-1 text-sm text-slate-500">Inserisci le tue credenziali per continuare.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email-input" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password-input" />
          </div>
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="login-error">{error}</div>}
          <Button type="submit" className="w-full" disabled={busy} data-testid="login-submit-button">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Accedi
          </Button>
        </form>
      </div>
    </div>
  );
}
