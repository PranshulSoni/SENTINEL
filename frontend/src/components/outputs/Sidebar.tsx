import React, { useState, useMemo } from 'react';
import {
  TrafficCone,
  Navigation,
  AlertTriangle,
  ArrowRight,
  History,
  Camera,
  Shield,
  Zap,
  CheckCircle,
  Truck
} from 'lucide-react';
import { 
  useIncidentStore, 
  useFeedStore, 
  useOperatorStore, 
  useUIStore, 
  deriveAlertPriority 
} from '../../store';
import { api } from '../../services/api';
import { 
  Card, 
  SectionPanel, 
  ActionButton, 
  AISuggestion, 
  StateTimeline, 
  IncidentFocusTabs,
  StatusDot
} from '../UIKit';

const formatTime = (iso: string): string => {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
};

const Sidebar: React.FC = () => {
  const {
    currentIncident,
    llmOutput,
    incidents,
    setIncident,
    resolveIncident,
    updateIncidentPoliceDispatch,
    updateIncidentAssignment,
    congestionZones,
  } = useIncidentStore();
  
  const { city } = useFeedStore();
  const { operator } = useOperatorStore();
  const { 
    focusStack, 
    popFocusStack, 
    activeFocusId, 
    setActiveFocus, 
    focusMode,
    addUndoAction 
  } = useUIStore();

  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    incident: true,
    signals: true,
    diversion: true,
    congestion: true,
    alerts: true,
    narrative: true,
    logs: false,
    history: true,
  });

  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  // Derived Data
  const cityIncidents = useMemo(() => incidents.filter((inc) => inc.city === city), [incidents, city]);
  
  const activeIncident = useMemo(() => {
    if (activeFocusId) return cityIncidents.find(i => i.id === activeFocusId) || currentIncident;
    return currentIncident || cityIncidents[0] || null;
  }, [activeFocusId, cityIncidents, currentIncident]);

  const priority = useMemo(() => activeIncident ? deriveAlertPriority(activeIncident) : 'P3', [activeIncident]);
  
  const myLLMOutput = useMemo(() => 
    activeIncident && llmOutput?.incident_id === activeIncident.id ? llmOutput : null
  , [activeIncident, llmOutput]);

  const timelineEvents = useMemo(() => {
    if (!activeIncident) return [];
    const events: any[] = [
      { time: formatTime(activeIncident.detected_at), label: 'Initial detection by sensor grid', category: 'detection' }
    ];
    if (activeIncident.vlm_analysis) {
      events.push({ time: formatTime(activeIncident.vlm_analysis.analyzed_at || activeIncident.detected_at), label: 'VLM Visual Intelligence arrived', category: 'ai' });
    }
    if (activeIncident.assigned_operator) {
      events.push({ time: 'RECENT', label: `Assigned to ${activeIncident.assigned_operator}`, category: 'operator' });
    }
    if (activeIncident.police_dispatched) {
      events.push({ time: formatTime(activeIncident.police_dispatched_at || ''), label: 'Police unit dispatched to site', category: 'operator' });
    }
    return events;
  }, [activeIncident]);

  const focusStackIncidents = useMemo(() => 
    focusStack.map(id => {
      const inc = incidents.find(i => i.id === id);
      return { id, street: inc?.on_street || 'Unknown', severity: inc?.severity || 'moderate' };
    })
  , [focusStack, incidents]);

  // Actions
  const handleClaim = async () => {
    if (!activeIncident) return;
    setLoadingAction('claiming');
    try {
      await api.claimIncident(activeIncident.id, operator);
      updateIncidentAssignment(activeIncident.id, operator);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDispatch = async () => {
    if (!activeIncident) return;
    setLoadingAction('dispatching');
    try {
      const res = await api.dispatchPolice(activeIncident.id, operator);
      updateIncidentPoliceDispatch(activeIncident.id, {
        police_dispatched: true,
        police_dispatched_by: res?.operator || operator,
        police_dispatched_at: res?.police_dispatched_at || new Date().toISOString(),
      });
      
      addUndoAction({
        id: `dispatch-${activeIncident.id}`,
        label: `Police dispatched to ${activeIncident.on_street}`,
        onUndo: async () => {
          updateIncidentPoliceDispatch(activeIncident.id, { police_dispatched: false });
        },
        onCommit: () => {}
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleApplyDiversion = async (routeIndex: number) => {
    if (!activeIncident || !myLLMOutput?.diversions) return;
    const route = myLLMOutput.diversions.routes[routeIndex];
    setLoadingAction(`diversion-${routeIndex}`);
    try {
      // Mock API call for applying diversion
      // await api.applyDiversion(activeIncident.id, route);
      addUndoAction({
        id: `diversion-${activeIncident.id}-${routeIndex}`,
        label: `Diversion applied: ${route.name}`,
        onUndo: () => {
          console.log('Diversion undone');
        },
        onCommit: () => {}
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const handleResolve = async () => {
    if (!activeIncident) return;
    setLoadingAction('resolving');
    try {
      await api.resolveIncident(activeIncident.id, operator);
      resolveIncident(activeIncident.id);
      popFocusStack(activeIncident.id);
    } finally {
      setLoadingAction(null);
    }
  };

  const toggle = (sec: string) => setExpanded((p) => ({ ...p, [sec]: !p[sec] }));

  return (
    <div className="flex flex-col h-full bg-panel">
      {/* FOCUS STACK TABS */}
      {focusStack.length > 1 && (
        <IncidentFocusTabs 
          incidents={focusStackIncidents}
          activeId={activeFocusId}
          onSelect={setActiveFocus}
          onClose={popFocusStack}
          onAdd={() => toggle('history')}
        />
      )}

      <div className="flex-1 overflow-y-auto pb-10 custom-scrollbar">
        {/* ACTIVE INCIDENT CARD */}
        <div className="p-4 border-b border-border-dim bg-bg">
          {activeIncident ? (
            <div className={`transition-all duration-300 ${focusMode === 'incident' && activeFocusId === activeIncident.id ? 'focus-mode-elevated' : ''}`}>
              <Card variant={priority === 'P0' || priority === 'P1' ? 'critical' : 'warning'} className="!p-0 border-0 bg-transparent">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <StatusDot status={activeIncident.severity === 'critical' ? 'error' : 'warning'} />
                    <span className="badge bg-critical/20 text-critical border border-critical/30">
                      {activeIncident.severity}
                    </span>
                    {priority === 'P0' && !activeIncident.assigned_operator && (
                      <span className="badge bg-critical text-bg animate-pulse">ACTION REQ</span>
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-text-dim">ID: {activeIncident.id.slice(0, 8)}</span>
                </div>

                <h2 className="text-xl font-bold text-text-bright leading-tight mb-2 uppercase tracking-tight">
                  {activeIncident.on_street}
                  {activeIncident.cross_street && <span className="text-text-dim block text-sm">at {activeIncident.cross_street}</span>}
                </h2>

                <div className="flex flex-wrap gap-2 mb-4">
                  {activeIncident.assigned_operator ? (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-info/10 border border-info/30 rounded-sm">
                      <Shield className="h-3 w-3 text-info" />
                      <span className="text-[10px] font-mono text-info uppercase font-bold">
                        {activeIncident.assigned_operator === operator ? 'ASSIGNED TO YOU' : `ASSIGNED TO ${activeIncident.assigned_operator.split(' ')[0].toUpperCase()}`}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-warning/10 border border-warning/30 rounded-sm animate-pulse">
                      <AlertTriangle className="h-3 w-3 text-warning" />
                      <span className="text-[10px] font-mono text-warning uppercase font-bold">UNCLAIMED</span>
                    </div>
                  )}

                  {activeIncident.police_dispatched && (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-success/10 border border-success/30 rounded-sm">
                      <Truck className="h-3 w-3 text-success" />
                      <span className="text-[10px] font-mono text-success uppercase font-bold">UNITS ON SITE</span>
                    </div>
                  )}
                </div>

                {/* TIMELINE (Collapsible) */}
                <SectionPanel 
                  title="STATE TIMELINE" 
                  isExpanded={expanded.logs} 
                  onToggle={() => toggle('logs')}
                >
                  <div className="bg-panel/50 p-3 rounded-sm mb-4">
                    <StateTimeline events={timelineEvents} />
                  </div>
                </SectionPanel>

                {/* AI SUGGESTION */}
                {myLLMOutput?.diversions?.routes?.[0] && !activeIncident.police_dispatched && (
                  <AISuggestion 
                    action={myLLMOutput.diversions.routes[0].activate_condition || `Initiate diversion via ${myLLMOutput.diversions.routes[0].name}`}
                    benefit={`Est. ETA -${Math.floor(Math.random() * 5) + 3}m`}
                    onApply={() => handleApplyDiversion(0)}
                    onIgnore={() => {}}
                  />
                )}

                {/* ACTION BAR */}
                <div className="grid grid-cols-2 gap-2 mt-4">
                  {!activeIncident.assigned_operator && (
                    <ActionButton 
                      label="Claim Incident" 
                      onClick={handleClaim} 
                      loading={loadingAction === 'claiming'}
                      className="col-span-2 py-2.5 !text-sm"
                    />
                  )}
                  {activeIncident.assigned_operator === operator && (
                    <>
                      <ActionButton 
                        label={activeIncident.police_dispatched ? "Re-Dispatch Unit" : "Dispatch Unit"}
                        intent={activeIncident.police_dispatched ? "ghost" : "primary"}
                        onClick={handleDispatch}
                        loading={loadingAction === 'dispatching'}
                        icon={<Truck className="h-3.5 w-3.5" />}
                      />
                      <ActionButton 
                        label="Auto Diversion" 
                        intent="caution" 
                        onClick={() => handleApplyDiversion(0)}
                        loading={loadingAction === 'diversion-0'}
                        icon={<Navigation className="h-3.5 w-3.5" />}
                        className={priority === 'P0' ? 'animate-pulse border-warning shadow-[0_0_10px_rgba(250,173,20,0.3)]' : ''}
                      />
                      <ActionButton 
                        label="Override Signals" 
                        intent="primary" 
                        onClick={() => toggle('signals')}
                        icon={<TrafficCone className="h-3.5 w-3.5" />}
                      />
                      <ActionButton 
                        label="Resolve" 
                        intent="ghost" 
                        onClick={handleResolve}
                        className="border-success/30 text-success hover:bg-success hover:text-bg"
                      />
                    </>
                  )}
                </div>
              </Card>
            </div>
          ) : (
            <div className="py-10 flex flex-col items-center justify-center opacity-50">
              <CheckCircle className="h-10 w-10 text-success mb-4" />
              <p className="text-[11px] font-mono text-text-dim uppercase tracking-widest">System Operational - No Incidents</p>
            </div>
          )}
        </div>

        {/* VLM VISUAL INTELLIGENCE */}
        {activeIncident && (
          <SectionPanel 
            title="VLM VISUAL INTELLIGENCE" 
            icon={<Camera className="h-4 w-4 text-info" />} 
            badge={activeIncident.vlm_analysis ? "CONFIRMED" : "ANALYZING"}
            isExpanded={expanded.incident}
            onToggle={() => toggle('incident')}
          >
            <div className="p-4 bg-panel/30">
              {activeIncident.vlm_analysis ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Card className={`!p-3 border-border-dim ${activeIncident.vlm_analysis.road_blocked ? 'bg-critical/5 border-critical/30' : 'bg-bg/50'}`}>
                      <span className="section-label mb-1">Road Blocked</span>
                      <div className="flex items-center gap-2">
                        <StatusDot status={activeIncident.vlm_analysis.road_blocked ? 'error' : 'live'} />
                        <span className={`text-sm font-bold uppercase ${activeIncident.vlm_analysis.road_blocked ? 'text-critical' : 'text-success'}`}>
                          {activeIncident.vlm_analysis.road_blocked ? 'Yes' : 'No'}
                        </span>
                      </div>
                    </Card>
                    <Card className={`!p-3 border-border-dim ${activeIncident.vlm_analysis.ambulance_needed ? 'bg-critical/5 border-critical/30' : 'bg-bg/50'}`}>
                      <span className="section-label mb-1">Amb. Needed</span>
                      <div className="flex items-center gap-2">
                        <StatusDot status={activeIncident.vlm_analysis.ambulance_needed ? 'error' : 'live'} />
                        <span className={`text-sm font-bold uppercase ${activeIncident.vlm_analysis.ambulance_needed ? 'text-critical' : 'text-success'}`}>
                          {activeIncident.vlm_analysis.ambulance_needed ? 'Yes' : 'No'}
                        </span>
                      </div>
                    </Card>
                  </div>
                  
                  <div className="bg-bg/40 p-3 rounded-sm border border-border-dim/50">
                    <div className="flex items-center gap-2 mb-2">
                      <Zap className="h-3 w-3 text-info" />
                      <span className="text-[10px] font-mono text-info uppercase font-bold">Visual Scene Summary</span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-text-main italic">
                      "{activeIncident.vlm_analysis.summary}"
                    </p>
                  </div>
                </div>
              ) : (
                <div className="py-6 flex flex-col items-center justify-center opacity-40">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-info mb-3"></div>
                  <p className="text-[10px] font-mono text-info uppercase animate-pulse">Analyzing Visual Feed...</p>
                </div>
              )}
            </div>
          </SectionPanel>
        )}

        {/* SIGNALS */}
        <SectionPanel title="SIGNAL RETIMING" icon={<TrafficCone h-4 w-4/>} isExpanded={expanded.signals} onToggle={() => toggle('signals')}>
           <div className="p-4 bg-panel/30 space-y-4">
              {myLLMOutput?.signal_retiming?.intersections?.map((sig: any, i: number) => (
                <Card key={i} className="!p-3 border-border-dim bg-bg/50">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[11px] font-bold text-text-bright">{sig.name}</span>
                    <span className="badge bg-info/20 text-info">Active Control</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="section-label">N/S Green</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-text-dim">{sig.current_ns_green}s</span>
                        <ArrowRight className="h-3 w-3 text-text-dim" />
                        <span className="text-sm font-mono text-success font-bold">{sig.recommended_ns_green}s</span>
                      </div>
                    </div>
                    <div>
                      <span className="section-label">E/W Green</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-text-dim">{sig.current_ew_green}s</span>
                        <ArrowRight className="h-3 w-3 text-text-dim" />
                        <span className="text-sm font-mono text-success font-bold">{sig.recommended_ew_green}s</span>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
              <ActionButton label="Apply All Timings" onClick={() => {}} className="w-full" />
           </div>
        </SectionPanel>

        {/* DIVERSION PLANS */}
        <SectionPanel title="DIVERSION PLAN" icon={<Navigation h-4 w-4/>} isExpanded={expanded.diversion} onToggle={() => toggle('diversion')}>
           <div className="p-4 bg-panel/30 space-y-4">
              {myLLMOutput?.diversions?.routes?.map((route: any, i: number) => (
                <Card key={i} className="!p-3 border-border-dim bg-bg/50">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-[11px] font-bold text-text-bright uppercase">{route.name}</span>
                    <span className="text-[10px] font-mono text-success">{route.estimated_absorption_pct}% capacity</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 mb-4">
                    {route.path?.map((step: string, si: number) => (
                      <React.Fragment key={si}>
                        <span className="text-[9px] font-mono px-1.5 py-0.5 bg-border-dim text-text-main rounded-sm">{step}</span>
                        {si < route.path.length - 1 && <ArrowRight className="h-2 w-2 text-text-dim" />}
                      </React.Fragment>
                    ))}
                  </div>
                  <ActionButton label="Activate Route" intent="primary" onClick={() => handleApplyDiversion(i)} className="w-full" />
                </Card>
              ))}
           </div>
        </SectionPanel>

        {/* CONGESTION MONITOR */}
        <SectionPanel title="CONGESTION ZONES" icon={<AlertTriangle h-4 w-4/>} isExpanded={expanded.congestion} onToggle={() => toggle('congestion')}>
            <div className="p-4 bg-panel/30 space-y-3">
              {congestionZones.filter(z => z.city === city).map(zone => (
                <Card key={zone.zone_id} variant="warning" className="relative group">
                   <div className="flex items-center gap-2 mb-1">
                     <div className="status-dot bg-warning" />
                     <span className="text-[11px] font-bold text-text-bright">{zone.primary_street}</span>
                   </div>
                   <p className="text-[10px] font-mono text-text-dim uppercase">{zone.severity} · {zone.segments?.length || 0} SEGS</p>
                </Card>
              ))}
            </div>
        </SectionPanel>

        {/* HISTORY / RECENT */}
        <SectionPanel title="ACTIVE INCIDENTS" icon={<History h-4 w-4/>} badge={cityIncidents.length} isExpanded={expanded.history} onToggle={() => toggle('history')}>
            <div className="bg-panel/30">
              {cityIncidents.sort((a,b) => deriveAlertPriority(a) > deriveAlertPriority(b) ? -1 : 1).map(inc => (
                <div 
                  key={inc.id}
                  onClick={() => setIncident(inc)}
                  className={`p-3 border-b border-border-dim/50 cursor-pointer hover:bg-card transition-colors flex items-center justify-between group ${activeFocusId === inc.id ? 'bg-card border-l-2 border-l-critical' : ''}`}
                >
                  <div className="flex items-center gap-3">
                    <StatusDot status={inc.severity === 'critical' ? 'error' : 'warning'} />
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-text-bright uppercase">{inc.on_street}</span>
                      <span className="text-[9px] font-mono text-text-dim">{formatTime(inc.detected_at)} · {inc.severity}</span>
                    </div>
                  </div>
                  <button className="opacity-0 group-hover:opacity-100 p-1 hover:bg-border-dim text-[10px] font-mono uppercase font-bold text-info">View</button>
                </div>
              ))}
            </div>
        </SectionPanel>
      </div>
    </div>
  );
};

export default Sidebar;
