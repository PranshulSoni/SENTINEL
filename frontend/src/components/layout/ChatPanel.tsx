import React, { useState } from 'react';
import { Send, Terminal } from 'lucide-react';

/* ═══ STATIC MOCK MESSAGES ═══ */
const MOCK_MESSAGES = [
  {
    role: 'system',
    content: 'SENTINEL CO-PILOT SESSION INITIATED. INGESTING LIVE FEEDS.',
    timestamp: '14:23:17',
  },
  {
    role: 'assistant',
    content: '[INCIDENT DETECTED]: Broadway & W 34th St.\nIntelligence generated. Awaiting officer confirmation.',
    timestamp: '14:23:22',
    isAlert: true,
  },
  {
    role: 'user',
    content: 'Is it safe to open the southbound lane on Broadway now?',
    timestamp: '14:28:45',
  },
  {
    role: 'assistant',
    content: '[NEGATIVE] — Cannot recommend lane opening.\n\n• Segment 1001 blocked\n• FDNY still on scene\n• Wreckage clearance not confirmed\n\nMaintain closure. Current diversion is handling traffic well.',
    timestamp: '14:28:48',
    isNegative: true,
  },
  {
    role: 'user',
    content: 'What\'s the estimated clearance time?',
    timestamp: '14:31:10',
  },
  {
    role: 'assistant',
    content: '[ESTIMATED CLEARANCE]: 35-50 minutes.\n\nPartial lane opening may be possible in ~18 mins after medical triage clears. I will alert you.',
    timestamp: '14:31:14',
    isWarning: true,
  },
];

const ChatPanel: React.FC = () => {
  const [input, setInput] = useState('');

  return (
    <div className="flex flex-col h-full bg-scada-bg">
      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {MOCK_MESSAGES.map((msg, i) => (
          <div key={i} className="flex flex-col gap-1.5 border-l-2 pl-3 border-scada-border transition-colors hover:border-scada-text-dim">
             <div className="flex items-center gap-2 text-[9px] font-mono text-scada-text-dim">
                <span className={`uppercase font-bold ${
                  msg.role === 'user' ? 'text-scada-green' : 
                  msg.role === 'assistant' ? 'text-scada-blue' : 
                  'text-scada-text-dim'
                }`}>
                  {msg.role === 'user' ? 'OFC. MARTINEZ' : msg.role === 'assistant' ? 'AI CO-PILOT' : 'SYSTEM'}
                </span>
                <span>{msg.timestamp}</span>
             </div>
             <p className={`text-[11px] font-mono leading-relaxed whitespace-pre-wrap ${
                msg.isAlert ? 'text-scada-red font-bold' :
                msg.isNegative ? 'text-scada-red' :
                msg.isWarning ? 'text-scada-yellow' :
                msg.role === 'system' ? 'text-scada-text-dim italic' : 'text-scada-header'
             }`}>
                {msg.content}
             </p>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-scada-border">
        <div className="flex gap-2">
          <div className="flex-1 relative flex items-center bg-scada-surface border border-scada-border focus-within:border-scada-blue transition-colors">
            <Terminal className="absolute left-2 h-4 w-4 text-scada-text" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="ENTER COMMAND..."
              className="w-full bg-transparent pl-8 pr-3 py-2 text-[11px] font-mono text-scada-header focus:outline-none placeholder:text-scada-text-dim uppercase tracking-wider"
            />
          </div>
          <button className="bg-scada-text text-scada-bg px-4 py-2 hover:bg-scada-blue transition-colors flex items-center gap-2 font-bold group">
            <span className="text-[10px] font-mono uppercase group-hover:text-black">SEND</span>
            <Send className="h-4 w-4 group-hover:text-black" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
