import React, { useState, useEffect, useRef } from 'react';
import {
  TrafficCone,
  Navigation,
  Share2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ArrowRight,
  FileText,
  CheckCircle,
  History,
  BookOpen,
  Camera,
} from 'lucide-react';
import { useIncidentStore, useFeedStore, useOperatorStore } from '../../store';
import { api } from '../../services/api';

interface LogEntry {
  time: string;
  event: string;
}

const formatTime = (iso: string): string => {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
};

const Sidebar: React.FC = () => {
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

  const [timingsApplied, setTimingsApplied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [showMedia, setShowMedia] = useState(false);
  const [dispatchingPolice, setDispatchingPolice] = useState(false);
  const [publishingSocial, setPublishingSocial] = useState(false);
  const [lastSocialPublish, setLastSocialPublish] = useState<string | null>(null);


  const {
    currentIncident,
    llmOutput,
    incidents,
    incidentRoutes,
    setIncident,
    setLLMOutput,
    resolveIncident,
    dismissIncident,
    updateIncidentPoliceDispatch,
    updateIncidentAssignment,
    congestionZones,
  } = useIncidentStore();
  const { segments, city } = useFeedStore();
  const { operator } = useOperatorStore();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const prevIncidentIdRef = useRef<string | null>(null);
  const prevLlmRef = useRef<boolean>(false);

  // Client-side city filter — double safety net even if store data leaks
  const cityIncidents = incidents.filter((inc) => inc.city === city);
  const cityCongestionZones = congestionZones.filter((z: any) =>
    !z._city || z._city === city || z.city === city
  );

  const cityCurrentIncident = currentIncident && currentIncident.city === city
    ? (cityIncidents.find((inc) => inc.id === currentIncident.id) ?? currentIncident)
    : null;
  const myIncident = cityIncidents.find((inc) => inc.assigned_operator === operator) ?? null;
  const fallbackCityIncident = cityIncidents[0] ?? null;

  // Keep user-selected/current incident in focus; only fallback when nothing selected.
  const activeIncident = cityCurrentIncident ?? myIncident ?? fallbackCityIncident;
  const activeIncidentIsMine = activeIncident?.assigned_operator === operator;
  const activeIncidentIsPending = !activeIncident?.assigned_operator;

  const myLLMOutput = activeIncident && llmOutput?.incident_id === activeIncident.id
    ? llmOutput
    : (llmOutput ?? null);  // Show latest output while selected-incident output hydrates
  const myRoutePair = activeIncident
    ? incidentRoutes.find((rp) => rp.incidentId === activeIncident.id) ?? null
    : null;
  const modeledEta = Number(myRoutePair?.alternate?.estimated_minutes || 0);
  const actualEta = Number(myRoutePair?.alternate?.estimated_actual_minutes || modeledEta || 0);
  const modeledExtraEta = Number(myRoutePair?.alternate?.estimated_extra_minutes || 0);
  const actualExtraEta = Number(
    myRoutePair?.alternate?.estimated_actual_extra_minutes || modeledExtraEta || 0
  );
  const socialAlertMessage = myLLMOutput?.alerts?.social_media || myLLMOutput?.alerts?.vms || '';
  const socialAlertDraft = (
    socialAlertMessage
    || myLLMOutput?.alerts?.radio
    || (activeIncident
      ? `Traffic advisory: congestion near ${activeIncident.on_street}${activeIncident.cross_street ? ` & ${activeIncident.cross_street}` : ''}. Use designated safe route and expect delays.`
      : `Traffic advisory for ${city === 'nyc' ? 'New York City' : 'Chandigarh'}: expect congestion in affected corridors and follow official safe-route guidance.`)
  ).trim();

  // Log when selected/active incident changes
  useEffect(() => {
    if (activeIncident && activeIncident.id !== prevIncidentIdRef.current) {
      prevIncidentIdRef.current = activeIncident.id;
      setLogs((prev) => [
        ...prev,
        {
          time: formatTime(activeIncident.detected_at),
          event: `Detection: Incident ${activeIncident.id} on ${activeIncident.on_street}`,
        },
      ]);
    }
    if (!activeIncident) {
      prevIncidentIdRef.current = null;
    }
  }, [activeIncident]);

  // Log when LLM output arrives for my incident
  useEffect(() => {
    if (myLLMOutput && !prevLlmRef.current) {
      prevLlmRef.current = true;
      setLogs((prev) => [
        ...prev,
        { time: formatTime(new Date().toISOString()), event: 'Action: LLM intelligence received' },
      ]);
    }
    if (!myLLMOutput) {
      prevLlmRef.current = false;
    }
  }, [myLLMOutput]);

  // Hydrate LLM output on reload / reconnect for the focused incident.
  useEffect(() => {
    if (!activeIncident?.id) return;
    let cancelled = false;
    const incidentId = activeIncident.id;
    api.getLLMOutput(incidentId)
      .then((data) => {
        if (cancelled) return;
        if (useIncidentStore.getState().currentIncident?.id !== incidentId) return;
        if (data && typeof data === 'object') {
          setLLMOutput(data);
        }
      })
      .catch(() => {
        if (!cancelled && useIncidentStore.getState().currentIncident?.id === incidentId) {
          setLLMOutput(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeIncident?.id, setLLMOutput]);

  useEffect(() => {
    setLastSocialPublish(null);
  }, [activeIncident?.id]);

  const publishSocialAlert = async () => {
    if (publishingSocial) return;
    setPublishingSocial(true);
    try {
      const res = await api.publishSocialAlert({
        city,
        message: socialAlertDraft,
        incident_id: activeIncident?.id,
        operator,
      });
      setLastSocialPublish(res?.published_at || new Date().toISOString());
      setLogs((prev) => [
        ...prev,
        {
          time: formatTime(new Date().toISOString()),
          event: `Action: Social alert published (${res?.recipient_count ?? 0} recipients)`,
        },
      ]);
    } catch (e: any) {
      console.error('Failed to publish social alert:', e?.detail || e);
    } finally {
      setPublishingSocial(false);
    }
  };

  const toggle = (sec: string) => setExpanded((p) => ({ ...p, [sec]: !p[sec] }));

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-8">

      {/* INCIDENT HEADER */}
      <div className="p-4 border-b border-scada-border">
        {activeIncident ? (
          <div className="flex items-start gap-3">
            <div className="mt-1 p-2 bg-scada-red/10 border border-scada-red">
              <AlertTriangle className="h-4 w-4 text-scada-red" />
            </div>
            <div className="flex-1">
              <span className="text-[10px] font-mono text-scada-red uppercase mb-1 block">
                Active {activeIncident.severity}
                {cityIncidents.length > 1 && (
                  <span className="ml-2 bg-scada-red/20 px-1.5 py-0.5 text-[9px]">
                    {cityIncidents.length} CITY-WIDE
                  </span>
                )}
              </span>
              <h3 className="text-sm font-bold text-scada-header uppercase leading-tight mb-2">
                {activeIncident.on_street}{activeIncident.cross_street ? ` & ${activeIncident.cross_street}` : ''}
              </h3>
              <div className="flex flex-col gap-1 text-[10px] font-mono text-scada-text mt-2">
                <span className="text-scada-text-dim">
                  ID: {activeIncident.id} | SEVERITY: {activeIncident.severity.toUpperCase()}
                </span>
                <span className="text-scada-text-dim">
                  DETECTED: {formatTime(activeIncident.detected_at)} | SEGMENTS: {activeIncident.affected_segment_ids.length} affected
                </span>
                {activeIncidentIsMine ? (
                  <span className="text-scada-blue bg-scada-blue/10 px-2 py-1 border border-scada-blue/20 mt-1 inline-block w-fit">
                    ASSIGNED TO YOU — {operator}
                  </span>
                ) : activeIncident.assigned_operator ? (
                  <span className="text-yellow-300 bg-yellow-400/10 px-2 py-1 border border-yellow-300/25 mt-1 inline-block w-fit">
                    ASSIGNED TO {activeIncident.assigned_operator.toUpperCase()}
                  </span>
                ) : (
                  <span className="text-scada-yellow bg-scada-yellow/10 px-2 py-1 border border-scada-yellow/25 mt-1 inline-block w-fit">
                    UNASSIGNED INCIDENT
                  </span>
                )}
                {actualEta > 0 && (
                  <span className="text-scada-green bg-scada-green/10 px-2 py-1 border border-scada-green/25 mt-1 inline-block w-fit">
                    SAFE ROUTE ETA: {actualEta.toFixed(1)} MIN
                    {actualExtraEta > 0 ? ` (+${actualExtraEta.toFixed(1)} MIN)` : ''}
                  </span>
                )}
                {activeIncident.needs_ambulance && (
                  <span className="text-scada-bg font-bold bg-scada-red px-2 py-1 mt-1 border border-scada-red flex items-center gap-2 w-fit">
                    <span className="animate-pulse">🚑</span> AMBULANCE DISPATCHED
                  </span>
                )}
                {activeIncident.police_dispatched && (
                  <span className="text-scada-bg font-bold bg-scada-blue px-2 py-1 mt-1 border border-scada-blue flex items-center gap-2 w-fit">
                    POLICE DISPATCHED
                    {activeIncident.police_dispatched_at ? ` @ ${formatTime(activeIncident.police_dispatched_at)}` : ''}
                  </span>
                )}
              </div>
              {activeIncident.media_url && (
                <div className="mt-3">
                  <button
                    onClick={() => setShowMedia(!showMedia)}
                    className="flex items-center gap-2 px-2 py-1 border border-scada-border text-[10px] font-mono hover:bg-scada-panel transition-colors"
                  >
                    <Camera className="w-3 h-3" />
                    {showMedia ? 'HIDE INCIDENT PHOTO' : 'VIEW ATTACHED PHOTO'}
                  </button>
                  {showMedia && (
                    <div className="mt-2 border border-scada-border bg-scada-bg p-1 relative">
                      <img src={activeIncident.media_url} alt="Incident" className="w-full h-auto max-h-48 object-contain" />
                    </div>
                  )}
                </div>
              )}

              {activeIncident.vlm_analysis && (
                <div className="mt-4 border border-scada-blue/30 bg-scada-blue/5 p-2 animate-in fade-in slide-in-from-top-2 duration-500">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                       <Camera className="w-3 h-3 text-scada-blue" />
                       <span className="text-[10px] font-mono font-bold text-scada-blue uppercase">VLM VISUAL ANALYSIS</span>
                    </div>
                    <span className="text-[8px] font-mono text-scada-text-dim uppercase">Live Feedback</span>
                  </div>
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className={`px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase border ${activeIncident.vlm_analysis.road_blocked ? 'bg-scada-red/20 border-scada-red text-scada-red' : 'bg-scada-green/20 border-scada-green text-scada-green'}`}>
                      {activeIncident.vlm_analysis.road_blocked ? '🚧 ROAD BLOCKED' : '✅ ROAD CLEAR'}
                    </span>
                    {activeIncident.vlm_analysis.ambulance_needed && (
                      <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase bg-scada-red border border-scada-red text-scada-bg animate-pulse">
                        🚑 AMBULANCE REQ
                      </span>
                    )}
                    <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase bg-scada-panel border border-scada-border text-scada-text-dim">
                      SEVERITY: {activeIncident.vlm_analysis.severity.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[10px] font-mono text-scada-text leading-relaxed italic border-l-2 border-scada-blue/30 pl-2 py-1">
                    "{activeIncident.vlm_analysis.summary}"
                  </p>
                  <div className="mt-2 flex items-center justify-between text-[8px] font-mono text-scada-text-dim uppercase">
                    <span>Model: {activeIncident.vlm_analysis.model || 'QWEN2-VL'}</span>
                    <span>Analysed: {activeIncident.vlm_analysis.analyzed_at ? formatTime(activeIncident.vlm_analysis.analyzed_at) : 'RECENT'}</span>
                  </div>
                </div>
              )}

              {!activeIncident.vlm_analysis && activeIncidentIsMine && (
                <button
                  onClick={async () => {
                    try {
                      await api.analyseIncidentImage(activeIncident.id);
                      setLogs((prev) => [
                        ...prev,
                        { time: formatTime(new Date().toISOString()), event: `VLM: Initializing visual analysis...` },
                      ]);
                    } catch (e) {
                      console.error('VLM analysis trigger failed:', e);
                    }
                  }}
                  className="mt-3 w-full border border-scada-blue/40 py-1.5 text-[9px] font-mono uppercase text-scada-blue hover:bg-scada-blue/10 transition-all flex items-center justify-center gap-2 group"
                >
                  <span className="group-hover:rotate-12 transition-transform">✨</span>
                  TRIGGER AI VISUAL ANALYSIS
                </button>
              )}

              {activeIncidentIsMine ? (
                <>
                  <button
                    onClick={async () => {
                      if (!activeIncident || activeIncident.police_dispatched || dispatchingPolice) return;
                      setDispatchingPolice(true);
                      try {
                        const res = await api.dispatchPolice(activeIncident.id, operator);
                        updateIncidentPoliceDispatch(activeIncident.id, {
                          police_dispatched: true,
                          police_dispatched_by: res?.operator || operator,
                          police_dispatched_at: res?.police_dispatched_at || new Date().toISOString(),
                        });
                        setLogs((prev) => [
                          ...prev,
                          { time: formatTime(new Date().toISOString()), event: `Action: Police dispatched by ${operator}` },
                        ]);
                      } catch (e: any) {
                        console.error('Failed to dispatch police:', e?.detail || e);
                      } finally {
                        setDispatchingPolice(false);
                      }
                    }}
                    disabled={Boolean(activeIncident?.police_dispatched) || dispatchingPolice}
                    className={`mt-1 w-full border py-1.5 text-[10px] font-mono uppercase transition-colors ${
                      activeIncident?.police_dispatched
                        ? 'border-scada-blue/40 text-scada-blue/60 cursor-default'
                        : dispatchingPolice
                        ? 'border-scada-blue/40 text-scada-blue/50 cursor-wait'
                        : 'border-scada-blue text-scada-blue hover:bg-scada-blue hover:text-scada-bg'
                    }`}
                  >
                    {activeIncident?.police_dispatched ? 'POLICE DISPATCHED' : dispatchingPolice ? 'DISPATCHING POLICE...' : 'DISPATCH POLICE'}
                  </button>
                  <button
                    onClick={async () => {
                      if (!activeIncident) return;
                      try {
                        await api.resolveIncident(activeIncident.id, operator);
                        resolveIncident(activeIncident.id);
                      } catch (e: any) {
                        const msg = await e?.json?.().catch(() => null);
                        console.error('Failed to resolve:', msg?.detail || e);
                      }
                    }}
                    className="mt-2 w-full border border-scada-green py-1.5 text-[10px] font-mono uppercase text-scada-green hover:bg-scada-green hover:text-scada-bg transition-colors"
                  >
                    RESOLVE INCIDENT
                  </button>
                  <button
                    onClick={async () => {
                      if (!activeIncident) return;
                      try {
                        await api.dismissIncident(activeIncident.id, operator);
                        dismissIncident(activeIncident.id);
                      } catch (e: any) {
                        const msg = await e?.json?.().catch(() => null);
                        console.error('Failed to dismiss:', msg?.detail || e);
                      }
                    }}
                    className="mt-1 w-full border border-yellow-500 py-1.5 text-[10px] font-mono uppercase text-yellow-500 hover:bg-yellow-500 hover:text-scada-bg transition-colors"
                  >
                    ⚠ DISMISS AS FALSE ALARM
                  </button>
                </>
              ) : activeIncidentIsPending ? (
                <button
                  onClick={async () => {
                    if (!activeIncident) return;
                    try {
                      await api.claimIncident(activeIncident.id, operator);
                      updateIncidentAssignment(activeIncident.id, operator);
                    } catch (e) {
                      console.error('Failed to claim incident:', e);
                    }
                  }}
                  className="mt-2 w-full border border-scada-blue py-1.5 text-[10px] font-mono uppercase text-scada-blue hover:bg-scada-blue hover:text-scada-bg transition-colors"
                >
                  CLAIM INCIDENT
                </button>
              ) : (
                <div className="mt-2 text-[10px] font-mono text-scada-text-dim border border-scada-border px-2 py-1.5">
                  This incident is currently assigned to another controller.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3">
            <div className="mt-1 p-2 bg-green-500/10 border border-green-500">
              <CheckCircle className="h-4 w-4 text-green-500" />
            </div>
            <div>
              <span className="text-[10px] font-mono text-green-500 uppercase mb-1 block">All Clear</span>
              <h3 className="text-sm font-bold text-scada-header uppercase leading-tight mb-2">
                NO ACTIVE INCIDENTS
              </h3>
              <div className="text-[10px] font-mono text-scada-text-dim">
                {segments.length} segments monitored — all clear
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SIGNALS */}
      <SectionHeader icon={<TrafficCone />} title="SIGNALS" isExpanded={expanded.signals} onToggle={() => toggle('signals')} />
      {expanded.signals && (
        <div className="p-4 border-b border-scada-border space-y-3 bg-scada-panel/30">
          {myLLMOutput?.signal_retiming?.intersections && myLLMOutput.signal_retiming.intersections.length > 0 ? (
            <>
              <div className="text-[11px] font-mono text-scada-text">
                {myLLMOutput.signal_retiming.intersections[0]?.name === 'Parsed from LLM' ? (
                  /* LLM didn't follow intersection format — show raw analysis */
                  <pre className="text-[10px] font-mono text-scada-text-dim whitespace-pre-wrap leading-relaxed">
                    {myLLMOutput.signal_retiming.intersections[0]?.reasoning || myLLMOutput.signal_retiming.raw_text}
                  </pre>
                ) : (
                  <ul className="list-disc pl-4 space-y-2 text-scada-text-dim">
                    {myLLMOutput.signal_retiming.intersections.map((sig: any, i: number) => (
                      <li key={i}>
                        <span className="text-scada-text">{sig.name ?? 'Unknown intersection'}</span>
                        <br />
                        N/S: {sig.current_ns_green ?? '?'}s → {sig.recommended_ns_green ?? '?'}s | E/W: {sig.current_ew_green ?? '?'}s → {sig.recommended_ew_green ?? '?'}s
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <button
                onClick={() => {
                  setTimingsApplied(true);
                  setTimeout(() => setTimingsApplied(false), 3000);
                }}
                disabled={timingsApplied}
                className={`w-full mt-2 border py-2 text-[10px] font-mono uppercase transition-colors ${
                  timingsApplied
                    ? 'border-scada-green text-scada-green cursor-default'
                    : 'border-scada-text-dim hover:bg-scada-text hover:text-scada-bg'
                }`}
              >
                {timingsApplied ? '✓ TIMINGS APPLIED' : 'APPLY ALL TIMINGS'}
              </button>
              {activeIncident && (
                <button
                  onClick={async () => {
                    setRegenerating(true);
                    try {
                      const result = await api.regenerateLLM(activeIncident.id);
                      if (result && typeof result === 'object') {
                        setLLMOutput(result.llm_doc ?? result);
                      }
                    } catch (e) {
                      console.error('Failed to regenerate:', e);
                    } finally {
                      setRegenerating(false);
                    }
                  }}
                  disabled={regenerating}
                  className={`w-full mt-1 border border-scada-yellow/50 py-2 text-[10px] font-mono uppercase transition-colors ${
                    regenerating
                      ? 'text-scada-yellow/50 cursor-wait'
                      : 'text-scada-yellow hover:bg-scada-yellow hover:text-scada-bg'
                  }`}
                >
                  {regenerating ? '↻ REGENERATING...' : '↻ REGENERATE ANALYSIS'}
                </button>
              )}
            </>
          ) : (
            <p className="text-[10px] font-mono text-scada-text-dim italic">
              {activeIncident ? 'Analyzing incident — LLM processing...' : 'No active incident'}
            </p>
          )}
        </div>
      )}

      {/* DIVERSION */}
      <SectionHeader icon={<Navigation />} title="DIVERSION PLAN" isExpanded={expanded.diversion} onToggle={() => toggle('diversion')} />
      {expanded.diversion && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-panel/30">
          {myLLMOutput?.diversions?.routes && myLLMOutput.diversions.routes.length > 0 ? (
            myLLMOutput.diversions.routes[0]?.activate_condition && myLLMOutput.diversions.routes[0]?.path?.length === 0 ? (
              /* LLM didn't follow route format — show raw diversion analysis */
              <pre className="text-[10px] font-mono text-scada-text-dim whitespace-pre-wrap leading-relaxed">
                {myLLMOutput.diversions.routes[0]?.activate_condition || myLLMOutput.diversions.raw_text}
              </pre>
            ) : (
            myLLMOutput.diversions.routes.map((route: any, ri: number) => (
              <div key={ri}>
                <span className="text-[11px] font-mono text-scada-text block mb-2">
                  #{route.priority ?? ri + 1}: {route.name ?? `Route ${ri + 1}`} {route.estimated_absorption_pct != null ? `(${route.estimated_absorption_pct}% absorption)` : ''}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  {(route.path ?? []).map((step: string, i: number) => (
                    <React.Fragment key={i}>
                      <span className="text-[9px] font-mono px-2 py-1 bg-scada-border text-scada-text">{step}</span>
                      {i < (route.path ?? []).length - 1 && <ArrowRight className="h-3 w-3 text-scada-text-dim" />}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))
            )
          ) : (
            <p className="text-[10px] font-mono text-scada-text-dim italic">
              {activeIncident ? 'Analyzing incident — LLM processing...' : 'No active incident'}
            </p>
          )}

        </div>
      )}

      {/* CONGESTION ZONES */}
      <SectionHeader icon={<AlertTriangle />} title="CONGESTION ZONES" isExpanded={expanded.congestion} onToggle={() => toggle('congestion')} />
      {expanded.congestion && (
        <div className="p-4 border-b border-scada-border space-y-3 bg-scada-panel/30">
          <section>
            <h3 className="text-[11px] font-mono font-bold text-amber-400 mb-2 tracking-widest flex items-center gap-1">
              <span>🚧</span> CONGESTION ZONES
              {cityCongestionZones.length > 0 && (
                <span className="ml-auto text-[9px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">
                  {cityCongestionZones.length} ACTIVE
                </span>
              )}
            </h3>
            {cityCongestionZones.length > 0 ? (
              <div className="space-y-2">
                {cityCongestionZones.map((zone: any) => (
                  <div key={zone.zone_id} className="bg-amber-500/10 border border-amber-500/30 rounded p-2">
                    <p className="text-[10px] font-mono text-amber-300 font-bold">{zone.primary_street}</p>
                    <p className="text-[9px] font-mono text-scada-text-dim mt-0.5">
                      {zone.severity?.toUpperCase()} — {zone.segments?.length || 0} segments affected
                    </p>
                    {zone.alternate_routes && zone.alternate_routes.length > 0 && (
                      <div className="mt-1.5 space-y-1">
                        {zone.alternate_routes.map((r: any, i: number) => (
                          <div key={i} className="text-[9px] font-mono text-amber-200/80 flex items-center gap-1">
                            <span>↗</span>
                            <span>{r.name}</span>
                            {r.total_length_km && <span className="text-scada-text-dim">({r.total_length_km} km)</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] font-mono text-scada-text-dim italic">
                {activeIncident ? 'No congestion detected in area' : 'Monitoring traffic flow...'}
              </p>
            )}
          </section>
        </div>
      )}

      {/* ALERTS */}
      <SectionHeader icon={<Share2 />} title="PUBLIC ALERTS" isExpanded={expanded.alerts} onToggle={() => toggle('alerts')} />
      {expanded.alerts && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-panel/30">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-scada-text-dim">SOCIAL ALERT</span>
              <button
                onClick={publishSocialAlert}
                disabled={publishingSocial}
                className={`p-0.5 border ${
                  publishingSocial
                    ? 'border-scada-blue/40 text-scada-blue/50 cursor-wait'
                    : 'border-scada-blue text-scada-blue hover:bg-scada-blue hover:text-scada-bg'
                }`}
                title={publishingSocial ? 'Publishing...' : 'Publish social alert to all city users'}
              >
                <CheckCircle className="h-3 w-3" />
              </button>
            </div>
            <pre className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text whitespace-pre-wrap">
              {socialAlertDraft || 'No social alert available'}
            </pre>
            {lastSocialPublish && (
              <p className="text-[9px] font-mono text-scada-green mt-1">
                Published at {formatTime(lastSocialPublish)} to all users in {city.toUpperCase()}
              </p>
            )}
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-scada-text-dim">RADIO BROADCAST</span>
              <CheckCircle className="h-3 w-3 text-scada-text-dim cursor-pointer hover:text-scada-text" />
            </div>
            <p className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text leading-relaxed">
              {myLLMOutput?.alerts?.radio || 'No radio broadcast drafted'}
            </p>
          </div>
        </div>
      )}

      {/* NARRATIVE */}
      <SectionHeader icon={<BookOpen />} title="INCIDENT NARRATIVE" isExpanded={expanded.narrative} onToggle={() => toggle('narrative')} />
      {expanded.narrative && (
        <div className="p-4 border-b border-scada-border bg-scada-panel/30">
          {myLLMOutput?.narrative_update ? (
            <p className="text-[10px] font-mono text-scada-text leading-relaxed whitespace-pre-wrap">
              {myLLMOutput.narrative_update}
            </p>
          ) : (
            <p className="text-[10px] font-mono text-scada-text-dim italic">
              {activeIncident ? 'Analyzing incident — LLM processing...' : 'No active incident'}
            </p>
          )}
        </div>
      )}

      {/* LOGS */}
      <SectionHeader icon={<FileText />} title="INCIDENT LOG"isExpanded={expanded.logs} onToggle={() => toggle('logs')} />
      {expanded.logs && (
        <div className="border-b border-scada-border">
          {logs.length > 0 ? (
            logs.map((log, i) => (
              <div key={i} className="flex gap-3 px-4 py-2 text-[10px] font-mono border-b border-scada-border/50 last:border-0 hover:bg-scada-panel transition-colors">
                <span className="text-scada-text-dim whitespace-nowrap">{log.time}</span>
                <span className="text-scada-text">{log.event}</span>
              </div>
            ))
          ) : (
            <div className="px-4 py-3 text-[10px] font-mono text-scada-text-dim italic">
              No events recorded
            </div>
          )}
        </div>
      )}

      {/* RECENT INCIDENTS */}
      {cityIncidents.length > 0 && (
        <>
          <SectionHeader
            icon={<History />}
            title={`${cityIncidents.length} ACTIVE INCIDENTS`}
            isExpanded={expanded.history}
            onToggle={() => toggle('history')}
          />
          {expanded.history && (
            <div className="border-b border-scada-border">
              {cityIncidents
                .slice()
                .sort((a, b) => {
                  // My assigned incidents always bubble to the top
                  const aIsMe = a.assigned_operator === operator;
                  const bIsMe = b.assigned_operator === operator;
                  if (aIsMe && !bIsMe) return -1;
                  if (!aIsMe && bIsMe) return 1;
                  return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
                })
                .map((inc) => {
                  // An incident is only "mine" if explicitly assigned to this operator
                  const isAssignedToMe = inc.assigned_operator === operator;
                  const isMyCase = isAssignedToMe;
                  const isPending = !inc.assigned_operator; // not yet assigned to anyone
                  const isFocused = activeIncident?.id === inc.id;
                  
                  return (
                  <div
                    key={inc.id}
                    className={`flex flex-col gap-2 px-4 py-2.5 border-b border-scada-border/50 last:border-0 transition-colors ${
                      'cursor-pointer hover:bg-scada-border/30'
                    } ${
                      isFocused
                        ? 'bg-scada-blue/10 border-l-2 border-l-scada-blue'
                        : isMyCase
                        ? 'bg-scada-blue/5 border-l-2 border-l-scada-blue'
                        : isPending
                        ? 'opacity-90'
                        : ''
                    }`}
                    onClick={() => {
                      setIncident(inc);
                      api.getLLMOutput(inc.id).then((llm: any) => {
                        if (llm && typeof llm === 'object') {
                          setLLMOutput(llm);
                        }
                      }).catch(() => {
                        if (useIncidentStore.getState().currentIncident?.id === inc.id) {
                          setLLMOutput(null);
                        }
                      });
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.5 uppercase flex-shrink-0 ${
                          inc.severity === 'critical'
                            ? 'bg-scada-red/20 text-scada-red border border-scada-red/50'
                            : inc.severity === 'major'
                            ? 'bg-scada-yellow/20 text-scada-yellow border border-scada-yellow/50'
                            : 'bg-scada-border text-scada-text-dim border border-scada-border'
                        }`}
                      >
                        {inc.severity}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <div className="text-[10px] font-mono text-scada-text truncate uppercase">
                            {inc.on_street}{inc.cross_street ? ` & ${inc.cross_street}` : ''}
                          </div>
                          {isMyCase && (
                            <span className="text-[8px] font-mono font-bold px-1 py-0.5 bg-scada-blue text-scada-bg uppercase shrink-0">MY CASE</span>
                          )}
                        </div>
                        <div className="flex items-center justify-between text-[9px] font-mono mt-0.5">
                          <span className="text-scada-text-dim">{formatTime(inc.detected_at)}</span>
                          {inc.assigned_operator && inc.assigned_operator !== operator && (
                            <span className="text-scada-red border border-scada-red px-1 uppercase">
                              VIEW: {inc.assigned_operator.split(' ')[0]}
                            </span>
                          )}
                          {isPending && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                api.claimIncident(inc.id, operator)
                                  .then(() => {
                                    useIncidentStore.getState().updateIncidentAssignment(inc.id, operator);
                                  })
                                  .catch(console.error);
                              }}
                              className="text-scada-green border border-scada-green px-1.5 py-0.5 uppercase tracking-widest hover:bg-scada-green hover:text-scada-bg transition-colors"
                            >
                              CLAIM
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
              </div>
            )}
          </>
        )}
    </div>
  );
};

const SectionHeader: React.FC<{ icon: React.ReactNode; title: string; isExpanded: boolean; onToggle: () => void }> = ({ icon, title, isExpanded, onToggle }) => (
  <button onClick={onToggle} className="w-full flex items-center justify-between p-3 border-b border-scada-border bg-scada-bg hover:bg-scada-panel transition-colors text-white">
    <div className="flex items-center gap-3">
      {React.cloneElement(icon as React.ReactElement<any>, { className: 'h-4 w-4 text-white/70' })}
      <span className="text-[11px] font-mono uppercase tracking-wider font-bold">{title}</span>
    </div>
    {isExpanded ? <ChevronDown className="h-4 w-4 text-white/50" /> : <ChevronRight className="h-4 w-4 text-white/50" />}
  </button>
);

export default Sidebar;
