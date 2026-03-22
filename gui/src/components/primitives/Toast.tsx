import { useState, useCallback, useEffect } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

const STYLES = {
  success: "bg-success-soft text-success border-success/30",
  error: "bg-danger-soft text-danger border-danger/30",
  info: "bg-info-soft text-info border-info/30",
};

let _setToasts: React.Dispatch<React.SetStateAction<ToastItem[]>> | null = null;
let _counter = 0;

export function toast(message: string, type: ToastType = "info") {
  if (!_setToasts) return;
  const id = ++_counter;
  _setToasts((prev) => [...prev, { id, message, type }]);
  setTimeout(() => {
    _setToasts?.((prev) => prev.filter((t) => t.id !== id));
  }, 3000);
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    _setToasts = setToasts;
    return () => { _setToasts = null; };
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => {
        const Icon = ICONS[t.type];
        return (
          <div
            key={t.id}
            className={`flex items-center gap-2 px-4 py-3 rounded-lg border shadow-md text-sm font-medium pointer-events-auto max-w-xs ${STYLES[t.type]}`}
          >
            <Icon size={15} className="shrink-0" />
            <span className="flex-1">{t.message}</span>
            <button onClick={() => dismiss(t.id)} className="shrink-0 opacity-60 hover:opacity-100 transition-opacity">
              <X size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function useToast() {
  return { toast, ToastContainer };
}
