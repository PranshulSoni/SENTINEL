import React, { useState, useEffect, useRef } from 'react';
import {
  MapPin, Clock, AlertTriangle, AlertCircle, ShieldCheck, X, AlertOctagon, Navigation,
  CheckCircle2, Search, ChevronDown, Camera, Image as ImageIcon
} from 'lucide-react';
import { api } from '../../services/api';
import { useFeedStore, useIncidentStore } from '../../store';

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

  const fetchLiveIncidents = async () => {
    try {
      const data = await api.getIncidents(city, 'active');
      if (Array.isArray(data)) {
        setLiveIncidents(data);
        setIncidents(data);
      }
    } catch { /* silent */ }
  };

  useEffect(() => {
    fetchLiveIncidents();
    const interval = setInterval(fetchLiveIncidents, 10000);
    return () => clearInterval(interval);
  }, [city]);

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
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* REPORT MODAL */}
      {isReportOpen && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center pb-[76px] bg-black/30 backdrop-blur-sm">
          <div className="bg-white w-full max-w-sm rounded-t-[2rem] shadow-2xl relative overflow-hidden animate-in slide-in-from-bottom duration-300 max-h-[calc(90vh-76px)] overflow-y-auto">
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
                    <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Severity</label>
                    <select
                      value={severity}
                      onChange={e => setSeverity(e.target.value)}
                      className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl px-4 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all appearance-none font-semibold"
                    >
                      <option value="minor">Minor</option>
                      <option value="moderate">Moderate</option>
                      <option value="major">Major</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Description</label>
                    <textarea
                      value={description}
                      onChange={e => setDescription(e.target.value)}
                      rows={2}
                      placeholder="Describe what happened..."
                      className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl px-4 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all resize-none font-semibold placeholder:text-gray-400 placeholder:font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">
                      Compulsory Photo Attachment
                    </label>
                    <div className="flex items-center gap-3">
                      <label className="flex-1 cursor-pointer flex flex-col items-center justify-center p-3 border-2 border-dashed border-gray-300 rounded-xl hover:border-[#FF5A5F] hover:bg-[#FF5A5F]/5 transition-all text-gray-500">
                        {photoBase64 ? (
                          <div className="flex items-center gap-2 text-green-500 font-bold text-sm">
                            <ImageIcon className="w-5 h-5" /> Attached
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 font-bold text-sm">
                            <Camera className="w-5 h-5" /> Click or Tap to attach
                          </div>
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
                  </div>

                  <div className="flex items-center gap-3 bg-red-50 p-3 rounded-xl border border-red-100 mt-2">
                    <input
                      type="checkbox"
                      id="ambulance"
                      checked={needsAmbulance}
                      onChange={(e) => setNeedsAmbulance(e.target.checked)}
                      className="w-5 h-5 rounded border-red-300 text-[#FF5A5F] focus:ring-[#FF5A5F]"
                    />
                    <label htmlFor="ambulance" className="font-bold text-[#FF5A5F] text-sm cursor-pointer">
                      Dispatch Ambulance Automatically
                    </label>
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
