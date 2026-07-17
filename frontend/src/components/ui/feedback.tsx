import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "../../lib/cn";

type ToastKind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}
interface ToastApi {
  success: (m: string) => void;
  error: (m: string) => void;
  info: (m: string) => void;
}
interface ConfirmOpts {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}
type ConfirmFn = (opts: ConfirmOpts) => Promise<boolean>;

const noopToast: ToastApi = { success: () => {}, error: () => {}, info: () => {} };
const ToastCtx = createContext<ToastApi>(noopToast);
const ConfirmCtx = createContext<ConfirmFn>(async () => false);

export const useToast = (): ToastApi => useContext(ToastCtx);
export const useConfirm = (): ConfirmFn => useContext(ConfirmCtx);

const KIND_META: Record<ToastKind, { icon: typeof Info; cls: string }> = {
  success: { icon: CheckCircle2, cls: "text-rw-success border-rw-success/30" },
  error: { icon: XCircle, cls: "text-rw-danger border-rw-danger/30" },
  info: { icon: Info, cls: "text-rw-accent border-rw-accent/30" },
};

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback(
    (id: number) => setToasts((t) => t.filter((x) => x.id !== id)),
    [],
  );
  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, kind, message }]);
      setTimeout(() => dismiss(id), 4500);
    },
    [dismiss],
  );
  const toast = useRef<ToastApi>({
    success: (m) => push("success", m),
    error: (m) => push("error", m),
    info: (m) => push("info", m),
  }).current;

  const [confirmState, setConfirmState] = useState<
    (ConfirmOpts & { resolve: (b: boolean) => void }) | null
  >(null);
  const confirm = useCallback<ConfirmFn>(
    (opts) => new Promise<boolean>((resolve) => setConfirmState({ ...opts, resolve })),
    [],
  );
  const closeConfirm = (val: boolean) => {
    setConfirmState((s) => {
      s?.resolve(val);
      return null;
    });
  };

  return (
    <ToastCtx.Provider value={toast}>
      <ConfirmCtx.Provider value={confirm}>
        {children}

        {/* Toast stack */}
        <div className="fixed top-4 right-4 z-[200] flex w-80 flex-col gap-2">
          {toasts.map((t) => {
            const { icon: Icon, cls } = KIND_META[t.kind];
            return (
              <div
                key={t.id}
                role="status"
                className={cn(
                  "animate-slide-in flex items-start gap-2.5 rounded-lg border bg-rw-elevated/95 px-3.5 py-3 shadow-lg backdrop-blur",
                  cls,
                )}
              >
                <Icon size={16} className="mt-0.5 shrink-0" />
                <p className="flex-1 text-sm text-rw-text">{t.message}</p>
                <button
                  onClick={() => dismiss(t.id)}
                  className="text-rw-dim transition-colors hover:text-rw-text"
                  aria-label="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}
        </div>

        {/* Confirm modal */}
        {confirmState && (
          <div
            className="animate-fade-in fixed inset-0 z-[210] flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => closeConfirm(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              className="animate-scale-in mx-4 w-full max-w-md rounded-xl border border-rw-border bg-rw-elevated p-5 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3">
                {confirmState.danger && (
                  <AlertTriangle size={20} className="mt-0.5 shrink-0 text-rw-danger" />
                )}
                <div className="flex-1">
                  <h3 className="text-base font-semibold text-rw-text">
                    {confirmState.title}
                  </h3>
                  {confirmState.message && (
                    <p className="mt-1.5 text-sm text-rw-muted">{confirmState.message}</p>
                  )}
                </div>
              </div>
              <div className="mt-5 flex justify-end gap-2">
                <button
                  onClick={() => closeConfirm(false)}
                  className="rounded-lg border border-rw-border px-4 py-2 text-sm text-rw-muted transition-colors hover:bg-rw-surface hover:text-rw-text"
                >
                  {confirmState.cancelLabel || "Cancel"}
                </button>
                <button
                  autoFocus
                  onClick={() => closeConfirm(true)}
                  className={cn(
                    "rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors",
                    confirmState.danger
                      ? "bg-rw-danger hover:bg-red-600"
                      : "bg-rw-accent hover:bg-rw-accent-hover",
                  )}
                >
                  {confirmState.confirmLabel || "Confirm"}
                </button>
              </div>
            </div>
          </div>
        )}
      </ConfirmCtx.Provider>
    </ToastCtx.Provider>
  );
}
