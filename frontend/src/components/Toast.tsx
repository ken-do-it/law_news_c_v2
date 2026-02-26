import { createContext, useContext, useState, useCallback, useEffect } from 'react';

interface ToastItem {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ToastCtx {
  toast: (message: string, type?: ToastItem['type']) => void;
}

const Ctx = createContext<ToastCtx>({ toast: () => {} });

export function useToast() {
  return useContext(Ctx);
}

function ToastItem({ item, onDone }: { item: ToastItem; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3200);
    return () => clearTimeout(t);
  }, [onDone]);

  const styles = {
    success: 'bg-emerald-600',
    error: 'bg-red-600',
    info: 'bg-[var(--color-navy)]',
  };
  const icons = { success: '✓', error: '✕', info: 'ℹ' };

  return (
    <div
      className={`flex items-center gap-3 ${styles[item.type]} text-white px-4 py-3 rounded-xl shadow-2xl text-sm min-w-[260px] max-w-sm`}
    >
      <span className="font-bold shrink-0 w-4 text-center">{icons[item.type]}</span>
      <span className="flex-1">{item.message}</span>
      <button
        onClick={onDone}
        className="opacity-60 hover:opacity-100 shrink-0 ml-1 leading-none"
      >
        ✕
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, type: ToastItem['type'] = 'success') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 items-end">
        {toasts.map((t) => (
          <ToastItem key={t.id} item={t} onDone={() => remove(t.id)} />
        ))}
      </div>
    </Ctx.Provider>
  );
}
