import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Optional fallback. Renders the default dark fallback if omitted. */
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary] Uncaught render error:", error, info.componentStack);
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    const msg = this.state.error?.message ?? "An unexpected error occurred.";
    const isBackendError =
      msg.toLowerCase().includes("backend unreachable") ||
      msg.toLowerCase().includes("failed to fetch");

    return (
      <div
        className="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-6 px-6"
        style={{ background: "#0B0F14" }}
      >
        <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <AlertTriangle className="w-7 h-7 text-red-400" />
        </div>

        <div className="text-center max-w-md">
          <p className="text-white font-semibold text-lg mb-2">
            {isBackendError ? "Backend unreachable" : "Something went wrong"}
          </p>
          <p className="text-gray-400 text-sm leading-relaxed">{msg}</p>
          {isBackendError && (
            <p className="text-gray-500 text-xs mt-3">
              Make sure the API server is running at{" "}
              <code className="text-gray-300 bg-white/5 px-1 py-0.5 rounded">
                localhost:8000
              </code>{" "}
              and refresh.
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 border border-white/10 text-sm text-white transition-colors"
          >
            Try again
          </button>
          <button
            onClick={this.handleReload}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-gray-300 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reload
          </button>
        </div>
      </div>
    );
  }
}
