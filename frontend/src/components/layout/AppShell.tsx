import React, { ReactNode, useState, useEffect } from 'react';
import { Activity, Map as MapIcon, MessageSquare, Sun, Moon } from 'lucide-react';
import { useFeedStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';
import { useTheme } from '../../hooks/useTheme';
import OperatorDropdown from './OperatorDropdown';

interface AppShellProps {
  leftPanel: ReactNode;
  centerPanel: ReactNode;
  rightPanel: ReactNode;
}

const AppShell: React.FC<AppShellProps> = ({ leftPanel, centerPanel, rightPanel }) => {
  const [currentTime, setCurrentTime] = useState(new Date());
  const { city, switchCity, fetchCityInfo, fetchBaselines, lastUpdate } = useFeedStore();
  const { fetchIncidents, currentIncident } = useIncidentStore();
  const [notification, setNotification] = useState<string | null>(null);
  const { isDark, toggleTheme } = useTheme();

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    fetchCityInfo();
    fetchBaselines();
    fetchIncidents().then(() => {
      const state = useIncidentStore.getState();
      const active = state.incidents
        .filter((i) => i.status !== 'resolved')
        .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());
      if (active.length > 0 && !state.currentIncident) {
        state.setIncident(active[0]);
        api.getLLMOutput(active[0].id).then((llm) => {
          if (llm && typeof llm === 'object') {
            useIncidentStore.getState().setLLMOutput(llm);
          }
        }).catch(() => {});
      }
    });
  }, [fetchCityInfo, fetchBaselines, fetchIncidents]);

  useEffect(() => {
    if (currentIncident) {
      setNotification(`INCIDENT: ${currentIncident.severity.toUpperCase()} · ${currentIncident.on_street}`);
      const timer = setTimeout(() => setNotification(null), 6000);
      return () => clearTimeout(timer);
    }
  }, [currentIncident?.id]);

  const isConnected = (() => {
    if (!lastUpdate) return false;
    return Date.now() - new Date(lastUpdate).getTime() < 10_000;
  })();

  const formatTime = (d: Date) =>
    d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const formatDate = (d: Date) =>
    d.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: '2-digit' }).toUpperCase();

  return (
    <div
      className="flex flex-col h-screen w-screen overflow-hidden"
      style={{ background: 'var(--color-bg)', color: 'var(--color-text)' }}
    >
      {/* ═══ HEADER ═══ */}
      <header
        className="h-12 flex items-center justify-between px-5 shrink-0"
        style={{
          background: 'var(--color-surface)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        {/* Left: Wordmark + status */}
        <div className="flex items-center gap-4">
          <span
            className="text-sm font-black uppercase tracking-[0.22em]"
            style={{ color: 'var(--color-text)', letterSpacing: '0.22em' }}
          >
            SENTINEL
          </span>
          <span
            className="h-[5px] w-[5px] inline-block"
            style={{ background: isConnected ? 'var(--color-success)' : 'var(--color-text-secondary)' }}
            title={isConnected ? 'Live feed connected' : 'No live data'}
          />
          {currentIncident && (
            <span
              className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider font-mono"
              style={{
                background: 'var(--color-danger)',
                color: '#fff',
              }}
            >
              1 ACTIVE
            </span>
          )}
        </div>

        {/* Center: City switcher */}
        <div className="flex items-center" style={{ borderLeft: '1px solid var(--color-border)', borderRight: '1px solid var(--color-border)' }}>
          {(['nyc', 'chandigarh'] as const).map((c, i) => (
            <button
              key={c}
              onClick={() => switchCity(c)}
              className="px-5 h-12 text-[11px] font-bold uppercase tracking-[0.12em] transition-colors duration-150"
              style={{
                background: city === c ? 'var(--color-accent)' : 'transparent',
                color: city === c ? '#fff' : 'var(--color-text-secondary)',
                borderLeft: i > 0 ? '1px solid var(--color-border)' : 'none',
              }}
            >
              {c === 'nyc' ? 'New York' : 'Chandigarh'}
            </button>
          ))}
        </div>

        {/* Right: Clock + theme toggle + operator */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end" style={{ gap: '1px' }}>
            <span className="text-sm font-mono" style={{ color: 'var(--color-text)', letterSpacing: '0.04em' }}>
              {formatTime(currentTime)}
            </span>
            <span className="text-[9px] font-mono uppercase" style={{ color: 'var(--color-text-secondary)' }}>
              {formatDate(currentTime)}
            </span>
          </div>

          <button
            onClick={toggleTheme}
            className="flex items-center justify-center h-7 w-7 transition-colors duration-200"
            style={{
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
              background: 'transparent',
            }}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          </button>

          <OperatorDropdown />
        </div>
      </header>

      {/* ═══ INCIDENT ALERT BANNER ═══ */}
      {notification && (
        <div
          className="h-8 flex items-center justify-center gap-3"
          style={{ background: 'var(--color-danger)' }}
        >
          <span
            className="h-[4px] w-[4px] inline-block"
            style={{ background: '#fff' }}
          />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] font-mono" style={{ color: '#fff' }}>
            {notification}
          </span>
        </div>
      )}

      {/* ═══ MAIN GRID ═══ */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left Panel */}
        <section
          className="w-[340px] flex flex-col overflow-hidden"
          style={{ borderRight: '1px solid var(--color-border)', background: 'var(--color-bg)' }}
        >
          <div
            className="h-9 px-4 flex items-center gap-2 shrink-0"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            <Activity className="h-3 w-3" style={{ color: 'var(--color-text-secondary)' }} />
            <h2
              className="text-[10px] font-bold uppercase tracking-[0.15em]"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              ACTION PANEL
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {leftPanel}
          </div>
        </section>

        {/* Center Panel: Map */}
        <section
          className="flex-1 relative flex flex-col overflow-hidden"
          style={{ background: 'var(--color-bg)' }}
        >
          {/* Map label */}
          <div
            className="absolute top-4 left-4 z-[1000] flex items-center gap-2 px-3 py-1.5 pointer-events-none"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <MapIcon className="h-3 w-3" style={{ color: 'var(--color-text-secondary)' }} />
            <span className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-secondary)' }}>
              SITUATION MAP
            </span>
          </div>

          {/* Legend */}
          <div
            className="absolute bottom-4 left-4 z-[1000] p-3 pointer-events-none"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div className="flex flex-col gap-2">
              {[
                { color: 'var(--color-danger)', label: 'INCIDENT / STOPPED' },
                { color: 'var(--color-warning)', label: 'SLOW / CONGESTED' },
              ].map(({ color, label }) => (
                <div key={label} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 shrink-0" style={{ background: color }} />
                  <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
                    {label}
                  </span>
                </div>
              ))}
              <div className="flex items-center gap-2">
                <div
                  className="w-2.5 border-t-2 border-dashed shrink-0"
                  style={{ borderColor: 'var(--color-text-secondary)' }}
                />
                <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
                  DIVERSION ROUTE
                </span>
              </div>
            </div>
          </div>

          {centerPanel}
        </section>

        {/* Right Panel: Chat */}
        <section
          className="w-[360px] flex flex-col overflow-hidden"
          style={{ borderLeft: '1px solid var(--color-border)', background: 'var(--color-bg)' }}
        >
          <div
            className="h-9 px-4 flex items-center gap-2 shrink-0"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            <MessageSquare className="h-3 w-3" style={{ color: 'var(--color-text-secondary)' }} />
            <h2
              className="text-[10px] font-bold uppercase tracking-[0.15em]"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              CO-PILOT CHAT
            </h2>
          </div>
          <div className="flex-1 overflow-hidden">
            {rightPanel}
          </div>
        </section>
      </main>
    </div>
  );
};

export default AppShell;
