import React, { useState, useEffect, useRef } from 'react';
import {
  MapPin, Clock, AlertTriangle, AlertCircle, ShieldCheck, X, AlertOctagon, Navigation,
  CheckCircle2, Search, ChevronDown, Camera, Image as ImageIcon
} from 'lucide-react';
import { api } from '../../services/api';
import { useFeedStore, useIncidentStore } from '../../store';
import { inferIncidentCity } from '../../utils/city';

// ─── City Streets ─────────────────────────────────────
const CITY_STREETS: Record<string, string[]> = {
  nyc: [
    'W 34th St & 7th Ave',
    'Broadway & 34th St',
    '10th Ave & 42nd St',
    'W 34th St & 8th Ave',
    '7th Ave & 33rd St'
  ],
  chandigarh: [
    'Madhya Marg & Sector 17 Chowk',
    'Madhya Marg & Sector 22 Chowk',
    'Madhya Marg & Aroma Light',
    'Madhya Marg & PGI Chowk',
    'Jan Marg & IT Park Chowk',
    'Jan Marg & Sector 9 Chowk',
    'Dakshin Marg & Transport Chowk',
    'Himalaya Marg & Piccadily Sq',
    'Vidhya Path & Sector 15',
    'Purv Marg & Housing Board',
    'Sector 43 ISBT Road',
    'Tribune Chowk',
    'Rock Garden Road',
    'Elante Mall Road',
    'Sector 32-33 Connector'
  ],
};

const SeverityConfig = {
  critical: { cssVar: 'var(--color-danger)',  icon: <AlertTriangle className="w-4 h-4" style={{ color: 'var(--color-danger)' }} /> },
  moderate: { cssVar: 'var(--color-warning)', icon: <AlertCircle  className="w-4 h-4" style={{ color: 'var(--color-warning)' }} /> },
  low:      { cssVar: 'var(--color-success)', icon: <ShieldCheck   className="w-4 h-4" style={{ color: 'var(--color-success)' }} /> },
};

