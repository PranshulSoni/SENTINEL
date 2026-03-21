import React, { useState, useEffect, useRef } from 'react';
import {
  MapPin, Clock, AlertTriangle, AlertCircle, ShieldCheck, X, AlertOctagon, Navigation,
  CheckCircle2, Search, ChevronDown
} from 'lucide-react';
import { api } from '../../services/api';
import { useFeedStore } from '../../store';

// ─── City Streets ─────────────────────────────────────
const CITY_STREETS: Record<string, string[]> = {
  nyc: [
    'Broadway & W 34th St', '7th Ave & W 42nd St', '5th Ave & E 59th St',
    '10th Ave & W 23rd St', 'Madison Ave & E 45th St', 'Lexington Ave & E 51st St',
    'Park Ave & E 40th St', '2nd Ave & E 34th St', '1st Ave & E 14th St',
    'Canal St & Broadway', 'Houston St & Varick St', 'W 57th St & 8th Ave',
    'Amsterdam Ave & W 86th St', 'Columbus Ave & W 72nd St', 'Riverside Dr & W 79th St',
    'FDR Drive & E 42nd St', 'West Side Hwy & Chambers St', 'Flatbush Ave & Atlantic Ave',
  ],
  chandigarh: [
    'Sector 17 Chowk', 'Sector 22 Market Road', 'Madhya Marg & Sector 9',
    'Jan Marg & Sector 17', 'Dakshin Marg & Sector 38', 'Uttar Marg & Sector 20',
    'Himalaya Marg & Sector 52', 'Purv Marg & Sector 44', 'Tribune Chowk',
    'PGI Roundabout', 'ISBT Sector 43', 'Airport Road Sector 9',
    'Sukhna Lake Road', 'Rock Garden Road', 'Sector 35 Chowk',
    'Sector 9 D Road', 'Hallomajra Crossing', 'Kharar Road Junction',
  ],
};

