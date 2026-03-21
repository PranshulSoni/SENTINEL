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
    history: false,
  });

  const [timingsApplied, setTimingsApplied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);


  const { currentIncident, llmOutput, incidents, setIncident, setLLMOutput, resolveIncident, dismissIncident, congestionZones } = useIncidentStore();
  const { segments, city } = useFeedStore();
  const { operator } = useOperatorStore();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const prevIncidentIdRef = useRef<string | null>(null);
  const prevLlmRef = useRef<boolean>(false);

  // Client-side city filter as safety net
  const cityIncidents = incidents.filter((inc) => inc.city === city);

  // Log when incident is detected
  useEffect(() => {
    if (currentIncident && currentIncident.id !== prevIncidentIdRef.current) {
      prevIncidentIdRef.current = currentIncident.id;
      setLogs((prev) => [
        ...prev,
        { time: formatTime(currentIncident.detected_at), event: `Detection: Incident ${currentIncident.id} on ${currentIncident.on_street}` },
      ]);
    }
  }, [currentIncident]);

  // Log when LLM output arrives
  useEffect(() => {
    if (llmOutput && !prevLlmRef.current) {
      prevLlmRef.current = true;
      setLogs((prev) => [
        ...prev,
        { time: formatTime(new Date().toISOString()), event: 'Action: LLM intelligence received' },
      ]);
    }
    if (!llmOutput) {
      prevLlmRef.current = false;
    }
  }, [llmOutput]);

  const toggle = (sec: string) => setExpanded((p) => ({ ...p, [sec]: !p[sec] }));

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-8">
      
      {/* INCIDENT HEADER */}
      <div className="p-4 border-b border-scada-border">
        {currentIncident ? (
          <div className="flex items-start gap-3">
            <div className="mt-1 p-2 bg-scada-red/10 border border-scada-red">
              <AlertTriangle className="h-4 w-4 text-scada-red" />
            </div>
            <div>
              <span className="text-[10px] font-mono text-scada-red uppercase mb-1 block">
                Active {currentIncident.severity}
                {cityIncidents.length > 1 && (
                  <span className="ml-2 bg-scada-red/20 px-1.5 py-0.5 text-[9px]">
                    {cityIncidents.length} INCIDENTS
                  </span>
                )}
              </span>
              <h3 className="text-sm font-bold text-scada-header uppercase leading-tight mb-2">
                {currentIncident.on_street} & {currentIncident.cross_street}
              </h3>
              <div className="flex flex-col gap-1 text-[10px] font-mono text-scada-text mt-2">
                <span className="text-scada-text-dim">
                  ID: {currentIncident.id} | SEVERITY: {currentIncident.severity.toUpperCase()}
                </span>
                <span className="text-scada-text-dim">
                  DETECTED: {formatTime(currentIncident.detected_at)} | SEGMENTS: {currentIncident.affected_segment_ids.length} affected
                </span>
                <span className="text-scada-blue bg-scada-blue/10 px-2 py-1 border border-scada-blue/20 mt-1 inline-block w-fit">
                  HANDLED BY: {currentIncident.assigned_operator || operator}
                </span>
              </div>
              <button 
                onClick={async () => {
                  try {
                    await api.resolveIncident(currentIncident.id, operator);
                    resolveIncident(currentIncident.id);
                  } catch (e: any) {
                    const msg = await e?.json?.().catch(() => null);
                    console.error('Failed to resolve:', msg?.detail || e);
                  }
                }}
                disabled={!!currentIncident.assigned_operator && currentIncident.assigned_operator !== operator}
                className={`mt-2 w-full border py-1.5 text-[10px] font-mono uppercase transition-colors ${
                  currentIncident.assigned_operator && currentIncident.assigned_operator !== operator
                    ? 'border-gray-600 text-gray-600 cursor-not-allowed opacity-50'
                    : 'border-scada-green text-scada-green hover:bg-scada-green hover:text-scada-bg'
                }`}
              >
                RESOLVE INCIDENT
              </button>
              <button 
                onClick={async () => {
                  try {
                    await api.dismissIncident(currentIncident.id, operator);
                    dismissIncident(currentIncident.id);
                  } catch (e: any) {
                    const msg = await e?.json?.().catch(() => null);
                    console.error('Failed to dismiss:', msg?.detail || e);
                  }
                }}
                disabled={!!currentIncident.assigned_operator && currentIncident.assigned_operator !== operator}
                className={`mt-1 w-full border py-1.5 text-[10px] font-mono uppercase transition-colors ${
                  currentIncident.assigned_operator && currentIncident.assigned_operator !== operator
                    ? 'border-gray-600 text-gray-600 cursor-not-allowed opacity-50'
                    : 'border-yellow-500 text-yellow-500 hover:bg-yellow-500 hover:text-scada-bg'
                }`}
              >
                ⚠ DISMISS AS FALSE ALARM
              </button>
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
          {llmOutput?.signal_retiming?.intersections && llmOutput.signal_retiming.intersections.length > 0 ? (
            <>
              <div className="text-[11px] font-mono text-scada-text">
                <ul className="list-disc pl-4 space-y-2 text-scada-text-dim">
                  {llmOutput.signal_retiming.intersections.map((sig: any, i: number) => (
                    <li key={i}>
                      <span className="text-scada-text">{sig.name ?? 'Unknown intersection'}</span>
                      <br />
                      N/S: {sig.current_ns_green ?? '?'}s → {sig.recommended_ns_green ?? '?'}s | E/W: {sig.current_ew_green ?? '?'}s → {sig.recommended_ew_green ?? '?'}s
                    </li>
                  ))}
                </ul>
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
              {currentIncident && (
                <button
                  onClick={async () => {
                    setRegenerating(true);
                    try {
                      const result = await api.regenerateLLM(currentIncident.id);
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
              {currentIncident ? 'Analyzing incident — LLM processing...' : 'No active incident'}
            </p>
          )}
        </div>
      )}

      {/* DIVERSION */}
      <SectionHeader icon={<Navigation />} title="DIVERSION PLAN" isExpanded={expanded.diversion} onToggle={() => toggle('diversion')} />
      {expanded.diversion && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-panel/30">
          {llmOutput?.diversions?.routes && llmOutput.diversions.routes.length > 0 ? (
            llmOutput.diversions.routes.map((route, ri) => (
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
          ) : (
            <p className="text-[10px] font-mono text-scada-text-dim italic">
              {currentIncident ? 'Analyzing incident — LLM processing...' : 'No active incident'}
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
              {congestionZones.length > 0 && (
                <span className="ml-auto text-[9px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">
                  {congestionZones.length} ACTIVE
                </span>
              )}
            </h3>
            {congestionZones.length > 0 ? (
              <div className="space-y-2">
                {congestionZones.map((zone: any) => (
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
                {currentIncident ? 'No congestion detected in area' : 'Monitoring traffic flow...'}
              </p>
            )}
          </section>
        </div>
      )}

      {/* ALERTS */}
      <SectionHeader icon={<Share2 />} title="PUBLIC ALERTS" isExpanded={expanded.alerts} onToggle={() => toggle('alerts')} />
      {expanded.alerts && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-panel/30">
          {llmOutput?.alerts && (llmOutput.alerts.vms || llmOutput.alerts.radio || llmOutput.alerts.social_media) ? (
            <>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono text-scada-text-dim">VMS SIGNBOARD</span>
                  <CheckCircle className="h-3 w-3 text-scada-text-dim cursor-pointer hover:text-scada-text" />
                </div>
                <pre className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text whitespace-pre-wrap">
                  {llmOutput.alerts.vms || 'No VMS message available'}
                </pre>
              </div>
              
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono text-scada-text-dim">RADIO BROADCAST</span>
                  <CheckCircle className="h-3 w-3 text-scada-text-dim cursor-pointer hover:text-scada-text" />
                </div>
                <p className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text leading-relaxed">
                  {llmOutput.alerts.radio || 'No radio broadcast drafted'}
                </p>
              </div>

              {llmOutput.alerts.social_media && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono text-scada-text-dim">SOCIAL MEDIA</span>
                    <CheckCircle className="h-3 w-3 text-scada-text-dim cursor-pointer hover:text-scada-text" />
                  </div>
                  <p className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text leading-relaxed">
                    {llmOutput.alerts.social_media}
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-[10px] font-mono text-scada-text-dim italic">No alerts generated</p>
          )}
        </div>
      )}

      {/* NARRATIVE */}
      <SectionHeader icon={<BookOpen />} title="INCIDENT NARRATIVE" isExpanded={expanded.narrative} onToggle={() => toggle('narrative')} />
      {expanded.narrative && (
        <div className="p-4 border-b border-scada-border bg-scada-panel/30">
          {llmOutput?.narrative_update ? (
            <p className="text-[10px] font-mono text-scada-text leading-relaxed whitespace-pre-wrap">
              {llmOutput.narrative_update}
            </p>
          ) : (
            <p className="text-[10px] font-mono text-scada-text-dim italic">
              {currentIncident ? 'Analyzing incident — LLM processing...' : 'No active incident'}
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
                .slice(0, 5)
                .map((inc) => {
                  const isAssignedToMe = !inc.assigned_operator || inc.assigned_operator === operator;
                  const isMyCase = inc.assigned_operator === operator;
                  
                  return (
                  <div
                    key={inc.id}
                    className={`flex items-center gap-3 px-4 py-2.5 border-b border-scada-border/50 last:border-0 transition-colors ${
                      isAssignedToMe ? 'cursor-pointer hover:bg-scada-border/30' : 'opacity-30 pointer-events-none'
                    } ${isMyCase ? 'bg-scada-blue/5 border-l-2 border-l-scada-blue' : ''}`}
                    onClick={() => {
                      if (!isAssignedToMe) return;
                      setIncident(inc);
                      api.getLLMOutput(inc.id).then((llm: any) => {
                        if (llm && typeof llm === 'object') {
                          setLLMOutput(llm);
                        }
                      }).catch(() => {});
                    }}
                  >
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
                            → {inc.assigned_operator.split(' ')[0]}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )})}
            </div>
          )}
        </>
      )}

    </div>
  );
};

const SectionHeader: React.FC<{ icon: React.ReactNode; title: string; isExpanded: boolean; onToggle: () => void }> = ({ icon, title, isExpanded, onToggle }) => (
  <button onClick={onToggle} className="w-full flex items-center justify-between p-3 border-b border-scada-border bg-scada-bg hover:bg-scada-panel transition-colors text-scada-text-dim">
    <div className="flex items-center gap-3">
      {React.cloneElement(icon as React.ReactElement<any>, { className: 'h-4 w-4' })}
      <span className="text-[11px] font-mono uppercase tracking-wider">{title}</span>
    </div>
    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
  </button>
);

export default Sidebar;
