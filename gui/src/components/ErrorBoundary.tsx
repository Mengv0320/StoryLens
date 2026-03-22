import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props { children: ReactNode }
interface State { hasError: boolean; error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-8 text-center">
          <h1 className="text-2xl font-semibold text-danger">页面渲染出错</h1>
          <p className="text-txt-soft max-w-md">{this.state.error?.message || "发生未知错误"}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:opacity-90 transition-opacity"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/**
 * PageErrorBoundary - a reusable error boundary for individual pages/sections.
 * Unlike the top-level ErrorBoundary which catches everything, this one renders
 * a localized error UI so only the affected section is replaced, not the whole app.
 */
interface PageErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
}
interface PageErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class PageErrorBoundary extends Component<PageErrorBoundaryProps, PageErrorBoundaryState> {
  state: PageErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): PageErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[PageErrorBoundary]", error, info.componentStack);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center gap-4 p-8 text-center min-h-[200px]">
          <h2 className="text-lg font-semibold text-danger">
            {this.props.fallbackTitle || "此区域加载出错"}
          </h2>
          <p className="text-txt-soft text-sm max-w-md">
            {this.state.error?.message || "发生未知错误，请尝试重试。"}
          </p>
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:opacity-90 transition-opacity"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
