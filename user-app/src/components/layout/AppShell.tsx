import React, { useState, useEffect } from 'react';
import type { ReactElement } from 'react';
import { ShieldAlert, Map as MapIcon, Home, MessageCircle, Share2 } from 'lucide-react';
import { useFeedStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';

interface AppShellProps {
  leftPanel: React.ReactNode; 
  centerPanel: React.ReactNode; 
  rightPanel: React.ReactNode;
  socialPanel: React.ReactNode;
}

const CITY_BGS = {
  nyc: 'https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?q=80&w=1080&auto=format&fit=crop',
  chandigarh: 'https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?q=80&w=1080&auto=format&fit=crop'
};

const AppShell: React.FC<AppShellProps> = ({ leftPanel, centerPanel, rightPanel, socialPanel }) => {
  const { city: activeCity, switchCity: setActiveCity, fetchCityInfo } = useFeedStore();
  const setCongestionZones = useIncidentStore((s) => s.setCongestionZones);
  const [activeTab, setActiveTab] = useState<'home' | 'map' | 'copilot' | 'social'>('home');

  useEffect(() => {
    fetchCityInfo();
  }, [fetchCityInfo]);

  useEffect(() => {
    api
      .getCongestionZones(activeCity, 'active,permanent')
      .then((zones) => {
        if (Array.isArray(zones)) {
          setCongestionZones(zones);
        }
      })
      .catch(() => {
        setCongestionZones([]);
      });
  }, [activeCity, setCongestionZones]);

  return (
    <div className="relative h-screen w-screen overflow-hidden text-[#1A1A1A] font-sans selection:bg-[#FF5A5F]/30 bg-[#FAFAFA]">
      
      {/* Main App Container (Mobile-first max-w constraint) */}
      <div className="relative z-10 h-full flex flex-col max-w-md mx-auto overflow-hidden bg-white/50 shadow-2xl shadow-black/5">
        
        {/* Header with Background Skyline inside it */}
        <header className="relative pt-12 pb-6 px-6 shrink-0 overflow-hidden rounded-b-[2rem] shadow-sm">
          {/* Skyline Background limited to header area */}
          <div 
            className="absolute inset-0 z-0 transition-opacity duration-1000 ease-in-out"
            style={{
              backgroundImage: `url(${CITY_BGS[activeCity]})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              filter: 'blur(2px)',
              opacity: 0.8
            }}
          />
          {/* Light Blur + Low Opacity White Overlay */}
          <div className="absolute inset-0 z-0 bg-white/30" />
          <div className="absolute inset-0 z-0 bg-gradient-to-b from-white/10 via-white/60 to-[#FAFAFA]" />

          {/* Header Content */}
          <div className="relative z-10">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <div className="live-dot" />
                <span className="text-[10px] font-bold tracking-widest text-[#FF5A5F] uppercase">Sentinel Live</span>
              </div>
              <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center border border-gray-200 shadow-sm">
                <ShieldAlert className="w-4 h-4 text-[#FF5A5F]" />
              </div>
            </div>
            
            <h1 className="text-3xl font-extrabold mb-6 tracking-tight text-[#1A1A1A]">Incident Command</h1>
            
            <div className="flex bg-white/60 p-1 rounded-2xl border border-gray-200/60 backdrop-blur-md shadow-sm">
              <button
                onClick={() => setActiveCity('nyc')}
                className={`flex-1 py-3 text-xs font-bold rounded-xl transition-all duration-300 ${
                  activeCity === 'nyc' ? 'bg-[#FF5A5F] text-white shadow-md shadow-[#FF5A5F]/20' : 'text-[#1A1A1A]/50 hover:text-[#1A1A1A]/80'
                }`}
              >
                New York
              </button>
              <button
                onClick={() => setActiveCity('chandigarh')}
                className={`flex-1 py-3 text-xs font-bold rounded-xl transition-all duration-300 ${
                  activeCity === 'chandigarh' ? 'bg-[#FF5A5F] text-white shadow-md shadow-[#FF5A5F]/20' : 'text-[#1A1A1A]/50 hover:text-[#1A1A1A]/80'
                }`}
              >
                Chandigarh
              </button>
            </div>
          </div>
        </header>

        {/* Views */}
        <main className="flex-1 overflow-hidden relative">
          <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'home' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
            <div className="h-full overflow-y-auto pt-6 pb-24">
              {leftPanel}
            </div>
          </div>

          <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'map' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
             {centerPanel}
          </div>

          <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'copilot' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
             <div className="h-full w-full bg-[#FAFAFA]/90 backdrop-blur-xl">
               {rightPanel}
             </div>
          </div>

          <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'social' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
            <div className="h-full w-full bg-[#FAFAFA]/90 backdrop-blur-xl">
              {socialPanel}
            </div>
          </div>
        </main>


        {/* Bottom Navigation */}
        <nav className="shrink-0 bg-white/95 backdrop-blur-xl rounded-t-[2rem] border-t border-gray-100 relative z-30 pb-safe pt-2 shadow-[0_-4px_24px_rgba(0,0,0,0.02)]">
          <div className="flex justify-between items-center px-8 py-3 max-w-sm mx-auto">
            <NavItem icon={<Home />} label="Home" active={activeTab === 'home'} onClick={() => setActiveTab('home')} />
            <NavItem icon={<MapIcon />} label="Map" active={activeTab === 'map'} onClick={() => setActiveTab('map')} />
            <NavItem icon={<MessageCircle />} label="Copilot" active={activeTab === 'copilot'} onClick={() => setActiveTab('copilot')} />
            <NavItem icon={<Share2 />} label="Social" active={activeTab === 'social'} onClick={() => setActiveTab('social')} />
          </div>
        </nav>
      </div>
    </div>
  );
};

const NavItem = ({ icon, label, active, onClick }: { icon: ReactElement<{ className?: string }>, label: string, active: boolean, onClick: () => void }) => (
  <button 
    onClick={onClick}
    className={`flex flex-col items-center gap-1.5 transition-all duration-300 ${
      active ? 'text-[#FF5A5F] scale-105' : 'text-gray-400 hover:text-gray-600'
    }`}
  >
    {React.cloneElement(icon, { className: 'w-6 h-6' })}
    <span className="text-[10px] font-bold tracking-wide">{label}</span>
  </button>
);

export default AppShell;
