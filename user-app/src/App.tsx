import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  MapPin, 
  ArrowRight,
  Plus,
  Crosshair,
  AlertTriangle,
  Check,
  X
} from 'lucide-react';

/* ═══ MOCK DATA ═══ */
const LIVE_INCIDENTS = {
  nyc: [
    { id: 'INC-4827', title: 'Multi-Vehicle Collision', location: 'Broadway & W 34th St', time: '14:23', delay: '+25m', severity: 'CRITICAL' },
    { id: 'INC-4828', title: 'Stalled Vehicle', location: 'FDR Drive SB', time: '14:40', delay: '+10m', severity: 'MODERATE' }
  ],
  chandigarh: [
    { id: 'CHD-9921', title: 'Traffic Signal Failure', location: 'Tribune Chowk', time: '15:10', delay: '+18m', severity: 'CRITICAL' },
    { id: 'CHD-9922', title: 'Road Construction', location: 'Sector 17 Bus Stand', time: '10:00', delay: '+5m', severity: 'MINOR' }
  ]
};

const App: React.FC = () => {
  const [city, setCity] = useState<'nyc' | 'chandigarh'>('nyc');
  const [isReporting, setIsReporting] = useState(false);
  const [formData, setFormData] = useState({ type: 'Accident', location: '', description: '' });
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'submitting' | 'success'>('idle');

  const [loaded, setLoaded] = useState(false);
  useEffect(() => { setLoaded(true); }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitStatus('submitting');
    setTimeout(() => {
      setSubmitStatus('success');
      setTimeout(() => {
        setIsReporting(false);
        setSubmitStatus('idle');
        setFormData({ type: 'Accident', location: '', description: '' });
      }, 2000);
    }, 1500);
  };

  const currentIncidents = LIVE_INCIDENTS[city];

  return (
    <div className="min-h-[100dvh] text-black font-sans flex flex-col selection:bg-blue-600 selection:text-white pb-32 overflow-x-hidden pt-4 px-4 sm:pt-8 relative">
      
      {/* Container Background explicitly made translucent wrapper (bg-white/60) so the underlying map layer is super visible */}
      <main className="flex-1 w-full max-w-xl mx-auto flex flex-col relative z-10 bg-white/60 backdrop-blur-[4px] border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-shadow">
        
        {/* ═══ HEADER ═══ */}
        <header className="sticky top-0 z-40 border-b-2 border-black w-full bg-white/95">
          <div className="flex flex-col">
            <div className="flex items-center justify-between p-4 bg-black text-white">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-white" />
                <h1 className="text-sm font-black uppercase tracking-[0.2em] text-white">SENTINEL</h1>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-green-400 animate-pulse" />
                <span className="text-[9px] font-mono tracking-widest uppercase text-green-300">Live Grid</span>
              </div>
            </div>
            
            <div className="flex text-[10px] font-mono uppercase font-bold w-full bg-white">
              <button 
                onClick={() => setCity('nyc')}
                className={`flex-1 py-3 transition-colors text-center border-r-2 border-black ${city === 'nyc' ? 'bg-blue-600 text-white' : 'text-zinc-500 hover:text-black hover:bg-zinc-100'}`}
              >
                NEW YORK
              </button>
              <button 
                onClick={() => setCity('chandigarh')}
                className={`flex-1 py-3 transition-colors text-center ${city === 'chandigarh' ? 'bg-blue-600 text-white' : 'text-zinc-500 hover:text-black hover:bg-zinc-100'}`}
              >
                CHANDIGARH
              </button>
            </div>
          </div>
        </header>

        {/* ═══ MAP HERO (Overlaying Background Map) ═══ */}
        <section className={`flex flex-col p-6 transition-all duration-1000 ${loaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
          <div className="mb-6 flex flex-col uppercase tracking-tighter">
            {/* Small to properly-scaled Big */}
            <span className="text-3xl font-black text-blue-700 leading-none mb-1">
              REPORT.
            </span>
            <span className="text-4xl font-black text-blue-500 leading-none mb-1">
              RESOLVE.
            </span>
            {/* Decreased font-size to 6xl (from 5.5rem prior) for a perfectly stepped look */}
            <span className="text-6xl font-black text-blue-300 leading-[0.8]">
              ROUTINE.
            </span>
          </div>
          
          <p className="text-[13px] font-mono text-zinc-800 leading-relaxed mb-8 max-w-[280px] tracking-wider relative font-semibold bg-white/50 p-2 border-l-4 border-blue-600">
            Reporting hazards powers real-time routing for your city.
          </p>
          
          <button 
            onClick={() => setIsReporting(true)}
            className="w-full py-5 bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-black uppercase tracking-[0.2em] flex justify-between items-center px-6 transition-colors group relative border-2 border-black shadow-[4px_4px_0px_0px_transparent] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            <span className="flex items-center gap-3">
              <Crosshair className="w-5 h-5 group-active:scale-90 transition-transform" /> 
              Drop Pin
            </span>
            <div className="w-8 h-8 flex items-center justify-center bg-black transition-transform group-active:-rotate-90">
              <Plus className="w-5 h-5 text-red-500" />
            </div>
          </button>
        </section>

        {/* ═══ LIVE HAZARDS FEED ═══ */}
        <section className={`flex flex-col flex-1 transition-all duration-1000 delay-200 mt-4 ${loaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
          <div className="border-y-2 border-black bg-white/90 px-5 py-3 flex items-center justify-between">
            <h3 className="text-[10px] font-mono font-bold text-black uppercase tracking-widest flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-blue-600" /> Live Vectors
            </h3>
            <span className="text-[10px] font-mono text-zinc-600 font-bold uppercase tracking-widest px-2 py-0.5 border border-zinc-300">
              {currentIncidents.length} Found
            </span>
          </div>
          
          <div className="flex flex-col bg-white/90 overflow-hidden pb-4">
            {currentIncidents.map((inc) => (
              <div key={inc.id} className="flex flex-col p-5 border-b-2 border-black active:bg-zinc-50 hover:bg-zinc-50 transition-colors group">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono font-black text-white bg-black px-1.5 py-0.5 uppercase tracking-widest">
                      {inc.id}
                    </span>
                    <span className={`text-[9px] font-mono font-bold uppercase tracking-widest px-1.5 py-0.5 border-2 ${
                      inc.severity === 'CRITICAL' ? 'border-red-600 text-red-600' : 'border-zinc-800 text-black bg-zinc-100'
                    }`}>
                      {inc.severity}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-zinc-500 font-bold">{inc.time}</span>
                </div>
                
                <h4 className="font-black text-xl uppercase tracking-tight text-black mb-4">{inc.title}</h4>
                
                <div className="flex items-end justify-between border-t border-zinc-200 pt-3">
                  <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-zinc-500">
                    <MapPin className="w-4 h-4 text-black" />
                    <span className="uppercase text-black">{inc.location}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                    <span className="text-sm font-black text-red-600 uppercase">{inc.delay}</span>
                  </div>
                </div>
              </div>
            ))}
            
            {currentIncidents.length === 0 && (
              <div className="p-8 text-center text-[10px] font-mono font-bold uppercase tracking-widest text-zinc-400 bg-white/80 h-32 flex items-center justify-center">
                Grid anomalies not detected.
              </div>
            )}
          </div>
        </section>

      </main>

      {/* ═══ FULL SCREEN MOBILE MODAL ═══ */}
      {isReporting && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-zinc-900/60 backdrop-blur-sm p-4 animate-in slide-in-from-bottom-6 duration-300">
          <div className="w-full max-w-xl mx-auto flex flex-col bg-white border-2 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] max-h-[95vh] overflow-hidden">
            
            <div className="flex items-center justify-between p-4 bg-black border-b-2 border-black h-16 shrink-0 z-20">
              <h2 className="text-[10px] font-mono font-bold text-white uppercase tracking-widest flex items-center gap-2">
                <span className="w-2 h-2 bg-blue-400" /> Transmit Anomaly
              </h2>
              {submitStatus === 'idle' && (
                <button onClick={() => setIsReporting(false)} className="p-2 text-zinc-400 hover:text-white transition-colors">
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto w-full flex flex-col p-6">
              {submitStatus === 'success' ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center py-12">
                  <div className="w-20 h-20 border-4 border-black flex items-center justify-center mb-6 bg-green-500 text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                    <Check className="w-10 h-10" />
                  </div>
                  <h3 className="text-2xl font-black text-black uppercase mb-4 tracking-tight">Pin Secured.</h3>
                  <p className="text-zinc-600 font-mono text-xs max-w-[250px] uppercase font-bold leading-relaxed tracking-wider">
                    Coordinates transmitted. SENTINEL command is validating vector anomalies.
                  </p>
                  <button 
                    onClick={() => setIsReporting(false)}
                    className="mt-12 w-full py-4 border-2 border-black text-black font-black uppercase tracking-widest hover:bg-black hover:text-white transition-colors"
                  >
                    Close Terminal
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="flex-1 flex flex-col">
                  <div className="space-y-6 flex-1">
                    <div>
                      <label className="block text-[10px] font-mono font-bold uppercase text-blue-700 mb-2 tracking-widest">Hazard Matrix</label>
                      <div className="relative">
                        <select 
                          required
                          value={formData.type}
                          onChange={(e) => setFormData({...formData, type: e.target.value})}
                          className="w-full border-2 border-black px-4 py-4 bg-white focus:bg-zinc-50 transition-colors appearance-none font-black text-xs uppercase tracking-wider text-black outline-none"
                          disabled={submitStatus === 'submitting'}
                        >
                          <option>Accident / Collision</option>
                          <option>Road Hazard / Debris</option>
                          <option>Stopped / Disabled</option>
                          <option>Traffic Light Outage</option>
                          <option>Severe Congestion</option>
                        </select>
                        <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none border-l-2 border-black bg-black text-white">
                          <ArrowRight className="w-4 h-4 rotate-90" />
                        </div>
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] font-mono font-bold uppercase text-blue-700 mb-2 tracking-widest">Vector Location</label>
                      <input 
                        type="text" 
                        required
                        placeholder="e.g. Broadway & W 34th St"
                        value={formData.location}
                        onChange={(e) => setFormData({...formData, location: e.target.value})}
                        className="w-full border-2 border-black px-4 py-4 bg-white focus:bg-zinc-50 transition-colors placeholder:text-zinc-400 font-black text-xs uppercase tracking-wider text-black outline-none"
                        disabled={submitStatus === 'submitting'}
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] font-mono font-bold uppercase text-blue-700 mb-2 tracking-widest">Telemetry (Optional)</label>
                      <textarea 
                        placeholder="Lanes blocked, variables..."
                        rows={4}
                        value={formData.description}
                        onChange={(e) => setFormData({...formData, description: e.target.value})}
                        className="w-full border-2 border-black px-4 py-4 bg-white focus:bg-zinc-50 transition-colors placeholder:text-zinc-400 resize-none font-black text-xs uppercase tracking-wider text-black outline-none"
                        disabled={submitStatus === 'submitting'}
                      />
                    </div>
                  </div>
                  
                  <div className="mt-8">
                    <button 
                      type="submit" 
                      disabled={submitStatus === 'submitting'}
                      className="w-full py-5 bg-black text-white font-black uppercase tracking-[0.2em] disabled:opacity-50 transition-colors flex justify-between items-center px-6 relative overflow-hidden group hover:bg-zinc-800 focus:outline-none focus:ring-4 ring-black/20"
                    >
                      {submitStatus === 'submitting' ? (
                        <span className="animate-pulse w-full text-center">Transmitting...</span>
                      ) : (
                        <>
                          <span>Submit Data</span>
                          <ArrowRight className="w-5 h-5 group-active:translate-x-2 transition-transform" />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sticky Bottom Report Button */}
      {!isReporting && (
        <div className="fixed bottom-0 left-0 right-0 p-4 pb-6 bg-gradient-to-t from-white/90 via-white/70 to-transparent z-30 flex justify-center pointer-events-none">
          <button 
            onClick={() => setIsReporting(true)}
            className="w-full max-w-xl mx-auto py-5 bg-black hover:bg-zinc-800 text-white font-black uppercase tracking-[0.2em] shadow-[4px_4px_0px_0px_rgba(0,0,0,0.5)] border-2 border-black pointer-events-auto transition-transform active:translate-y-1 active:shadow-none"
          >
            Pin Issue
          </button>
        </div>
      )}

    </div>
  );
};

export default App;