const SeverityConfig = {
  critical: { colorHex: '#FF5A5F', text: 'text-[#FF5A5F]', icon: <AlertTriangle className="w-5 h-5 text-[#FF5A5F]" /> },
  moderate: { colorHex: '#eab308', text: 'text-[#eab308]', icon: <AlertCircle className="w-5 h-5 text-[#eab308]" /> },
  low: { colorHex: '#A3B18A', text: 'text-[#A3B18A]', icon: <ShieldCheck className="w-5 h-5 text-[#A3B18A]" /> },
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
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); onChange(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={city === 'nyc' ? 'e.g. Broadway & W 34th St' : 'e.g. Sector 17 Chowk'}
          className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl pl-10 pr-10 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all font-semibold placeholder:text-gray-400 placeholder:font-medium"
        />
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
      </div>
      {open && filtered.length > 0 && (
        <div className="absolute z-50 w-full bg-white border border-gray-200 rounded-xl shadow-xl mt-1 overflow-hidden">
          {filtered.map(street => (
            <button
              key={street}
              onMouseDown={() => { onChange(street); setQuery(street); setOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-sm text-[#1A1A1A] font-medium hover:bg-[#FF5A5F]/5 hover:text-[#FF5A5F] flex items-center gap-2 transition-colors"
            >
              <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
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
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [location, setLocation] = useState('');
  const [title, setTitle] = useState('Traffic Collision');
  const [description, setDescription] = useState('');
  const [locError, setLocError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  // Live incidents from backend
  const [liveIncidents, setLiveIncidents] = useState<any[]>([]);

  const fetchLiveIncidents = async () => {
    try {
      const data = await api.getIncidents(city, 'active');
      if (Array.isArray(data)) setLiveIncidents(data);
    } catch { /* silent */ }
  };

  useEffect(() => {
    fetchLiveIncidents();
    const interval = setInterval(fetchLiveIncidents, 10000);
    return () => clearInterval(interval);
  }, [city]);

  const handleSubmit = async () => {
    if (!location.trim()) { setLocError('Location is required'); return; }
    setIsSubmitting(true);
    setLocError('');
    try {
      const res = await api.reportIncident({ title, city, location_str: location, description });
      if (res?.incident_id) {
        setSubmitSuccess(true);
        setTimeout(() => {
          setIsReportOpen(false);
          setSubmitSuccess(false);
          setLocation('');
          setDescription('');
          fetchLiveIncidents(); // refresh list
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
      <div className="px-6 mb-6">
        <button
          onClick={() => setIsReportOpen(true)}
          className="w-full bg-gradient-to-r from-[#FF5A5F] to-[#ff878a] rounded-2xl p-4 text-white shadow-lg shadow-[#FF5A5F]/20 flex items-center justify-center gap-3 hover:scale-[1.02] active:scale-95 transition-all"
        >
          <AlertOctagon className="w-5 h-5" />
          <span className="font-bold text-[15px] tracking-wide">Report a Problem</span>
        </button>
      </div>

      {/* CITY TAG */}
      <div className="px-6 mb-3 flex items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
          {city === 'nyc' ? '🗽 New York – Active Incidents' : '🏙️ Chandigarh – Active Incidents'}
        </span>
        <span className="ml-auto text-[10px] font-bold text-[#FF5A5F]">{liveIncidents.length} active</span>
      </div>

      {/* LIVE INCIDENTS */}
      <div className="px-6 space-y-4">
        {liveIncidents.length === 0 ? (
          <div className="bg-green-50 border border-green-200 rounded-2xl p-5 flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
            <div>
              <p className="text-sm font-bold text-green-800">All Clear</p>
              <p className="text-xs text-green-600 mt-0.5">No active incidents in {city === 'nyc' ? 'New York' : 'Chandigarh'}</p>
            </div>
          </div>
        ) : (
          liveIncidents.map(inc => {
            const severity = inc.severity as keyof typeof SeverityConfig;
            const conf = SeverityConfig[severity] ?? SeverityConfig.moderate;
            return (
              <div
                key={inc._id}
                className="bg-white rounded-[1.25rem] p-5 shadow-sm border border-[#EAEAEA] hover:shadow-md transition-all relative overflow-hidden"
                style={{ borderLeftColor: conf.colorHex, borderLeftWidth: 4 }}
              >
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-gray-50 border border-gray-100">{conf.icon}</div>
                    <div>
                      <h3 className="font-extrabold text-[#1A1A1A] text-sm">{inc.title || inc.on_street}</h3>
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mt-0.5">
                        {inc.status?.toUpperCase()}
                      </p>
                    </div>
                  </div>
                  {inc.severity === 'critical' && (
                    <span className="flex h-2.5 w-2.5 relative mt-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FF5A5F] opacity-75" />
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#FF5A5F]" />
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs text-gray-600">
                    <MapPin className="w-3.5 h-3.5 text-gray-400" />
                    <span className="font-medium">{inc.on_street || '—'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <Clock className="w-3.5 h-3.5 text-gray-400" />
                      <span>{formatTime(inc.detected_at)}</span>
                    </div>
                    {inc.assigned_operator && (
                      <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
                        {inc.assigned_operator.split(' ')[0]}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* REPORT MODAL */}
      {isReportOpen && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/30 backdrop-blur-sm">
          <div className="bg-white w-full max-w-sm rounded-t-[2rem] shadow-2xl relative overflow-hidden animate-in slide-in-from-bottom duration-300 max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white pt-4 pb-2 px-6 flex items-center justify-between border-b border-gray-100 z-10">
              <h2 className="text-lg font-extrabold text-[#1A1A1A]">Report a Problem</h2>
              <button
                onClick={() => { setIsReportOpen(false); setLocError(''); setSubmitSuccess(false); }}
                className="p-2 bg-gray-50 text-gray-400 rounded-full hover:bg-gray-100 transition-colors"
              ><X className="w-4 h-4" /></button>
            </div>

            <div className="p-6 space-y-4">
              {/* City indicator */}
              <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-sm font-bold text-gray-500 flex items-center gap-2">
                <span>{city === 'nyc' ? '🗽' : '🏙️'}</span>
                <span>Reporting for {city === 'nyc' ? 'New York City' : 'Chandigarh'}</span>
              </div>

              {submitSuccess ? (
                <div className="flex flex-col items-center gap-3 py-8">
                  <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                    <CheckCircle2 className="w-8 h-8 text-green-500" />
                  </div>
                  <p className="font-bold text-[#1A1A1A] text-lg">Report Submitted!</p>
                  <p className="text-sm text-gray-500 text-center">An operator has been notified and will respond shortly.</p>
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Issue Type</label>
                    <select
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                      className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl px-4 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all appearance-none font-semibold"
                    >
                      <option>Traffic Collision</option>
                      <option>Road Hazard / Debris</option>
                      <option>Infrastructure Damage</option>
                      <option>Medical Emergency</option>
                      <option>Flooding / Waterlogging</option>
                      <option>Signal Malfunction</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Location / Street</label>
                    <StreetSearch city={city as 'nyc' | 'chandigarh'} value={location} onChange={setLocation} />
                    <button
                      onClick={handleGetLocation}
                      className="mt-2 flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#FF5A5F] transition-colors"
                    >
                      <Navigation className="w-3.5 h-3.5" />
                      Use my GPS coordinates instead
                    </button>
                    {locError && <p className="text-[#FF5A5F] text-[11px] mt-1.5 font-bold">{locError}</p>}
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Description</label>
                    <textarea
                      value={description}
                      onChange={e => setDescription(e.target.value)}
                      rows={3}
                      placeholder="Describe what happened..."
                      className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl px-4 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all resize-none font-semibold placeholder:text-gray-400 placeholder:font-medium"
                    />
                  </div>

                  <button
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="w-full bg-gradient-to-r from-[#FF5A5F] to-[#ff878a] text-white rounded-xl py-4 font-bold tracking-wide shadow-lg hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isSubmitting ? (
                      <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Submitting...</>
                    ) : (
                      <><AlertOctagon className="w-4 h-4" />Submit Emergency Report</>
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
