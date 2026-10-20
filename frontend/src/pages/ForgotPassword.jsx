import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, formatApiError } from "@/lib/api";

export const AuthShell = ({ children }) => (
  <div className="grid-bg flex min-h-screen items-center justify-center bg-slate-50 p-6">
    <div className="fade-up w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">{children}</div>
  </div>
);

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState("");
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/auth/forgot-password", { email });
      setSent(data.message);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell>
      <Link to="/login" className="mb-6 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900" data-testid="forgot-back-link"><ArrowLeft size={16} /> Torna al login</Link>
      <h1 className="text-2xl font-bold tracking-tight">Password dimenticata</h1>
      {sent ? (
        <div className="mt-5 flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800" data-testid="forgot-success">
          <MailCheck className="h-5 w-5 shrink-0" /> {sent}
        </div>
      ) : (
        <form onSubmit={submit} className="mt-5 space-y-4" data-testid="forgot-form">
          <p className="text-sm text-slate-500">Inserisci la tua email: ti invieremo un link per reimpostare la password.</p>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email-input" />
          </div>
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="forgot-error">{error}</div>}
          <Button type="submit" className="w-full" disabled={busy} data-testid="forgot-submit-button">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Invia link
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
