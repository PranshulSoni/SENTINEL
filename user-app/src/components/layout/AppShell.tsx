import React, { useState, useEffect } from 'react';
import type { ReactElement } from 'react';
import { Map as MapIcon, Home, MessageCircle, Share2, Sun, Moon, ShieldAlert } from 'lucide-react';
import { useFeedStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';
import { useTheme } from '../../hooks/useTheme';

interface AppShellProps {
  leftPanel: React.ReactNode;
  centerPanel: React.ReactNode;
  rightPanel: React.ReactNode;
  socialPanel: React.ReactNode;
}

const AppShell: React.FC<AppShellProps> = ({ leftPanel, centerPanel, rightPanel, socialPanel }) => {
  const { city: activeCity, switchCity: setActiveCity, fetchCityInfo } = useFeedStore();
  const setCongestionZones = useIncidentStore((s) => s.setCongestionZones);
  const [activeTab, setActiveTab] = useState<'home' | 'map' | 'copilot' | 'social'>('home');
  const { isDark, toggleTheme } = useTheme();

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
    <div
      className="relative h-screen w-screen overflow-hidden"
      style={{ background: 'var(--color-bg)', color: 'var(--color-text)' }}
    >
      {/* Main App Container */}
      <div
        className="relative z-10 h-full flex flex-col max-w-md mx-auto overflow-hidden"
        style={{ borderLeft: '1px solid var(--color-border)', borderRight: '1px solid var(--color-border)' }}
      >
        {/* ── Header ── */}
        <header
          className="shrink-0 px-5 pt-10 pb-4"
          style={{
            background: 'var(--color-surface)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          {/* Top row: brand + controls */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="h-4 w-4" style={{ color: 'var(--color-accent)' }} />
              <span
                className="text-sm font-black uppercase tracking-[0.2em]"
                style={{ color: 'var(--color-text)' }}
              >
                SENTINEL
              </span>
              <span className="live-dot" />
            </div>
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center h-7 w-7 transition-colors"
              style={{
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-secondary)',
                background: 'transparent',
              }}
              title={isDark ? 'Light mode' : 'Dark mode'}
            >
              {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            </button>
          </div>

          {/* City selector */}
          <div
            className="flex"
            style={{ border: '1px solid var(--color-border)' }}
          >
            {(['nyc', 'chandigarh'] as const).map((c, i) => (
              <button
                key={c}
                onClick={() => setActiveCity(c)}
                className="flex-1 py-2.5 text-[11px] font-bold uppercase tracking-[0.12em] transition-colors duration-150"
                style={{
                  background: activeCity === c ? 'var(--color-accent)' : 'transparent',
                  color: activeCity === c ? '#fff' : 'var(--color-text-secondary)',
                  borderLeft: i > 0 ? '1px solid var(--color-border)' : 'none',
                }}
              >
                {c === 'nyc' ? 'New York' : 'Chandigarh'}
              </button>
            ))}
          </div>
        </header>

        {/* ── Views ── */}
        <main className="flex-1 overflow-hidden relative">
          <div className={`absolute inset-0 transition-opacity duration-200 ${activeTab === 'home' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
            <div className="h-full overflow-y-auto pt-5 pb-24">
              {leftPanel}
            </div>
          </div>

          <div className={`absolute inset-0 transition-opacity duration-200 ${activeTab === 'map' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
            {centerPanel}
          </div>

          <div className={`absolute inset-0 transition-opacity duration-200 ${activeTab === 'copilot' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
            <div className="h-full w-full" style={{ background: 'var(--color-bg)' }}>
              {rightPanel}
            </div>
          </div>

          <div className={`absolute inset-0 transition-opacity duration-200 ${activeTab === 'social' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
            <div className="h-full w-full" style={{ background: 'var(--color-bg)' }}>
              {socialPanel}
            </div>
          </div>
        </main>

        {/* ── Bottom Navigation ── */}
        <nav
          className="shrink-0 pb-safe relative z-30"
          style={{
            background: 'var(--color-surface)',
            borderTop: '1px solid var(--color-border)',
          }}
        >
          <div className="flex justify-between items-center px-6 py-3 max-w-sm mx-auto">
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

const NavItem = ({
  icon,
  label,
  active,
  onClick,
}: {
  icon: ReactElement<{ className?: string }>;
  label: string;
  active: boolean;
  onClick: () => void;
}) => (
  <button
    onClick={onClick}
    className="flex flex-col items-center gap-1 transition-all duration-200 min-w-[44px] min-h-[44px] justify-center"
    style={{ color: active ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}
  >
    {React.cloneElement(icon, { className: 'w-5 h-5' })}
    <span
      className="text-[9px] font-bold uppercase tracking-[0.1em]"
      style={{ color: active ? 'var(--color-accent)' : 'var(--color-text-secondary)' }}
    >
      {label}
    </span>
    {active && (
      <div
        className="h-[2px] w-4"
        style={{ background: 'var(--color-accent)' }}
      />
    )}
  </button>
);

export default AppShell;
