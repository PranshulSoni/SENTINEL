import React from 'react';
import { 
  ChevronDown, 
  ChevronRight, 
  RotateCcw, 
  X, 
  Zap, 
  Check, 
  Activity
} from 'lucide-react';

// --- Card ---
interface CardProps {
  variant?: 'critical' | 'warning' | 'info' | 'ai' | 'normal';
  elevated?: boolean;
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ 
  variant = 'normal', 
  elevated = false, 
  className = '', 
  children,
  onClick 
}) => {
  const variantClass = {
    critical: 'card--critical',
    warning: 'card--warning',
    info: 'card--info',
    ai: 'card--ai',
    normal: ''
  }[variant];

  return (
    <div 
      onClick={onClick}
      className={`card ${variantClass} ${elevated ? 'focus-mode-elevated shadow-lg' : ''} ${className} ${onClick ? 'cursor-pointer' : ''}`}
    >
      {children}
    </div>
  );
};

// --- StatusDot ---
interface StatusDotProps {
  status: 'live' | 'idle' | 'error' | 'warning';
  className?: string;
}

export const StatusDot: React.FC<StatusDotProps> = ({ status, className = '' }) => {
  const colorClass = {
    live: 'bg-success',
    idle: 'bg-text-dim',
    error: 'bg-critical',
    warning: 'bg-warning'
  }[status];

  const pulse = (status === 'live' || status === 'error') ? 'animate-pulse-live' : '';

  return <span className={`status-dot ${colorClass} ${pulse} ${className}`} />;
};

// --- SectionPanel ---
interface SectionPanelProps {
  title: string;
  icon?: React.ReactNode;
  isExpanded: boolean;
  onToggle: () => void;
  badge?: string | number;
  children: React.ReactNode;
}

export const SectionPanel: React.FC<SectionPanelProps> = ({ 
  title, 
  icon, 
  isExpanded, 
  onToggle, 
  badge, 
  children 
}) => {
  return (
    <div className="border-b border-border-dim">
      <button 
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-panel transition-colors"
      >
        <div className="flex items-center gap-3">
          {icon && <span className="text-text-dim">{icon}</span>}
          <span className="section-label font-bold text-text-bright">{title}</span>
          {badge !== undefined && (
            <span className="badge bg-border-strong text-text-bright">{badge}</span>
          )}
        </div>
        {isExpanded ? <ChevronDown className="h-4 w-4 text-text-dim" /> : <ChevronRight className="h-4 w-4 text-text-dim" />}
      </button>
      <div 
        className={`overflow-hidden transition-all duration-200 ease-in-out`}
        style={{ maxHeight: isExpanded ? '2000px' : '0' }}
      >
        {children}
      </div>
    </div>
  );
};

// --- ActionButton ---
interface ActionButtonProps {
  label: string;
  icon?: React.ReactNode;
  intent?: 'primary' | 'danger' | 'caution' | 'ghost';
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
}

export const ActionButton: React.FC<ActionButtonProps> = ({
  label,
  icon,
  intent = 'primary',
  onClick,
  loading = false,
  disabled = false,
  className = ''
}) => {
  const intentClasses = {
    primary: 'bg-info text-bg hover:bg-text-bright',
    danger: 'border border-critical text-critical hover:bg-critical hover:text-bg',
    caution: 'border border-warning text-warning hover:bg-warning hover:text-bg',
    ghost: 'text-text-dim hover:text-text-bright border border-transparent hover:border-border-strong'
  }[intent];

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`px-3 py-1.5 font-mono text-[10px] uppercase font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 ${intentClasses} ${className}`}
    >
      {loading ? (
        <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        icon
      )}
      {label}
    </button>
  );
};

// --- AISuggestion ---
interface AISuggestionProps {
  action: string;
  benefit?: string;
  onApply: () => void;
  onIgnore: () => void;
}

export const AISuggestion: React.FC<AISuggestionProps> = ({ action, benefit, onApply, onIgnore }) => {
  return (
    <Card variant="ai" className="mt-2 group relative overflow-hidden">
      <div className="flex items-center gap-2 mb-2">
        <Zap className="h-3 w-3 text-ai-accent" />
        <span className="section-label text-ai-accent">AI Suggestion</span>
      </div>
      <p className="text-[11px] text-text-main mb-3 leading-relaxed">
        {action} {benefit && <span className="text-success font-bold">({benefit})</span>}
      </p>
      <div className="flex gap-2">
        <ActionButton 
          label="Apply" 
          intent="primary" 
          onClick={onApply} 
          className="flex-1 !bg-ai-accent !text-white"
          icon={<Check className="h-3 w-3" />}
        />
        <ActionButton 
          label="Ignore" 
          intent="ghost" 
          onClick={onIgnore} 
          className="flex-1"
          icon={<X className="h-3 w-3" />}
        />
      </div>
    </Card>
  );
};

