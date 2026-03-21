import React, { useState } from 'react';
import {
  MapPin, Clock, AlertTriangle, AlertCircle, ShieldCheck, X, AlertOctagon, Navigation
} from 'lucide-react';

/* ═══ MOCK DATA ═══ */
const INCIDENTS = [
  {
    id: 'INC-4827',
    title: 'Multi-Vehicle Collision',
    street: 'Broadway & W 34th St',
    time: '14:23',
    etaImpact: '+25 min',
    severity: 'critical',
  },
  {
    id: 'INC-4828',
    title: 'Construction Delay',
    street: '7th Ave & W 42nd St',
    time: '13:10',
    etaImpact: '+10 min',
    severity: 'moderate',
  },
  {
    id: 'INC-4829',
    title: 'Debris on Road',
    street: '10th Ave Bypass',
    time: '14:05',
    etaImpact: '+2 min',
    severity: 'low',
  }
];

const SeverityConfig = {
  critical: { color: 'bg-[#FF5A5F]', text: 'text-[#FF5A5F]', border: 'border-l-[#FF5A5F]', icon: <AlertTriangle className="w-5 h-5 text-[#FF5A5F]" /> },
  moderate: { color: 'bg-[#eab308]', text: 'text-[#eab308]', border: 'border-l-[#eab308]', icon: <AlertCircle className="w-5 h-5 text-[#eab308]" /> },
  low: { color: 'bg-[#A3B18A]', text: 'text-[#A3B18A]', border: 'border-l-[#A3B18A]', icon: <ShieldCheck className="w-5 h-5 text-[#A3B18A]" /> },
};

const Sidebar: React.FC = () => {
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [location, setLocation] = useState('');
  const [locError, setLocError] = useState('');

  const handleGetLocation = () => {
    setLocError('');
    if (!navigator.geolocation) {
      setLocError('Geolocation not supported');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      },
      () => {
        setLocError('Location access denied');
      }
    );
  };

  return (
    <div className="flex flex-col h-full w-full">
      
      {/* FULL WIDTH REPORT BLOCK */}
      <div className="px-6 mb-8">
        <button 
          onClick={() => setIsReportOpen(true)}
          className="w-full bg-gradient-to-r from-[#FF5A5F] to-[#ff878a] rounded-2xl p-4 text-white shadow-lg shadow-[#FF5A5F]/20 flex items-center justify-center gap-3 hover:scale-[1.02] active:scale-95 transition-all"
        >
          <AlertOctagon className="w-5 h-5" />
          <span className="font-bold text-[15px] tracking-wide">Report a Problem</span>
        </button>
      </div>

      <div className="px-6 space-y-4">
        {INCIDENTS.map(inc => {
          const conf = SeverityConfig[inc.severity as keyof typeof SeverityConfig];
          return (
            <div 
              key={inc.id} 
              className={`bg-white rounded-[1.25rem] p-5 shadow-sm border border-[#EAEAEA] border-l-4 hover:shadow-md transition-all cursor-pointer relative overflow-hidden`}
              style={{ borderLeftColor: conf.color.replace('bg-[', '').replace(']', '') }}
            >
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-xl bg-gray-50 border border-gray-100`}>
                    {conf.icon}
                  </div>
                  <div>
                    <h3 className="font-extrabold text-[#1A1A1A] text-sm">{inc.title}</h3>
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mt-0.5">{inc.id}</p>
                  </div>
                </div>
                {inc.severity === 'critical' && (
                  <span className="flex h-2.5 w-2.5 relative mt-2 mr-1">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FF5A5F] opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#FF5A5F]"></span>
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2.5 text-xs text-gray-600">
                  <MapPin className="w-4 h-4 text-gray-400" />
                  <span className="font-medium">{inc.street}</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5 text-xs text-gray-600">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span className="font-medium">{inc.time}</span>
                  </div>
                  <div className={`text-xs font-bold px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-100`}>
                    <span className={conf.text}>{inc.etaImpact}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* REPORT MODAL POPUP */}
      {isReportOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/30 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white w-full max-w-sm rounded-[2rem] shadow-2xl relative overflow-hidden animate-in zoom-in-95 duration-200">
            <button 
              onClick={() => setIsReportOpen(false)}
              className="absolute top-5 right-5 p-2 bg-gray-50 text-gray-400 rounded-full hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="p-6 pt-8">
              <h2 className="text-xl font-extrabold text-[#1A1A1A] mb-6">Report a Problem</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Report Issue Type</label>
                  <select className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl px-4 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all appearance-none font-semibold">
                    <option>Traffic Collision</option>
                    <option>Road Hazard / Debris</option>
                    <option>Infrastructure Damage</option>
                    <option>Medical Emergency</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Location</label>
                  <div className="relative">
                    <input 
                      type="text" 
                      value={location}
                      onChange={e => setLocation(e.target.value)}
                      placeholder="e.g. Broadway & W 34th St" 
                      className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl pl-4 pr-12 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all font-semibold placeholder:text-gray-400 placeholder:font-medium" 
                    />
                    <button 
                      onClick={handleGetLocation}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-gray-400 hover:text-[#FF5A5F] transition-colors"
                      title="Use Current Location"
                    >
                      <Navigation className="w-4 h-4" />
                    </button>
                  </div>
                  {locError && <p className="text-[#FF5A5F] text-[10px] mt-1.5 font-bold">{locError}</p>}
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Describe Issue</label>
                  <textarea rows={3} placeholder="Provide details..." className="w-full bg-gray-50 border border-gray-200 text-[#1A1A1A] text-sm rounded-xl px-4 py-3.5 outline-none focus:border-[#FF5A5F] focus:ring-1 focus:ring-[#FF5A5F] transition-all resize-none font-semibold placeholder:text-gray-400 placeholder:font-medium"></textarea>
                </div>
                
                <button 
                  onClick={() => setIsReportOpen(false)}
                  className="w-full mt-6 bg-[#1A1A1A] text-white rounded-xl py-4 font-bold tracking-wide shadow-lg hover:bg-black transition-colors"
                >
                  Submit Report
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default Sidebar;
