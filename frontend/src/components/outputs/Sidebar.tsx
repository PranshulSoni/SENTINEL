import React, { useState } from 'react';
import {
  TrafficCone,
  Navigation,
  Share2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  MapPin,
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

const SIGNAL_RETIMING = [
  'Extend N/S Green on Broadway by 45s',
  'Reduce E/W Green on 34th St by 15s',
  'Pre-empt spillback at 7th Ave & W 33rd',
];

const DIVERSION = {
  name: 'Primary: 10th Ave Bypass',
  path: ['10th Ave', 'W 42nd St', '9th Ave', 'W 30th St'],
  status: 'READY to Activate',
};

const ALERTS = {
  vms: 'ACCIDENT W 34TH ST\nUSE 10TH AVE ALT\nDELAY: 15-25 MIN',
  radio: 'Attention motorists. Accident at Broadway and W 34th St. 3 lanes blocked. Use 10th Ave as alternate. Expected delays of 15 to 25 minutes.',
};

const LOGS = [
  { time: '14:23:17', event: 'Detection: Speed drop on Segment 1001' },
  { time: '14:24:03', event: 'Action: Signal recommendations posted' },
  { time: '14:27:45', event: 'Update: FDNY Engine 26 on scene' },
];

const Sidebar: React.FC = () => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    incident: true,
    signals: true,
    diversion: true,
    alerts: true,
    logs: false,
  });

  const toggle = (sec: string) => setExpanded((p) => ({ ...p, [sec]: !p[sec] }));

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-8">
      
      {/* INCIDENT HEADER */}
      <div className="p-4 border-b border-scada-border">
        <div className="flex items-start gap-3">
          <div className="mt-1 p-2 bg-scada-red/10 border border-scada-red">
            <AlertTriangle className="h-4 w-4 text-scada-red" />
          </div>
          <div>
            <span className="text-[10px] font-mono text-scada-red uppercase mb-1 block">Active Critical</span>
            <h3 className="text-sm font-bold text-scada-header uppercase leading-tight mb-2">
              {INCIDENT.street}
            </h3>
            <div className="flex flex-col gap-1 text-[10px] font-mono text-scada-text">
              <span className="text-scada-text-dim">ID: {INCIDENT.id} | TYPE: {INCIDENT.type}</span>
              <span className="text-scada-text-dim">DETECTED: {INCIDENT.detectedAt} | LANES: {INCIDENT.lanesBlocked} blocked</span>
            </div>
          </div>
        </div>
      </div>

      {/* SIGNALS */}
      <SectionHeader icon={<TrafficCone />} title="SIGNALS" isExpanded={expanded.signals} onToggle={() => toggle('signals')} />
      {expanded.signals && (
        <div className="p-4 border-b border-scada-border space-y-3 bg-scada-panel/30">
          <div className="text-[11px] font-mono text-scada-text">
            <ul className="list-disc pl-4 space-y-2 text-scada-text-dim">
              {SIGNAL_RETIMING.map((sig, i) => (
                <li key={i}>{sig}</li>
              ))}
            </ul>
          </div>
          <button className="w-full mt-2 border border-scada-text-dim py-2 text-[10px] font-mono uppercase hover:bg-scada-text hover:text-scada-bg transition-colors">
            APPLY ALL TIMINGS
          </button>
        </div>
      )}

      {/* DIVERSION */}
      <SectionHeader icon={<Navigation />} title="DIVERSION PLAN" isExpanded={expanded.diversion} onToggle={() => toggle('diversion')} />
      {expanded.diversion && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-panel/30">
          <div>
            <span className="text-[11px] font-mono text-scada-text block mb-2">{DIVERSION.name}</span>
            <div className="flex flex-wrap items-center gap-2">
              {DIVERSION.path.map((step, i) => (
                <React.Fragment key={i}>
                  <span className="text-[9px] font-mono px-2 py-1 bg-scada-border text-scada-text">{step}</span>
                  {i < DIVERSION.path.length - 1 && <ArrowRight className="h-3 w-3 text-scada-text-dim" />}
                </React.Fragment>
              ))}
            </div>
          </div>
          <button className="w-full border border-scada-text-dim py-2 text-[10px] font-mono uppercase hover:bg-scada-text hover:text-scada-bg transition-colors">
            ACTIVATE ROUTE
          </button>
        </div>
      )}

      {/* ALERTS */}
      <SectionHeader icon={<Share2 />} title="PUBLIC ALERTS" isExpanded={expanded.alerts} onToggle={() => toggle('alerts')} />
      {expanded.alerts && (
        <div className="p-4 border-b border-scada-border space-y-4 bg-scada-panel/30">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-scada-text-dim">VMS SIGNBOARD</span>
              <CheckCircle className="h-3 w-3 text-scada-text-dim cursor-pointer hover:text-scada-text" />
            </div>
            <pre className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text">
              {ALERTS.vms}
            </pre>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-scada-text-dim">RADIO BROADCAST</span>
              <CheckCircle className="h-3 w-3 text-scada-text-dim cursor-pointer hover:text-scada-text" />
            </div>
            <p className="text-[10px] font-mono bg-scada-bg p-2 border border-scada-border/50 text-scada-text leading-relaxed">
              {ALERTS.radio}
            </p>
          </div>
        </div>
      )}

      {/* LOGS */}
      <SectionHeader icon={<FileText />} title="INCIDENT LOG" isExpanded={expanded.logs} onToggle={() => toggle('logs')} />
      {expanded.logs && (
        <div className="border-b border-scada-border">
          {LOGS.map((log, i) => (
            <div key={i} className="flex gap-3 px-4 py-2 text-[10px] font-mono border-b border-scada-border/50 last:border-0 hover:bg-scada-panel transition-colors">
              <span className="text-scada-text-dim whitespace-nowrap">{log.time}</span>
              <span className="text-scada-text">{log.event}</span>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};

const SectionHeader: React.FC<{ icon: React.ReactNode; title: string; isExpanded: boolean; onToggle: () => void }> = ({ icon, title, isExpanded, onToggle }) => (
  <button onClick={onToggle} className="w-full flex items-center justify-between p-3 border-b border-scada-border bg-scada-bg hover:bg-scada-panel transition-colors text-scada-text-dim">
    <div className="flex items-center gap-3">
      {React.cloneElement(icon as React.ReactElement, { className: 'h-4 w-4' })}
      <span className="text-[11px] font-mono uppercase tracking-wider">{title}</span>
    </div>
    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
  </button>
);

export default Sidebar;
