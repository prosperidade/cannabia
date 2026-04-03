"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "./button";

type ErrorBoundaryProps = {
  children: ReactNode;
  /** Optional fallback render. Receives error and reset fn. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
};

type ErrorBoundaryState = {
  error: Error | null;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback(error, this.reset);
    }

    return (
      <div className="ds-error-fallback" role="alert">
        <div className="ds-error-fallback__icon" aria-hidden="true">!</div>
        <h2 className="ds-error-fallback__title">Algo deu errado</h2>
        <p className="ds-error-fallback__desc">
          Ocorreu um erro inesperado nesta seção. Você pode tentar recarregar
          ou voltar à página anterior.
        </p>
        <div style={{ display: "flex", gap: "12px" }}>
          <Button onClick={this.reset} variant="primary" size="sm">
            Tentar novamente
          </Button>
          <Button
            onClick={() => window.location.assign("/dashboard")}
            variant="secondary"
            size="sm"
          >
            Voltar ao dashboard
          </Button>
        </div>
      </div>
    );
  }
}
