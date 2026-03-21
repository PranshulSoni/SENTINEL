import React, { useState } from 'react';
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
} from 'lucide-react';

/* ═══ STATIC MOCK DATA ═══ */
const INCIDENT = {
  id: 'INC-4827',
  street: 'BROADWAY & W 34TH ST',
  type: 'Multi-Vehicle Collision',
  detectedAt: '14:23:17',
  lanesBlocked: '3 of 4',
};

const ALERTS = {
  vms: 'ACCIDENT W 34TH ST\nUSE 10TH AVE ALT\nDELAY: 15-25 MIN',
  radio: 'Attention motorists. Accident at Broadway and W 34th St. 3 lanes blocked. Use 10th Ave as alternate. Expected delays of 15 to 25 minutes.',
};

const LOGS = [
  { time: '14:23:17', type: 'alert', event: 'Detection: Speed drop on Segment 1001' },
  { time: '14:24:03', type: 'success', event: 'Action: Signal recommendations posted' },
  { time: '14:27:45', type: 'info', event: 'Update: FDNY Engine 26 on scene' },
];

const Sidebar: React.FC = () => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    incident: true,
    signals: true,
    diversion: true,
    alerts: true,
    logs: true,
  });

  const toggle = (sec: string) => setExpanded((p) => ({ ...p, [sec]: !p[sec] }));

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-8">
      
      {/* INCIDENT HEADER */}
      <div className="p-4 border-b border-scada-border">
        <div className="flex items-start gap-3">
          <div className="mt-1 p-2 bg-scada-red/10 border border-scada-red/50">
            <AlertTriangle className="h-4 w-4 text-scada-red" />
          </div>
          <div>
            <span className="text-[10px] font-mono text-scada-red uppercase mb-1 block tracking-wider font-bold">
              ● Active Critical
            </span>
            <h3 className="text-sm font-bold text-scada-header uppercase leading-tight mb-2">
              {INCIDENT.street}
            </h3>
            <div className="flex flex-col gap-1 text-[10px] font-mono">
              <span className="text-scada-text">
                <span className="text-scada-text-dim">ID:</span> {INCIDENT.id} <span className="text-scada-text-dim px-1">|</span> <span className="text-scada-text-dim">TYPE:</span> <span className="text-scada-yellow">{INCIDENT.type}</span>
              </span>
              <span className="text-scada-text">
                <span className="text-scada-text-dim">DETECTED:</span> {INCIDENT.detectedAt} <span className="text-scada-text-dim px-1">|</span> <span className="text-scada-text-dim">LANES:</span> <span className="text-scada-red font-bold">{INCIDENT.lanesBlocked} blocked</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* SIGNALS */}
      <SectionHeader icon={<TrafficCone />} title="SIGNALS" isExpanded={expanded.signals} onToggle={() => toggle('signals')} />
      {expanded.signals && (
        <div className="p-4 border-b border-scada-border space-y-3 bg-scada-surface">
          <div className="text-[11px] font-mono text-scada-text space-y-2">
            <div className="flex items-start gap-2">
              <span className="text-scada-green font-bold">[EXTEND]</span>
              <span>N/S Green on Broadway by <span className="text-scada-green font-bold">+45s</span></span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-scada-red font-bold">[REDUCE]</span>
              <span>E/W Green on 34th St by <span className="text-scada-red font-bold">-15s</span></span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-scada-blue font-bold">[PRE-EMPT]</span>
              <span>Spillback at 7th Ave & W 33rd</span>
            </div>
          </div>
          <button className="w-full mt-2 border border-scada-green/30 bg-scada-green/10 text-scada-green py-2 text-[10px] font-mono font-bold uppercase hover:bg-scada-green hover:text-black transition-colors">
            APPLY ALL TIMINGS
          </button>
        </div>
      )}

      {/* DIVERSION */}
      <SectionHeader icon={<Navigation />} title="DIVERSION PLAN" isExpanded={expanded.diversion} onToggle={() => toggle('diversion')} />
      {expanded.diversion && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-surface">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[11px] font-mono text-scada-header font-bold block">10th Ave Bypass</span>
              <span className="text-[9px] font-mono px-1.5 py-0.5 border border-scada-blue/30 bg-scada-blue/10 text-scada-blue font-bold">READY</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {['10th Ave', 'W 42nd St', '9th Ave', 'W 30th St'].map((step, i, arr) => (
                <React.Fragment key={i}>
                  <span className="text-[9px] font-mono px-2 py-1 border border-scada-border text-scada-text">{step}</span>
                  {i < arr.length - 1 && <ArrowRight className="h-3 w-3 text-scada-text-dim" />}
                </React.Fragment>
              ))}
            </div>
          </div>
          <button className="w-full border border-scada-blue/30 bg-scada-blue/5 text-scada-blue py-2 text-[10px] font-mono font-bold uppercase hover:bg-scada-blue hover:text-black transition-colors">
            ACTIVATE ROUTE
          </button>
        </div>
      )}

      {/* ALERTS */}
      <SectionHeader icon={<Share2 />} title="PUBLIC ALERTS" isExpanded={expanded.alerts} onToggle={() => toggle('alerts')} />
      {expanded.alerts && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-surface">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-scada-text-dim">VMS SIGNBOARD</span>
              <CheckCircle className="h-3 w-3 text-scada-green cursor-pointer hover:text-scada-green" />
            </div>
            <pre className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border text-scada-yellow leading-relaxed">
              {ALERTS.vms}
            </pre>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-scada-text-dim">RADIO BROADCAST</span>
              <CheckCircle className="h-3 w-3 text-scada-green cursor-pointer hover:text-scada-green" />
            </div>
            <p className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border text-scada-header leading-relaxed">
              {ALERTS.radio}
            </p>
          </div>
        </div>
      )}

      {/* LOGS */}
      <SectionHeader icon={<FileText />} title="INCIDENT LOG" isExpanded={expanded.logs} onToggle={() => toggle('logs')} />
      {expanded.logs && (
        <div className="border-b border-scada-border bg-scada-surface">
          {LOGS.map((log, i) => (
            <div key={i} className="flex gap-3 px-4 py-2 text-[10px] font-mono border-b border-scada-border last:border-0">
              <span className="text-scada-text-dim whitespace-nowrap">{log.time}</span>
              <span className={`flex-1 ${
                log.type === 'alert' ? 'text-scada-red' :
                log.type === 'success' ? 'text-scada-green' :
                'text-scada-blue'
              }`}>
                {log.event}
              </span>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};

const SectionHeader: React.FC<{ icon: React.ReactNode; title: string; isExpanded: boolean; onToggle: () => void }> = ({ icon, title, isExpanded, onToggle }) => (
  <button onClick={onToggle} className="w-full flex items-center justify-between p-3 border-b border-scada-border bg-scada-panel hover:bg-scada-surface transition-colors text-scada-text-dim">
    <div className="flex items-center gap-3">
      {React.cloneElement(icon as React.ReactElement, { className: 'h-4 w-4 text-scada-text' })}
      <span className="text-[11px] font-mono uppercase font-bold text-scada-text tracking-wider">{title}</span>
    </div>
    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
  </button>
);

export default Sidebar;