// --- StateTimeline ---
interface TimelineEvent {
  time: string;
  label: string;
  category: 'detection' | 'ai' | 'operator' | 'system';
}

export const StateTimeline: React.FC<{ events: TimelineEvent[] }> = ({ events }) => {
  const catColors = {
    detection: 'bg-critical',
    ai: 'bg-ai-accent',
    operator: 'bg-info',
    system: 'bg-text-dim'
  };

  return (
    <div className="timeline-rail py-2 space-y-4">
      {events.map((ev, i) => (
        <div key={i} className="relative">
          <span className={`absolute -left-[18px] top-1 h-2 w-2 rounded-full ${catColors[ev.category]}`} />
          <div className="flex flex-col">
            <span className="text-[9px] font-mono text-text-dim uppercase leading-none mb-1">{ev.time}</span>
            <span className="text-[11px] font-mono text-text-main leading-tight">{ev.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

// --- IncidentFocusTabs ---
interface IncidentFocusTabsProps {
  incidents: { id: string; street: string; severity: string }[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
  onAdd: () => void;
}

export const IncidentFocusTabs: React.FC<IncidentFocusTabsProps> = ({ 
  incidents, 
  activeId, 
  onSelect, 
  onClose,
  onAdd
}) => {
  return (
    <div className="flex items-center gap-1 p-2 bg-panel border-b border-border-dim overflow-x-auto scroller-hidden">
      {incidents.map((inc) => (
        <div 
          key={inc.id}
          className={`flex items-center gap-2 px-3 py-1.5 border rounded-sm transition-all cursor-pointer ${
            activeId === inc.id 
              ? 'bg-card border-critical' 
              : 'bg-bg border-border-dim hover:border-border-strong opacity-70'
          }`}
          onClick={() => onSelect(inc.id)}
        >
          <StatusDot status={inc.severity === 'critical' ? 'error' : 'warning'} />
          <span className="text-[10px] font-mono font-bold text-text-bright truncate max-w-[80px]">
            {inc.street}
          </span>
          <button 
            onClick={(e) => { e.stopPropagation(); onClose(inc.id); }}
            className="text-text-dim hover:text-critical"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ))}
      <button 
        onClick={onAdd}
        className="px-3 py-1.5 text-[10px] font-mono text-text-dim hover:text-text-bright border border-dashed border-border-dim rounded-sm"
      >
        + ADD
      </button>
    </div>
  );
};

// --- UndoToast ---
export const UndoToast: React.FC<{ 
  message: string, 
  onUndo: () => void, 
  duration?: number 
}> = ({ message, onUndo, duration = 7000 }) => {
  return (
    <div className="fixed bottom-6 left-[380px] z-[2000] animate-alert-slide">
      <div className="bg-card border border-info flex flex-col min-w-[300px] overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between p-3 gap-6">
          <div className="flex items-center gap-3">
            <Check className="h-4 w-4 text-success" />
            <span className="text-[11px] font-mono text-text-bright uppercase font-bold">{message}</span>
          </div>
          <button 
            onClick={onUndo}
            className="flex items-center gap-2 px-3 py-1 bg-info text-bg font-bold text-[10px] uppercase hover:bg-text-bright transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Undo
          </button>
        </div>
        <div className="h-1 bg-info/20 w-full relative overflow-hidden">
          <div 
            className="h-full bg-info absolute left-0" 
            style={{ animation: `undo-countdown ${duration}ms linear forwards` }}
          />
        </div>
      </div>
    </div>
  );
};

// --- MetricsBar ---
interface MetricsBarProps {
  flow: number;
  activeCount: number;
  delay: string;
}

export const MetricsBar: React.FC<MetricsBarProps> = ({ flow, activeCount, delay }) => {
  const flowColor = flow > 75 ? 'text-success' : flow > 50 ? 'text-warning' : 'text-critical';

  return (
    <div className="flex items-center gap-6 px-4 py-1.5 bg-bg border border-border-dim rounded-sm">
      <div className="flex items-center gap-2">
        <Activity className="h-3 w-3 text-text-dim" />
        <span className="text-[10px] font-mono text-text-dim uppercase tracking-wider">Traffic Health</span>
      </div>
      <div className="h-4 w-[1px] bg-border-dim" />
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-text-dim uppercase">Flow:</span>
          <span className={`text-[11px] font-mono font-bold ${flowColor}`}>{flow}%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-text-dim uppercase">Active:</span>
          <span className="text-[11px] font-mono font-bold text-text-bright">{activeCount}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-text-dim uppercase">Avg Delay:</span>
          <span className="text-[11px] font-mono font-bold text-warning">+{delay}m</span>
        </div>
      </div>
    </div>
  );
};
