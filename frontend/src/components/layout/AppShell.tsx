import React, { useState, useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';
import { ShieldAlert, Bell, Eye, EyeOff, X } from 'lucide-react';
import OperatorDropdown from './OperatorDropdown';
import DemoControls from '../demo/DemoControls';
import { useFeedStore, useIncidentStore, useUIStore, deriveAlertPriority } from '../../store';
import { api } from '../../services/api';
import { StatusDot, MetricsBar, UndoToast } from '../UIKit';

interface AppShellProps {
  leftPanel: ReactNode;
  centerPanel: ReactNode;
  rightPanel: ReactNode;
}

const AppShell: React.FC<AppShellProps> = ({ leftPanel, centerPanel, rightPanel }) => {
  const [currentTime, setCurrentTime] = useState(new Date());
  const { city, fetchBaselines, lastUpdate, segments } = useFeedStore();
  const { fetchIncidents, currentIncident, incidents } = useIncidentStore();
  const { 
    focusMode, 
    setFocusMode, 
    pendingUndoActions, 
    triggerUndo, 
    pushFocusStack 
  } = useUIStore();
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    api.switchCity(city).catch(() => {}).finally(() => {
      fetchBaselines();
    });
  }, [city, fetchBaselines]);

  useEffect(() => {
    if (city) {
      fetchIncidents(city).then(() => {
        const state = useIncidentStore.getState();
        const active = state.incidents
          .filter((i) => i.status !== 'resolved')
          .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());
        if (active.length > 0 && !state.currentIncident) {
          state.setIncident(active[0]);
        }
      });

      api.getCongestionZones(city, 'active,permanent').then((zones: any[]) => {
        if (Array.isArray(zones)) {
          const { setCongestionZone } = useIncidentStore.getState();
          zones.forEach((z: any) => setCongestionZone(z));
        }
      }).catch(() => {});
    }
  }, [city, fetchIncidents]);

  // Alert & Focus Logic
  useEffect(() => {
    if (currentIncident) {
      const priority = deriveAlertPriority(currentIncident);
      if (priority === 'P0' || priority === 'P1') {
        pushFocusStack(currentIncident.id);
        setNotification(`🚨 CRITICAL ALERT: ${currentIncident.on_street}`);
      } else {
        setNotification(`INCIDENT detected: ${currentIncident.on_street}`);
      }
      const timer = setTimeout(() => setNotification(null), 8000);
      return () => clearTimeout(timer);
    }
  }, [currentIncident?.id, pushFocusStack]);

  const isConnected = useMemo(() => {
    if (!lastUpdate) return false;
    return Date.now() - new Date(lastUpdate).getTime() < 10_000;
  }, [lastUpdate]);

  const metrics = useMemo(() => {
    if (!segments.length) return { flow: 0, active: 0, delay: '0.0' };
    const healthy = segments.filter(s => (s as any).speed_ratio > 0.6).length;
    const flow = Math.round((healthy / segments.length) * 100);
    const active = incidents.filter(i => i.status === 'active').length;
    
    // Average delay logic placeholder
    const totalDelay = 4.2; 
    return { flow, active, delay: totalDelay.toFixed(1) };
  }, [segments, incidents]);

  const formatTime = (d: Date) =>
    d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const formatDate = (d: Date) =>
    d.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: '2-digit' }).toUpperCase();

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg text-text-main">
      {/* ═══ TOP BAR ═══ */}
      <header className="h-12 border-b border-border-dim flex items-center justify-between px-4 bg-panel">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="text-critical h-5 w-5" />
            <h1 className="text-sm font-bold text-text-bright uppercase tracking-[0.2em]">SENTINEL</h1>
          </div>
          
          <div className="flex items-center gap-2 px-3 py-1 bg-bg border border-border-dim rounded-sm">
            <StatusDot status={isConnected ? 'live' : 'error'} />
            <span className="text-[10px] font-mono uppercase tracking-wider text-text-dim">
              {isConnected ? 'FEED LIVE' : 'FEED OFFLINE'}
            </span>
          </div>

          <div className="ml-2">
            <DemoControls />
          </div>
        </div>

        {/* METRICS BAR */}
        <div className="flex-1 flex justify-center px-10">
          <MetricsBar flow={metrics.flow} activeCount={metrics.active} delay={metrics.delay} />
        </div>

        <div className="flex items-center gap-6">
          <button 
            onClick={() => setFocusMode(focusMode === 'normal' ? 'incident' : 'normal')}
            className={`flex items-center gap-2 px-3 py-1 border transition-all ${
              focusMode === 'incident' 
                ? 'bg-critical text-bg border-critical' 
                : 'bg-bg text-text-dim border-border-dim hover:text-text-bright'
            }`}
          >
            {focusMode === 'incident' ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            <span className="text-[10px] font-mono font-bold uppercase">Focus Mode</span>
          </button>

          <div className="flex flex-col items-end -space-y-0.5">
            <span className="text-sm font-mono text-text-bright font-bold tracking-tight">
              {formatTime(currentTime)}
            </span>
            <span className="text-[9px] font-mono text-text-dim">
              {formatDate(currentTime)}
            </span>
          </div>

          <OperatorDropdown />
        </div>
      </header>

      {/* P0 ALERT BANNER */}
      {notification && (
        <div className="h-8 bg-critical flex items-center justify-center gap-3 animate-alert-slide relative z-[1500]">
          <Bell className="h-4 w-4 text-bg animate-bounce" />
          <span className="text-[11px] font-mono font-bold text-bg uppercase tracking-widest">
            {notification}
          </span>
          <button 
            onClick={() => setNotification(null)}
            className="absolute right-4 text-bg/70 hover:text-bg"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* ═══ MAIN GRID ═══ */}
      <main className="flex-1 flex overflow-hidden relative">
        {/* Left Panel */}
        <section className={`w-[360px] border-r border-border-dim flex flex-col bg-panel transition-all duration-300 ${focusMode === 'incident' && !currentIncident ? 'focus-mode-dim' : ''}`}>
          <div className="flex-1 overflow-hidden">
            {leftPanel}
          </div>
        </section>

        {/* Map Center */}
        <section className="flex-1 relative flex flex-col overflow-hidden bg-bg">
          {centerPanel}
          
          {/* REDESIGNED LEGEND */}
          <div className="absolute bottom-6 left-6 z-[1000] backdrop-blur-md bg-bg/80 border border-border-dim p-4 rounded-sm shadow-2xl pointer-events-none transition-all duration-500 hover:opacity-100">
             <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3 text-[10px] font-mono font-bold text-text-bright tracking-tight">
                  <div className="w-2 h-2 rounded-full bg-critical animate-pulse-live" /> INCIDENT / BLOCKED
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-text-dim">
                  <div className="w-2 h-2 rounded-full bg-warning" /> CONGESTION ZONE
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-text-dim">
                  <div className="w-2 h-2 rounded-full bg-success" /> SAFE ALTERNATE
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-text-dim">
                  <div className="w-2 h-2 rounded-sm bg-info" /> CCTV MARKER
                </div>
             </div>
          </div>
        </section>

        {/* Right Panel */}
        <section className={`w-[380px] border-l border-border-dim flex flex-col bg-panel transition-all duration-300 ${focusMode === 'incident' ? 'opacity-60' : ''}`}>
          <div className="flex-1 overflow-hidden">
            {rightPanel}
          </div>
        </section>

        {/* UNDO TOASTS */}
        {pendingUndoActions.map(action => (
          <UndoToast 
            key={action.id}
            message={action.label}
            onUndo={() => triggerUndo(action.id)}
          />
        ))}
      </main>
    </div>
  );
};

export default AppShell;