const formatTime = (iso: string) => {
  try { return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
};

// ─── Street Search Dropdown ──────────────────────────
const StreetSearch: React.FC<{
  city: 'nyc' | 'chandigarh';
  value: string;
  onChange: (v: string) => void;
}> = ({ city, value, onChange }) => {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const streets = CITY_STREETS[city] || [];
  const filtered = query.length > 0
    ? streets.filter(s => s.toLowerCase().includes(query.toLowerCase())).slice(0, 6)
    : streets.slice(0, 6);

  useEffect(() => { setQuery(value); }, [value]);
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none" style={{ color: 'var(--color-text-secondary)' }} />
        <input
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); onChange(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={city === 'nyc' ? 'e.g. Broadway & W 34th St' : 'e.g. Sector 17 Chowk'}
          className="w-full bg-transparent text-sm pl-9 pr-9 py-3 outline-none font-medium"
          style={{
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
          }}
        />
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none" style={{ color: 'var(--color-text-secondary)' }} />
      </div>
      {open && filtered.length > 0 && (
        <div
          className="absolute z-50 w-full mt-0.5 overflow-hidden"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          {filtered.map(street => (
            <button
              key={street}
              onMouseDown={() => { onChange(street); setQuery(street); setOpen(false); }}
              className="w-full text-left px-3 py-2.5 text-sm font-medium flex items-center gap-2 transition-colors"
              style={{ color: 'var(--color-text)' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-accent-dim)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <MapPin className="w-3 h-3 shrink-0" style={{ color: 'var(--color-text-secondary)' }} />
              {street}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Main Sidebar ────────────────────────────────────
const Sidebar: React.FC = () => {
  const { city } = useFeedStore();
  const { setIncidents } = useIncidentStore();
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [location, setLocation] = useState('');
  const [title, setTitle] = useState('Traffic Collision');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('moderate');
  const [needsAmbulance, setNeedsAmbulance] = useState(false);
  const [photoBase64, setPhotoBase64] = useState<string | null>(null);
  
  const [locError, setLocError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  // Live incidents from backend
  const [liveIncidents, setLiveIncidents] = useState<any[]>([]);

  const fetchLiveIncidents = async (targetCity: 'nyc' | 'chandigarh' = city) => {
    try {
      const data = await api.getIncidents(targetCity, 'active');
      if (Array.isArray(data)) {
        // Guard against race conditions when city is switched while requests are in-flight.
        if (useFeedStore.getState().city !== targetCity) return;
        const scoped = data
          .filter((inc: any) => inferIncidentCity(inc) === targetCity)
          .map((inc: any) => ({ ...inc, city: inferIncidentCity(inc) ?? targetCity }));
        setLiveIncidents(scoped);
        setIncidents(scoped);
      }
    } catch { /* silent */ }
  };

  useEffect(() => {
    const cityAtStart = city;
    fetchLiveIncidents(cityAtStart);
    const interval = setInterval(() => fetchLiveIncidents(cityAtStart), 10000);
    return () => clearInterval(interval);
  }, [city]);

  const cityLiveIncidents = liveIncidents.filter((inc: any) => inferIncidentCity(inc) === city);

  const handleSubmit = async () => {
    if (!photoBase64) { setLocError('A photo of the incident is compulsory.'); return; }
    if (!location.trim()) { setLocError('Location is required'); return; }
    setIsSubmitting(true);
    setLocError('');
    try {
      const res = await api.reportIncident({ 
        title, city, location_str: location, description,
        severity, needs_ambulance: needsAmbulance, media_url: photoBase64
      });
      if (res?.incident_id) {
        setSubmitSuccess(true);
        setTimeout(() => {
          setIsReportOpen(false);
          setSubmitSuccess(false);
          setLocation('');
          setDescription('');
          setPhotoBase64(null);
          setNeedsAmbulance(false);
          setSeverity('moderate');
          fetchLiveIncidents(city); // refresh list
        }, 1800);
      } else {
        setLocError(res?.detail || 'Submission failed – try again');
      }
    } catch {
      setLocError('Network error – is the backend running?');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGetLocation = () => {
    setLocError('');
    if (!navigator.geolocation) { setLocError('Geolocation not supported'); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => setLocation(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`),
      () => setLocError('Location access denied')
    );
  };

  return (
    <div className="flex flex-col h-full w-full">

      {/* REPORT BUTTON */}
      <div className="px-4 mb-4">
        <button
          onClick={() => setIsReportOpen(true)}
          className="w-full flex items-center justify-center gap-2 py-3 text-[11px] font-bold uppercase tracking-[0.14em] transition-colors"
          style={{
            background: 'var(--color-accent)',
            color: '#fff',
            border: '1px solid var(--color-accent)',
          }}
        >
          <AlertOctagon className="w-4 h-4" />
          <span>Report a Problem</span>
        </button>
      </div>

      {/* CITY TAG */}
      <div className="px-4 mb-3 flex items-center gap-2">
        <span
          className="text-[9px] font-mono uppercase tracking-[0.14em]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {city === 'nyc' ? 'New York' : 'Chandigarh'} · Active Incidents
        </span>
        <span
          className="ml-auto text-[9px] font-mono font-bold"
          style={{ color: 'var(--color-accent)' }}
        >
          {cityLiveIncidents.length} active
        </span>
      </div>

      {/* LIVE INCIDENTS */}
      <div className="px-4 space-y-2">
        {cityLiveIncidents.length === 0 ? (
          <div
            className="p-4 flex items-center gap-3"
            style={{
              background: 'var(--color-success-dim)',
              border: '1px solid var(--color-success)',
              borderLeft: '3px solid var(--color-success)',
            }}
          >
            <CheckCircle2 className="w-4 h-4 shrink-0" style={{ color: 'var(--color-success)' }} />
            <div>
              <p className="text-sm font-bold" style={{ color: 'var(--color-success)' }}>All Clear</p>
              <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                No active incidents in {city === 'nyc' ? 'New York' : 'Chandigarh'}
              </p>
            </div>
          </div>
        ) : (
          cityLiveIncidents.map(inc => {
            const sev = inc.severity as keyof typeof SeverityConfig;
            const conf = SeverityConfig[sev] ?? SeverityConfig.moderate;
            return (
              <div
                key={inc._id}
                className="p-4 transition-colors"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderLeft: `3px solid ${conf.cssVar}`,
                }}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {conf.icon}
                    <h3 className="font-bold text-sm" style={{ color: 'var(--color-text)' }}>
                      {inc.title || inc.on_street}
                    </h3>
                  </div>
                  {inc.severity === 'critical' && (
                    <div
                      className="h-2 w-2 shrink-0 mt-1"
                      style={{ background: 'var(--color-danger)' }}
                    />
                  )}
                </div>
                <div
                  className="text-[9px] font-mono uppercase tracking-wider mb-2"
                  style={{ color: conf.cssVar }}
                >
                  {inc.status?.toUpperCase()} · {sev.toUpperCase()}
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                    <MapPin className="w-3 h-3" />
                    <span>{inc.on_street || '—'}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                    <Clock className="w-3 h-3" />
                    <span>{formatTime(inc.detected_at)}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* REPORT MODAL */}
      {isReportOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-end justify-center pb-[76px]"
          style={{ background: 'rgba(0,0,0,0.6)' }}
        >
          <div
            className="w-full max-w-sm relative overflow-hidden max-h-[calc(90vh-76px)] overflow-y-auto"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderTop: '2px solid var(--color-accent)',
            }}
          >
            {/* Modal header */}
            <div
              className="sticky top-0 px-5 py-4 flex items-center justify-between z-10"
              style={{
                background: 'var(--color-surface)',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              <h2
                className="text-sm font-black uppercase tracking-[0.16em]"
                style={{ color: 'var(--color-text)' }}
              >
                Report a Problem
              </h2>
              <button
                onClick={() => { setIsReportOpen(false); setLocError(''); setSubmitSuccess(false); }}
                className="flex items-center justify-center h-7 w-7 transition-colors"
                style={{
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                  background: 'var(--color-bg)',
                }}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* City indicator */}
              <div
                className="px-3 py-2 text-xs font-bold flex items-center gap-2"
                style={{
                  background: 'var(--color-accent-dim)',
                  border: '1px solid var(--color-accent)',
                  color: 'var(--color-accent)',
                }}
              >
                <span className="font-mono uppercase tracking-wider text-[10px]">
                  Reporting for {city === 'nyc' ? 'New York City' : 'Chandigarh'}
                </span>
              </div>

              {submitSuccess ? (
                <div className="flex flex-col items-center gap-3 py-8">
                  <CheckCircle2 className="w-10 h-10" style={{ color: 'var(--color-success)' }} />
                  <p className="font-bold text-lg" style={{ color: 'var(--color-text)' }}>Report Submitted!</p>
                  <p className="text-sm text-center" style={{ color: 'var(--color-text-secondary)' }}>
                    An operator has been notified and will respond shortly.
                  </p>
                </div>
              ) : (
                <>
                  {/* Issue Type */}
                  <div>
                    <label
                      className="block text-[9px] font-mono uppercase tracking-wider mb-1.5"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Issue Type
                    </label>
                    <select
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                      className="w-full text-sm px-3 py-3 outline-none appearance-none font-medium"
                      style={{
                        background: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text)',
                      }}
                    >
                      <option>Traffic Collision</option>
                      <option>Road Hazard / Debris</option>
                      <option>Infrastructure Damage</option>
                      <option>Medical Emergency</option>
                      <option>Flooding / Waterlogging</option>
                      <option>Signal Malfunction</option>
                    </select>
                  </div>

                  {/* Location */}
                  <div>
                    <label
                      className="block text-[9px] font-mono uppercase tracking-wider mb-1.5"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Location / Street
                    </label>
                    <StreetSearch city={city as 'nyc' | 'chandigarh'} value={location} onChange={setLocation} />
                    <button
                      onClick={handleGetLocation}
                      className="mt-2 flex items-center gap-1.5 text-[11px] font-medium transition-colors"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      <Navigation className="w-3 h-3" />
                      Use GPS coordinates
                    </button>
                    {locError && (
                      <p className="text-[11px] mt-1.5 font-bold" style={{ color: 'var(--color-danger)' }}>
                        {locError}
                      </p>
                    )}
                  </div>

                  {/* Severity */}
                  <div>
                    <label
                      className="block text-[9px] font-mono uppercase tracking-wider mb-1.5"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Severity
                    </label>
                    <select
                      value={severity}
                      onChange={e => setSeverity(e.target.value)}
                      className="w-full text-sm px-3 py-3 outline-none appearance-none font-medium"
                      style={{
                        background: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text)',
                      }}
                    >
                      <option value="minor">Minor</option>
                      <option value="moderate">Moderate</option>
                      <option value="major">Major</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>

                  {/* Description */}
                  <div>
                    <label
                      className="block text-[9px] font-mono uppercase tracking-wider mb-1.5"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Description
                    </label>
                    <textarea
                      value={description}
                      onChange={e => setDescription(e.target.value)}
                      rows={2}
                      placeholder="Describe what happened..."
                      className="w-full text-sm px-3 py-3 outline-none resize-none font-medium"
                      style={{
                        background: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text)',
                      }}
                    />
                  </div>

                  {/* Photo */}
                  <div>
                    <label
                      className="block text-[9px] font-mono uppercase tracking-wider mb-1.5"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Compulsory Photo
                    </label>
                    <label
                      className="cursor-pointer flex items-center justify-center gap-2 py-4"
                      style={{
                        border: `1px dashed ${photoBase64 ? 'var(--color-success)' : 'var(--color-border-strong)'}`,
                        background: photoBase64 ? 'var(--color-success-dim)' : 'var(--color-bg)',
                        color: photoBase64 ? 'var(--color-success)' : 'var(--color-text-secondary)',
                      }}
                    >
                      {photoBase64 ? (
                        <><ImageIcon className="w-4 h-4" /><span className="text-sm font-bold">Attached</span></>
                      ) : (
                        <><Camera className="w-4 h-4" /><span className="text-sm font-medium">Tap to attach photo</span></>
                      )}
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            const reader = new FileReader();
                            reader.onload = (ev) => setPhotoBase64(ev.target?.result as string);
                            reader.readAsDataURL(file);
                          }
                        }}
                      />
                    </label>
                  </div>

                  {/* Ambulance toggle */}
                  <div
                    className="flex items-center gap-3 px-3 py-3"
                    style={{
                      background: 'var(--color-danger-dim)',
                      border: '1px solid var(--color-danger)',
                    }}
                  >
                    <input
                      type="checkbox"
                      id="ambulance"
                      checked={needsAmbulance}
                      onChange={(e) => setNeedsAmbulance(e.target.checked)}
                      className="w-4 h-4"
                      style={{ accentColor: 'var(--color-danger)' }}
                    />
                    <label
                      htmlFor="ambulance"
                      className="font-bold text-sm cursor-pointer"
                      style={{ color: 'var(--color-danger)' }}
                    >
                      Dispatch Ambulance Automatically
                    </label>
                  </div>

                  {/* Submit */}
                  <button
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="w-full py-3.5 text-[11px] font-bold uppercase tracking-[0.14em] flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                    style={{
                      background: 'var(--color-accent)',
                      color: '#fff',
                      border: '1px solid var(--color-accent)',
                    }}
                  >
                    {isSubmitting ? (
                      <><span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white animate-spin" />Submitting...</>
                    ) : (
                      <><AlertOctagon className="w-3.5 h-3.5" />Submit Emergency Report</>
                    )}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
