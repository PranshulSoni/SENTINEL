import { StrictMode, Component, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      const err = this.state.error as Error;
      return (
        <div style={{ background: '#000', color: '#ef4444', fontFamily: 'monospace', padding: '2rem', minHeight: '100vh' }}>
          <h1 style={{ fontSize: '1rem', marginBottom: '1rem' }}>⚠ SENTINEL — RENDER ERROR</h1>
          <pre style={{ fontSize: '0.75rem', color: '#a1a1aa', whiteSpace: 'pre-wrap' }}>{err.message}\n\n{err.stack}</pre>
          <button onClick={() => this.setState({ error: null })} style={{ marginTop: '1rem', padding: '0.5rem 1rem', border: '1px solid #ef4444', background: 'transparent', color: '#ef4444', cursor: 'pointer', fontFamily: 'monospace' }}>
            RETRY
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
