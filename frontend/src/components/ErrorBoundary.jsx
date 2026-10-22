/**
 * ErrorBoundary — Recoverable React Error Boundary for Van Setu Studio Panels.
 *
 * Ensures that an isolated rendering or WebGL/Leaflet exception in any studio
 * panel displays a clean diagnostic recovery card with a one-click "Recover Panel"
 * button rather than crashing the entire application to a blank screen.
 */

import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error(
      `[VanSetu ErrorBoundary: ${this.props.panelName || 'Component'}]`,
      error,
      errorInfo
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    if (typeof this.props.onRecover === 'function') {
      this.props.onRecover();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="studio-error-boundary-card"
          role="alert"
          data-testid={`error-boundary-${this.props.panelName || 'panel'}`}
          style={{
            padding: '18px',
            margin: '12px',
            borderRadius: '12px',
            background: 'rgba(15, 23, 42, 0.94)',
            border: '1px solid rgba(239, 68, 68, 0.45)',
            color: '#f8fafc',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              marginBottom: '8px',
            }}
          >
            <strong style={{ color: '#fca5a5', fontSize: '13px' }}>
              ⚠️ {this.props.panelName || 'Studio Panel'} encountered a display error
            </strong>
            <button
              type="button"
              onClick={this.handleRetry}
              style={{
                background: 'linear-gradient(135deg, #0284c7, #00f2fe)',
                color: '#081426',
                border: 'none',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '11.5px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ↺ Recover Panel
            </button>
          </div>
          <p style={{ fontSize: '12px', color: '#cbd5e1', margin: 0 }}>
            {this.state.error?.message ||
              'An unexpected rendering issue occurred. Click Recover Panel to restore this section.'}
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}
