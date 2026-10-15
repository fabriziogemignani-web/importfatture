import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Layout } from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Invoices from "@/pages/Invoices";
import InvoiceDetail from "@/pages/InvoiceDetail";
import Anagrafiche from "@/pages/Anagrafiche";
import AnagraficaDetail from "@/pages/AnagraficaDetail";
import Upload from "@/pages/Upload";
import Settings from "@/pages/Settings";

const Protected = ({ children }) => {
  const { user } = useAuth();
  if (user === null) {
    return <div className="min-h-screen grid place-items-center text-slate-500" data-testid="auth-loading">Caricamento…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/attive" element={<Invoices tipo="attiva" />} />
            <Route path="/passive" element={<Invoices tipo="passiva" />} />
            <Route path="/fatture/:id" element={<InvoiceDetail />} />
            <Route path="/anagrafiche" element={<Anagrafiche />} />
            <Route path="/anagrafiche/:id" element={<AnagraficaDetail />} />
            <Route path="/carica" element={<Upload />} />
            <Route path="/impostazioni" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AuthProvider>
  );
}

export default App;
