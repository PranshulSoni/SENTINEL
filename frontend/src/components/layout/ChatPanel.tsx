import React, { useState, useRef, useEffect } from 'react';
import { Send, Terminal, Loader2, Mic, Square } from 'lucide-react';

interface ChatMessage {
  role: 'system' | 'assistant' | 'user';
  content: string;
  timestamp: string;
  safety_assessment?: string;
  confidence?: string;
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    role: 'system',
    content: 'SENTINEL CO-PILOT SESSION INITIATED. INGESTING LIVE FEEDS.',
    timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
  }
];

const ChatPanel: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleRecording = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
        setIsRecording(false);
      }
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Use webm for broad compatibility, or what the browser supports natively
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' });
          const reader = new FileReader();
          reader.readAsDataURL(audioBlob);
          reader.onloadend = () => {
            const base64data = (reader.result as string).split(',')[1];
            handleVoiceSend(base64data, audioBlob.type || 'audio/webm');
          };
          stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        setIsRecording(true);
      } catch (err) {
        console.error("Microphone access denied or failing", err);
      }
    }
  };

  const handleVoiceSend = async (base64Audio: string, mimeType: string) => {
    if (loading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: '[VOICE COMMAND RECORDED]',
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false })
    };

    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/narrative/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          audio_base64: base64Audio,
          audio_mime_type: mimeType
        })
      });

      if (!res.ok) throw new Error('API Error');

      const data = await res.json();
      
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: data.answer,
        timestamp: data.timestamp ? data.timestamp.split(' ')[1] : new Date().toLocaleTimeString('en-US', { hour12: false }),
        safety_assessment: data.safety_assessment,
        confidence: data.confidence
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: 'ERROR: CONNECTION TO BACKEND FAILED.',
        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false })
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading || isRecording) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false })
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/narrative/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMsg.content })
      });

      if (!res.ok) throw new Error('API Error');

      const data = await res.json();
      
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: data.answer,
        timestamp: data.timestamp ? data.timestamp.split(' ')[1] : new Date().toLocaleTimeString('en-US', { hour12: false }),
        safety_assessment: data.safety_assessment,
        confidence: data.confidence
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: 'ERROR: CONNECTION TO BACKEND FAILED.',
        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false })
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-scada-bg">
      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className="flex flex-col gap-1">
             <div className="flex items-center gap-2 text-[9px] font-mono text-scada-text-dim">
                <span className={`uppercase font-bold ${msg.role === 'assistant' ? (msg.safety_assessment === 'unsafe' ? 'text-scada-red' : msg.safety_assessment === 'caution' ? 'text-scada-yellow' : 'text-scada-text') : 'text-scada-text'}`}>
                  {msg.role === 'user' ? 'OFC. MARTINEZ' : msg.role === 'assistant' ? 'AI CO-PILOT' : 'SYSTEM'}
                  {msg.safety_assessment && msg.safety_assessment !== 'unknown' && ` [${msg.safety_assessment.toUpperCase()}]`}
                </span>
                <span>{msg.timestamp}</span>
             </div>
             <p className={`text-[11px] font-mono leading-relaxed whitespace-pre-wrap ${
                msg.role === 'system' ? 'text-scada-text-dim italic' : msg.role === 'user' && msg.content === '[VOICE COMMAND RECORDED]' ? 'text-scada-blue italic font-bold' : 'text-scada-header'
             }`}>
                {msg.content}
             </p>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-[10px] font-mono text-scada-text-dim">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>ANALYZING NARRATIVE WITH NATIVE AUDIO...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
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
              onKeyDown={handleKeyDown}
              disabled={loading || isRecording}
              placeholder={isRecording ? "RECORDING COMMAND..." : "ENTER COMMAND..."}
              className={`w-full bg-transparent pl-7 pr-3 py-2 text-[10px] font-mono focus:outline-none uppercase disabled:opacity-50 ${isRecording ? 'text-scada-red placeholder:text-scada-red animate-pulse' : 'text-scada-header placeholder:text-scada-text-dim'}`}
            />
          </div>
          <button
            onClick={toggleRecording}
            disabled={loading}
            className={`px-3 py-2 disabled:opacity-50 transition-colors flex items-center justify-center border ${isRecording ? 'bg-scada-red text-scada-white border-scada-red' : 'bg-scada-panel text-scada-text border-scada-border hover:bg-scada-bg'}`}
            title="Voice Command"
          >
            {isRecording ? <Square className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
          </button>
          <button 
            onClick={handleSend}
            disabled={loading || isRecording}
            className="bg-scada-text text-scada-bg px-4 py-2 hover:bg-scada-header disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            <span className="text-[10px] font-mono font-bold uppercase">SEND</span>
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
