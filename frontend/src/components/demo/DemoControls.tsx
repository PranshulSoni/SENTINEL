import React, { useState } from 'react';
import { Zap, ChevronDown, ChevronUp, Loader2, CheckCircle, AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';

type Severity = 'minor' | 'major' | 'critical';

const STREETS = [
  'W 34th St & 7th Ave',
  'Broadway & 34th St',
  '10th Ave & 42nd St',
  'W 34th St & 8th Ave',
  '7th Ave & 33rd St',
];

const SEVERITY_COLORS: Record<Severity, string> = {
  minor: 'text-yellow-400 border-yellow-400',
  major: 'text-orange-400 border-orange-400',
  critical: 'text-scada-red border-scada-red',
};

const DemoControls: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [severity, setSeverity] = useState<Severity>('major');
  const [street, setStreet] = useState(STREETS[0]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleInject = async () => {
    setStatus('loading');
    setMessage('');
    try {
      const res = await api.injectIncident({ severity, street_name: street });
      if (res.status === 'injected') {
        setStatus('success');
        setMessage(`${severity.toUpperCase()} incident injected at ${street}`);
      } else {
        setStatus('error');
        setMessage(res.detail || 'Injection failed');
      }
    } catch (e: any) {
      setStatus('error');
      setMessage(e.message || 'Network error');
    }
    setTimeout(() => {
      setStatus('idle');
      setMessage('');
    }, 4000);
  };

  return (
    <div className="fixed bottom-4 right-4 z-[2000] w-64 font-mono">
      {/* Header toggle */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-scada-panel border border-scada-red text-scada-red text-[10px] uppercase tracking-widest hover:bg-scada-red hover:text-scada-bg transition-colors"
      >
        <span className="flex items-center gap-2">
          <Zap className="h-3 w-3" />
          DEMO INJECTOR
        </span>
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
      </button>

      {open && (
        <div className="bg-scada-panel border border-t-0 border-scada-border p-3 space-y-3">
          {/* Severity selector */}
          <div>
            <div className="text-[9px] text-scada-text-dim mb-1.5 uppercase tracking-wider">Severity</div>
            <div className="flex gap-1">
              {(['minor', 'major', 'critical'] as Severity[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverity(s)}
                  className={`flex-1 px-1 py-1 text-[9px] uppercase border transition-colors ${
                    severity === s
                      ? `${SEVERITY_COLORS[s]} bg-opacity-10`
                      : 'text-scada-text-dim border-scada-border hover:text-scada-text'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Street selector */}
          <div>
            <div className="text-[9px] text-scada-text-dim mb-1.5 uppercase tracking-wider">Location</div>
            <select
              value={street}
              onChange={(e) => setStreet(e.target.value)}
              className="w-full bg-scada-bg border border-scada-border text-scada-text text-[9px] px-2 py-1.5 uppercase tracking-wide outline-none focus:border-scada-text-dim"
            >
              {STREETS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {/* Inject button */}
          <button
            onClick={handleInject}
            disabled={status === 'loading'}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-scada-red text-scada-bg text-[10px] uppercase tracking-widest font-bold hover:opacity-80 disabled:opacity-50 transition-opacity"
          >
            {status === 'loading' ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                INJECTING...
              </>
            ) : (
              <>
                <Zap className="h-3 w-3" />
                INJECT INCIDENT
              </>
            )}
          </button>

          {/* Status feedback */}
          {message && (
            <div
              className={`flex items-start gap-2 text-[9px] ${
                status === 'success' ? 'text-green-400' : 'text-scada-red'
              }`}
            >
              {status === 'success' ? (
                <CheckCircle className="h-3 w-3 mt-0.5 flex-shrink-0" />
              ) : (
                <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
              )}
              <span className="leading-tight">{message}</span>
            </div>
          )}

          <div className="text-[8px] text-scada-text-dim leading-tight">
            Bypasses detector warmup. LLM output appears via WebSocket in ~3s.
          </div>
        </div>
      )}
    </div>
  );
};

export default DemoControls;
