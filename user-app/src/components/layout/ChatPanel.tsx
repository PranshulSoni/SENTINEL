import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Mic, Square } from 'lucide-react';

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
    <div className="flex flex-col h-full bg-transparent">
      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 pb-28 space-y-6">
        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
             <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500">
                <span className={`uppercase tracking-wider ${msg.role === 'assistant' ? (msg.safety_assessment === 'unsafe' ? 'text-[#FF5A5F]' : msg.safety_assessment === 'caution' ? 'text-[#eab308]' : 'text-[#A3B18A]') : 'text-gray-800'}`}>
                  {msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'Copilot' : 'System'}
                  {msg.safety_assessment && msg.safety_assessment !== 'unknown' && ` [${msg.safety_assessment.toUpperCase()}]`}
                </span>
                <span>{msg.timestamp}</span>
             </div>
             
             <div className={`px-4 py-3 rounded-[1.25rem] max-w-[85%] text-sm font-medium leading-relaxed shadow-sm ${
                msg.role === 'system' ? 'w-full bg-gray-50 text-gray-500 italic border border-gray-100 text-center rounded-2xl' : 
                msg.role === 'user' ? 'bg-[#FF5A5F] text-white rounded-tr-sm shadow-md shadow-[#FF5A5F]/20' : 
                'bg-white text-[#1A1A1A] border border-gray-100 rounded-tl-sm shadow-sm'
             }`}>
                <p className={`${msg.content === '[VOICE COMMAND RECORDED]' ? 'italic font-bold' : ''}`}>
                  {msg.content}
                </p>
             </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-xs font-bold text-gray-400 pl-2">
            <Loader2 className="w-4 h-4 animate-spin text-[#A3B18A]" />
            <span className="animate-pulse">Analyzing context...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="absolute bottom-0 w-full p-6 pt-2 pb-safe bg-gradient-to-t from-[#FAFAFA] via-[#FAFAFA]/95 to-transparent">
        <div className="flex gap-2.5 max-w-md mx-auto relative">
          <div className="flex-1 relative flex items-center bg-white rounded-full border border-gray-200 shadow-sm px-4 focus-within:border-[#FF5A5F] focus-within:ring-1 focus-within:ring-[#FF5A5F] transition-all">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading || isRecording}
              placeholder={isRecording ? "Listening..." : "Message Copilot..."}
              className={`w-full bg-transparent py-3.5 text-xs focus:outline-none disabled:opacity-50 ${isRecording ? 'text-[#FF5A5F] placeholder:text-[#FF5A5F] animate-pulse font-bold' : 'text-[#1A1A1A] placeholder:text-gray-400 font-bold'}`}
            />
          </div>
          <button
            onClick={toggleRecording}
            disabled={loading}
            className={`w-[48px] h-[48px] shrink-0 rounded-full disabled:opacity-50 transition-all flex items-center justify-center shadow-lg ${isRecording ? 'bg-[#FF5A5F] text-white shadow-[#FF5A5F]/30 hover:scale-105' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}
            title="Voice Command"
          >
            {isRecording ? <Square className="w-5 h-5 fill-current" /> : <Mic className="w-5 h-5" />}
          </button>
          <button 
            onClick={handleSend}
            disabled={loading || isRecording || !input.trim()}
            className="w-[48px] h-[48px] shrink-0 bg-[#1A1A1A] text-white rounded-full disabled:opacity-50 transition-all flex items-center justify-center shadow-md hover:scale-105 hover:bg-black disabled:hover:scale-100"
          >
            <Send className="w-5 h-5 ml-1" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
