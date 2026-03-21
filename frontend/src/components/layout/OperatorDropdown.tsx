import React, { useState, useRef, useEffect } from 'react';
import { ChevronLeft, Check, LogOut, ChevronDown } from 'lucide-react';
import { useFeedStore, useOperatorStore, OPERATORS } from '../../store';

// Consistent color hash for avatar
const getColorHash = (name: string) => {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'
  ];
  return colors[Math.abs(hash) % colors.length];
};

const getInitials = (name: string) =>
  name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

const OperatorDropdown: React.FC = () => {
  const { city, switchCity } = useFeedStore();
  const { operator, setOperator } = useOperatorStore();
  const [isOpen, setIsOpen] = useState(false);
  
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const handleSelectOperator = (e: React.MouseEvent, selectedOperator: string, selectedCity: 'nyc' | 'chandigarh') => {
    e.stopPropagation();
    e.preventDefault();
    if (selectedCity !== city) {
      switchCity(selectedCity);
    }
    setOperator(selectedOperator);
    // Small delay to ensure state propagation before menu closes
    setTimeout(() => setIsOpen(false), 150);
  };

  const avatarColor = getColorHash(operator);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Header Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 hover:bg-scada-panel/80 transition-colors border border-transparent hover:border-scada-border rounded-sm"
      >
        <div className="flex flex-col items-end leading-none mr-1">
          <span className="text-[10px] font-mono text-scada-white font-bold">{operator}</span>
          <span className="text-[9px] font-mono text-scada-text-dim uppercase tracking-wider">
            {city === 'nyc' ? 'New York' : 'Chandigarh'}
          </span>
        </div>
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center border border-scada-bg"
          style={{ backgroundColor: avatarColor }}
        >
          <span className="text-[10px] font-bold text-white shadow-sm">{getInitials(operator)}</span>
        </div>
        <ChevronDown className={`h-3 w-3 text-scada-text-dim transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Main Dropdown Panel */}
      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-56 bg-scada-panel border border-scada-border shadow-2xl z-[9999]">
          <div className="p-3 border-b border-scada-border bg-scada-bg/50">
            <h3 className="text-[10px] font-mono uppercase text-scada-text-dim mb-1">Active Session</h3>
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                style={{ backgroundColor: avatarColor }}
              >
                <span className="text-xs font-bold text-white">{getInitials(operator)}</span>
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="text-xs font-bold text-scada-white truncate">{operator}</span>
                <span className="text-[10px] text-scada-text-dim uppercase">{city} Base</span>
              </div>
            </div>
          </div>

          <div className="p-1 font-mono text-[10px] uppercase">
            
            {/* 1. CHANGE SESSION */}
            <div className="relative group/session">
              <button className="w-full flex items-center justify-between px-3 py-2 text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors">
                <div className="flex items-center gap-2">
                  <ChevronLeft className="h-3 w-3 opacity-50" />
                  <span>Change Session</span>
                </div>
              </button>
              
              {/* Session -> Cities Popout (pops out to the LEFT) */}
              <div className="absolute top-0 right-[100%] mr-1 w-48 bg-scada-panel border border-scada-border shadow-xl hidden group-hover/session:block">
                
                {/* NYC City Hover */}
                <div className="relative group/nyc">
                  <button className="w-full flex items-center justify-between px-3 py-2 text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors">
                    <div className="flex items-center gap-2">
                      <ChevronLeft className="h-3 w-3 opacity-50" />
                      <span>New York</span>
                    </div>
                    {city === 'nyc' && <div className="w-1.5 h-1.5 rounded-full bg-scada-green" />}
                  </button>
                  {/* NYC Operators Popout */}
                  <div className="absolute top-0 right-[100%] mr-1 w-48 bg-scada-panel border border-scada-border shadow-xl hidden group-hover/nyc:block">
                    <div className="px-3 py-1.5 border-b border-scada-border bg-scada-bg/50 text-scada-text-dim">
                      NYC Operators
                    </div>
                    <div className="p-1 max-h-60 overflow-y-auto">
                      {OPERATORS.nyc.map((op) => (
                        <button
                          key={op}
                          onClick={(e) => handleSelectOperator(e, op, 'nyc')}
                          className="w-full flex items-center justify-between px-2 py-1.5 text-left text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors group"
                        >
                          <span className={operator === op ? 'text-scada-white font-bold' : ''}>{op}</span>
                          {operator === op && <Check className="h-3 w-3 text-scada-blue" />}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* CHD City Hover */}
                <div className="relative group/chd">
                  <button className="w-full flex items-center justify-between px-3 py-2 text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors">
                    <div className="flex items-center gap-2">
                      <ChevronLeft className="h-3 w-3 opacity-50" />
                      <span>Chandigarh</span>
                    </div>
                    {city === 'chandigarh' && <div className="w-1.5 h-1.5 rounded-full bg-scada-green" />}
                  </button>
                  {/* CHD Operators Popout */}
                  <div className="absolute top-0 right-[100%] mr-1 w-48 bg-scada-panel border border-scada-border shadow-xl hidden group-hover/chd:block">
                    <div className="px-3 py-1.5 border-b border-scada-border bg-scada-bg/50 text-scada-text-dim">
                      CHD Operators
                    </div>
                    <div className="p-1 max-h-60 overflow-y-auto">
                      {OPERATORS.chandigarh.map((op) => (
                        <button
                          key={op}
                          onClick={(e) => handleSelectOperator(e, op, 'chandigarh')}
                          className="w-full flex items-center justify-between px-2 py-1.5 text-left text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors group"
                        >
                          <span className={operator === op ? 'text-scada-white font-bold' : ''}>{op}</span>
                          {operator === op && <Check className="h-3 w-3 text-scada-blue" />}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

              </div>
            </div>

            {/* 2. CHANGE OPERATOR (Current Session) */}
            <div className="relative group/operator">
              <button className="w-full flex items-center justify-between px-3 py-2 text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors">
                <div className="flex items-center gap-2">
                  <ChevronLeft className="h-3 w-3 opacity-50" />
                  <span>Change Operator</span>
                </div>
              </button>
              
              {/* Operator Popout (pops out to the LEFT) */}
              <div className="absolute top-0 right-[100%] mr-1 w-48 bg-scada-panel border border-scada-border shadow-xl hidden group-hover/operator:block">
                <div className="px-3 py-1.5 border-b border-scada-border bg-scada-bg/50 text-scada-text-dim">
                  {city === 'nyc' ? 'NYC' : 'CHD'} Active Roster
                </div>
                <div className="p-1 max-h-60 overflow-y-auto">
                  {OPERATORS[city].map((op) => (
                    <button
                      key={op}
                      onClick={(e) => handleSelectOperator(e, op, city)}
                      className="w-full flex items-center justify-between px-2 py-1.5 text-left text-scada-text hover:bg-scada-bg hover:text-scada-white transition-colors group"
                    >
                      <span className={operator === op ? 'text-scada-white font-bold' : ''}>{op}</span>
                      {operator === op && <Check className="h-3 w-3 text-scada-blue" />}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
          
          <div className="border-t border-scada-border p-1">
             <button className="w-full flex items-center justify-between px-3 py-2 text-scada-red/70 hover:text-scada-red hover:bg-scada-red/10 transition-colors">
               <span className="text-[10px] font-mono uppercase">System Logout</span>
               <LogOut className="h-3 w-3" />
             </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default OperatorDropdown;
