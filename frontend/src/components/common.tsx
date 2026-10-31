import { Component, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { Volume2 } from "lucide-react";
import { speak, t } from "../lib/i18n";

/** Big "listen" button; plays once automatically when the text changes (one new step = one prompt). */
export function PlayButton({ text, auto = true }: { text: string; auto?: boolean }) {
  useEffect(() => {
    if (auto) speak(text);
  }, [text, auto]);
  return (
    <button type="button" className="play" onClick={() => speak(text)}>
      <Volume2 aria-hidden="true" size={28} /> {t("common.play")}
    </button>
  );
}

type Async<T> = { data: T | null; error: string | null; loading: boolean; reload: () => void; setData: (d: T) => void };

/** Fetch on mount and whenever `deps` change; ignores responses from superseded requests. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  const seq = useRef(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps);
  const reload = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true }));
    run().then(
      (data) => id === seq.current && setState({ data, error: null, loading: false }),
      (e: Error) => id === seq.current && setState((s) => ({ ...s, error: e.message, loading: false })),
    );
  }, [run]);
  useEffect(reload, [reload]);
  const setData = useCallback((data: T) => setState({ data, error: null, loading: false }), []);
  return { ...state, reload, setData };
}

export function ErrorNotice({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="notice notice-error row spread" role="alert">
      <span>{t("common.error", { detail: error })}</span>
      {onRetry && <button type="button" className="btn" onClick={onRetry}>{t("common.retry")}</button>}
    </div>
  );
}

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <main className="walk">
          <ErrorNotice error={this.state.error.message} onRetry={() => location.reload()} />
        </main>
      );
    }
    return this.props.children;
  }
}

export function Skeleton({ height = 120 }: { height?: number }) {
  return <div className="skeleton" style={{ height }} aria-hidden="true" />;
}
