import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, CopyCheck, UploadCloud, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";
import { PageHeader, Panel, TipoBadge } from "@/components/common";
import { api, formatApiError } from "@/lib/api";

const BATCH = 10;
const ICON = {
  ok: <CheckCircle2 className="h-4 w-4 text-emerald-600" />,
  duplicate: <CopyCheck className="h-4 w-4 text-amber-600" />,
  error: <XCircle className="h-4 w-4 text-red-600" />,
};

export default function Upload() {
  const input = useRef(null);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState(null);
  const [results, setResults] = useState([]);

  const handle = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setResults([]);
    setProgress(0);
    for (let i = 0; i < files.length; i += BATCH) {
      const fd = new FormData();
      files.slice(i, i + BATCH).forEach((f) => fd.append("files", f));
      try {
        const { data } = await api.post("/invoices/upload", fd);
        setResults((prev) => [...prev, ...data.results]);
      } catch (e) {
        toast.error(formatApiError(e));
        break;
      }
      setProgress(Math.round((Math.min(i + BATCH, files.length) / files.length) * 100));
    }
    setProgress(null);
    if (input.current) input.current.value = "";
  };

  const count = (s) => results.filter((r) => r.status === s).length;

  return (
    <div>
      <PageHeader eyebrow="Importazione massiva" title="Carica fatture" />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files); }}
        onClick={() => input.current?.click()}
        data-testid="upload-dropzone"
        className={`fade-up grid-bg flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-14 text-center transition-colors ${drag ? "border-slate-900 bg-slate-100" : "border-slate-300 bg-white hover:border-slate-500"}`}>
        <div className="grid h-14 w-14 place-items-center rounded-xl bg-slate-900 text-white"><UploadCloud /></div>
        <div className="mt-4 text-lg font-semibold">Trascina qui i file o clicca per selezionarli</div>
        <div className="mt-1 text-sm text-slate-500">Supporta <span className="font-mono">.xml</span>, <span className="font-mono">.xml.p7m</span> e archivi <span className="font-mono">.zip</span> — anche centinaia di file insieme</div>
        <input ref={input} type="file" multiple accept=".xml,.p7m,.zip" className="hidden" onChange={(e) => handle(e.target.files)} data-testid="upload-file-input" />
      </div>
      {progress !== null && <div className="mt-5" data-testid="upload-progress"><Progress value={progress} /><div className="mt-1 text-xs text-slate-500">Elaborazione… {progress}%</div></div>}
      {results.length > 0 && (
        <Panel className="mt-6 overflow-hidden" data-testid="upload-results">
          <div className="flex flex-wrap gap-4 border-b border-slate-200 p-4 text-sm" data-testid="upload-summary">
            <span className="text-emerald-700"><b data-testid="upload-count-ok">{count("ok")}</b> importate</span>
            <span className="text-amber-700"><b data-testid="upload-count-duplicate">{count("duplicate")}</b> duplicate</span>
            <span className="text-red-700"><b data-testid="upload-count-error">{count("error")}</b> errori</span>
          </div>
          <ul className="max-h-[50vh] divide-y divide-slate-100 overflow-auto">
            {results.map((r, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-2.5 text-sm" data-testid={`upload-result-${i}`}>
                {ICON[r.status]}
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{r.filename}</span>
                {r.tipo && <TipoBadge tipo={r.tipo} />}
                {r.numero && <span className="font-mono text-xs">N. {r.numero}</span>}
                <span className="hidden text-xs text-slate-500 sm:inline">{r.message}</span>
                {r.id && <Link to={`/fatture/${r.id}`} className="text-xs font-semibold underline">Apri</Link>}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
