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
    content: 'INCIDENT DETECTED: Broadway & W 34th St. Intelligence generated.',
    timestamp: '14:23:22',
  },
  {
    role: 'user',
    content: 'Is it safe to open the southbound lane on Broadway now?',
    timestamp: '14:28:45',
  },
  {
    role: 'assistant',
    content: 'NEGATIVE — Cannot recommend lane opening.\n\n• Segment 1001 blocked\n• FDNY still on scene\n• Wreckage clearance not confirmed\n\nMaintain closure. Current diversion is handling traffic well.',
    timestamp: '14:28:48',
  },
  {
    role: 'user',
    content: 'What\'s the estimated clearance time?',
    timestamp: '14:31:10',
  },
  {
    role: 'assistant',
    content: 'ESTIMATED CLEARANCE: 35-50 minutes.\n\nPartial lane opening may be possible in ~18 mins after medical triage clears. I will alert you.',
    timestamp: '14:31:14',
  },
];

const ChatPanel: React.FC = () => {
  const [input, setInput] = useState('');

  return (
    <div className="flex flex-col h-full bg-scada-bg">
      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {MOCK_MESSAGES.map((msg, i) => (
          <div key={i} className="flex flex-col gap-1">
             <div className="flex items-center gap-2 text-[9px] font-mono text-scada-text-dim">
                <span className="uppercase font-bold text-scada-text">
                  {msg.role === 'user' ? 'OFC. MARTINEZ' : msg.role === 'assistant' ? 'AI CO-PILOT' : 'SYSTEM'}
                </span>
                <span>{msg.timestamp}</span>
             </div>
             <p className={`text-[11px] font-mono leading-relaxed whitespace-pre-wrap ${
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
          <div className="flex-1 relative flex items-center bg-scada-panel border border-scada-border">
            <Terminal className="absolute left-2 h-3 w-3 text-scada-text-dim" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="ENTER COMMAND..."
              className="w-full bg-transparent pl-7 pr-3 py-2 text-[10px] font-mono text-scada-header focus:outline-none placeholder:text-scada-text-dim uppercase"
            />
          </div>
          <button className="bg-scada-text text-scada-bg px-4 py-2 hover:bg-scada-header transition-colors flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold uppercase">SEND</span>
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
