import React, { ReactNode, useState, useEffect } from 'react';
import { ShieldAlert, Activity, Map as MapIcon, MessageSquare, Bell } from 'lucide-react';
import { useFeedStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';

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
      setNotification(`🚨 INCIDENT DETECTED: ${currentIncident.severity.toUpperCase()} at ${currentIncident.on_street}`);
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
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-scada-bg">
      {/* ═══ MINIMAL TOP BAR ═══ */}
      <header className="h-10 border-b flex items-center justify-between px-4 bg-scada-panel border-scada-border">
        {/* Left: Logo */}
        <div className="flex items-center gap-3">
          <ShieldAlert className="text-scada-text-dim h-4 w-4" />
          <h1 className="text-sm font-bold text-scada-header uppercase tracking-[0.2em]">
            SENTINEL
          </h1>
          <span
            className={`ml-2 h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
            title={isConnected ? 'Live feed connected' : 'No live data'}
          />
          {currentIncident && (
            <span className="ml-2 px-2 py-0.5 bg-scada-red text-scada-bg text-[9px] font-mono font-bold uppercase">
              1 ACTIVE
            </span>
          )}
        </div>

        {/* Center: Essential Context */}
        <div className="flex bg-scada-bg border border-scada-border">
          <button
            onClick={() => switchCity('nyc')}
            className={`px-4 py-1.5 text-[10px] font-mono uppercase tracking-[0.1em] transition-colors ${
              city === 'nyc'
                ? 'bg-scada-text-dim text-scada-white'
                : 'text-scada-text-dim hover:text-scada-text'
            }`}
          >
            NEW YORK
          </button>
          <button
            onClick={() => switchCity('chandigarh')}
            className={`px-4 py-1.5 text-[10px] font-mono uppercase tracking-[0.1em] border-l border-scada-border transition-colors ${
              city === 'chandigarh'
                ? 'bg-scada-text-dim text-scada-white'
                : 'text-scada-text-dim hover:text-scada-text'
            }`}
          >
            CHANDIGARH
          </button>
        </div>

        {/* Right: Clock */}
        <div className="flex flex-col items-end -space-y-1">
          <span className="text-sm font-mono text-scada-text">
            {formatTime(currentTime)}
          </span>
          <span className="text-[9px] font-mono text-scada-text-dim">
            {formatDate(currentTime)}
          </span>
        </div>
      </header>

      {notification && (
        <div className="h-8 bg-scada-red flex items-center justify-center gap-2 animate-pulse">
          <Bell className="h-3 w-3 text-scada-bg" />
          <span className="text-[10px] font-mono font-bold text-scada-bg uppercase tracking-wider">
            {notification}
          </span>
        </div>
      )}

      {/* ═══ MAIN GRID ═══ */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left Panel: Intelligence Outputs */}
        <section className="w-[340px] border-r border-scada-border flex flex-col bg-scada-bg overflow-hidden">
          <div className="h-9 px-4 border-b border-scada-border flex items-center gap-2">
            <Activity className="h-3 w-3 text-scada-text-dim" />
            <h2 className="text-[10px] font-mono uppercase text-scada-text">
              ACTION PANEL
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {leftPanel}
          </div>
        </section>

        {/* Center Panel: Map */}
        <section className="flex-1 relative flex flex-col overflow-hidden bg-scada-bg">
          <div className="absolute top-4 left-4 z-[1000] flex items-center gap-2 bg-scada-panel px-3 py-1.5 border border-scada-border pointer-events-none">
            <MapIcon className="h-3 w-3 text-scada-text-dim" />
            <span className="text-[10px] font-mono uppercase text-scada-text">
              SITUATION MAP
            </span>
          </div>
          
          {/* Simple Legend */}
          <div className="absolute bottom-4 left-4 z-[1000] bg-scada-panel/90 border border-scada-border p-3 pointer-events-none">
             <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2 text-[9px] font-mono text-scada-text">
                  <div className="w-3 h-3 bg-scada-red flex-shrink-0" /> INCIDENT / STOPPED
                </div>
                <div className="flex items-center gap-2 text-[9px] font-mono text-scada-text">
                  <div className="w-3 h-3 bg-scada-yellow flex-shrink-0" /> SLOW / CONGESTED
                </div>
                <div className="flex items-center gap-2 text-[9px] font-mono text-scada-text">
                  <div className="w-3 h-3 border-t-2 border-scada-text border-dashed flex-shrink-0" /> DIVERSION ROUTE
                </div>
             </div>
          </div>

          {centerPanel}
        </section>

        {/* Right Panel: Chat */}
        <section className="w-[360px] border-l border-scada-border flex flex-col bg-scada-bg overflow-hidden">
          <div className="h-9 px-4 border-b border-scada-border flex items-center gap-2">
            <MessageSquare className="h-3 w-3 text-scada-text-dim" />
            <h2 className="text-[10px] font-mono uppercase text-scada-text">
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
