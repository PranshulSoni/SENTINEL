import React, { useState, useEffect, useRef } from 'react';
import { Zap, Loader2, CheckCircle, AlertTriangle, ChevronDown } from 'lucide-react';
import { api } from '../../services/api';
import { useFeedStore, useOperatorStore } from '../../store';

type Severity = 'minor' | 'major' | 'critical';

const SEVERITY_COLORS: Record<Severity, string> = {
  minor: 'border-yellow-400 text-yellow-400',
  major: 'border-orange-400 text-orange-400',
  critical: 'border-scada-red text-scada-red',
};

const DemoControls: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [severity, setSeverity] = useState<Severity>('major');
  const [streets, setStreets] = useState<string[]>([]);
  const [street, setStreet] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const panelRef = useRef<HTMLDivElement>(null);

  const city = useFeedStore((s) => s.city);
  const operator = useOperatorStore((s) => s.operator);

  useEffect(() => {
    api.getDemoStreets(city).then((data: { streets: Array<{ name: string }> }) => {
      const names = data.streets.map((s) => s.name);
      setStreets(names);
      if (names.length > 0) setStreet(names[0]);
    }).catch(() => {
      const fallback = city === 'chandigarh'
        ? ['Madhya Marg & Sector 17 Chowk', 'Jan Marg & IT Park Chowk', 'Dakshin Marg & Transport Chowk']
        : ['W 34th St & 7th Ave', 'Broadway & 34th St', '10th Ave & 42nd St'];
      setStreets(fallback);
      setStreet(fallback[0]);
    });
  }, [city]);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const handleInject = async () => {
    setStatus('loading');
    setMessage('');
    try {
      const res = await api.injectIncident({ severity, street_name: street, city, operator });
      if (res.status === 'injected') {
        setStatus('success');
        setMessage(`${severity.toUpperCase()} at ${street}`);
      } else {
        setStatus('error');
        setMessage(res.detail || 'Injection failed');
      }
    } catch (e: any) {
      setStatus('error');
      setMessage(e.message || 'Network error');
    }
    setTimeout(() => { setStatus('idle'); setMessage(''); }, 4000);
  };

  return (
    <div className="relative" ref={panelRef}>
      {/* Compact navbar button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-mono uppercase tracking-widest border transition-colors ${
          open
            ? 'bg-scada-red border-scada-red text-scada-bg'
            : 'border-scada-red/60 text-scada-red/80 hover:border-scada-red hover:text-scada-red'
        }`}
      >
        <Zap className="h-3 w-3" />
        <span>Demo</span>
        <ChevronDown className={`h-2.5 w-2.5 transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown panel — anchored below the button, NOT fixed */}
      {open && (
        <div className="absolute top-full left-0 mt-2 w-64 bg-scada-panel border border-scada-border shadow-2xl z-[9999] font-mono">
          <div className="px-3 py-2 border-b border-scada-border flex items-center justify-between">
            <span className="text-[9px] uppercase tracking-widest text-scada-red flex items-center gap-1.5">
              <Zap className="h-3 w-3" /> Demo Injector
            </span>
            <span className="text-[8px] text-scada-text-dim uppercase">{city}</span>
          </div>

          <div className="p-3 space-y-3">
            {/* Severity */}
            <div>
              <div className="text-[9px] text-scada-text-dim mb-1.5 uppercase tracking-wider">Severity</div>
              <div className="flex gap-1">
                {(['minor', 'major', 'critical'] as Severity[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSeverity(s)}
                    className={`flex-1 px-1 py-1 text-[9px] uppercase border transition-colors ${
                      severity === s
                        ? SEVERITY_COLORS[s]
                        : 'text-scada-text-dim border-scada-border hover:text-scada-text'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Street */}
            <div>
              <div className="text-[9px] text-scada-text-dim mb-1.5 uppercase tracking-wider">Location</div>
              <select
                value={street}
                onChange={(e) => setStreet(e.target.value)}
                disabled={streets.length === 0}
                className="w-full bg-scada-bg border border-scada-border text-scada-text text-[9px] px-2 py-1.5 uppercase tracking-wide outline-none focus:border-scada-text-dim disabled:opacity-50"
              >
                {streets.length === 0
                  ? <option value="">Loading...</option>
                  : streets.map((s) => <option key={s} value={s}>{s}</option>)
                }
              </select>
            </div>

            {/* Inject */}
            <button
              onClick={handleInject}
              disabled={status === 'loading'}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-scada-red text-scada-bg text-[10px] uppercase tracking-widest font-bold hover:opacity-80 disabled:opacity-50 transition-opacity"
            >
              {status === 'loading' ? (
                <><Loader2 className="h-3 w-3 animate-spin" /> Injecting...</>
              ) : (
                <><Zap className="h-3 w-3" /> Inject Incident</>
              )}
            </button>

            {/* Feedback */}
            {message && (
              <div className={`flex items-start gap-2 text-[9px] ${status === 'success' ? 'text-green-400' : 'text-scada-red'}`}>
                {status === 'success'
                  ? <CheckCircle className="h-3 w-3 mt-0.5 shrink-0" />
                  : <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                }
                <span className="leading-tight">{message}</span>
              </div>
            )}

            <div className="text-[8px] text-scada-text-dim leading-tight">
              LLM output appears via WebSocket in ~3s.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DemoControls;
