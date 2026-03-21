import React, { useState, useEffect, useRef } from 'react';
import { Send, Terminal, Loader2, Mic, Square } from 'lucide-react';
import { useChatStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';

const formatTimestamp = (iso: string): string => {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
};

const ChatPanel: React.FC = () => {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const { messages, addMessage, isStreaming, setStreaming } = useChatStore();
  const { currentIncident, llmOutput } = useIncidentStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);
  const prevIncidentIdRef = useRef<string | null>(null);
  const prevLlmNarrativeRef = useRef<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Initial system message on mount
  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true;
      addMessage({
        role: 'system',
        content: 'SENTINEL CO-PILOT SESSION INITIATED. AWAITING LIVE FEED DATA.',
        timestamp: new Date().toISOString(),
      });
    }
  }, [addMessage]);

  // When currentIncident changes, add system message
  useEffect(() => {
    if (currentIncident && currentIncident.id !== prevIncidentIdRef.current) {
      prevIncidentIdRef.current = currentIncident.id;
      addMessage({
        role: 'system',
        content: `INCIDENT DETECTED: ${currentIncident.on_street}. LLM intelligence incoming.`,
        timestamp: new Date().toISOString(),
      });
    }
  }, [currentIncident, addMessage]);

  // When llmOutput changes, add assistant message with narrative
  useEffect(() => {
    const narrative = llmOutput?.narrative_update ?? null;
    if (narrative && narrative !== prevLlmNarrativeRef.current) {
      prevLlmNarrativeRef.current = narrative;
      addMessage({
        role: 'assistant',
        content: narrative,
        timestamp: new Date().toISOString(),
      });
    }
  }, [llmOutput, addMessage]);

  // Load chat history from backend
  useEffect(() => {
    const incidentId = currentIncident?.id || 'general';
    api.getChatHistory(incidentId)
      .then((data) => {
        if (data?.messages && Array.isArray(data.messages)) {
          if (messages.length <= 1) {
            data.messages.forEach((msg: any) => {
              addMessage({
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp || new Date().toISOString(),
              });
            });
          }
        }
      })
      .catch(() => {});
  }, [currentIncident?.id]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
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
      console.error('Microphone access denied', err);
    }
  };

  const handleVoiceSend = async (base64Audio: string, mimeType: string) => {
    if (isStreaming) return;
    addMessage({ role: 'user', content: '[VOICE COMMAND RECORDED]', timestamp: new Date().toISOString() });
    setStreaming(true);
    try {
      const response = await api.sendChat('[voice]', currentIncident?.id, { audio_base64: base64Audio, audio_mime_type: mimeType });
      addMessage({
        role: 'assistant',
        content: response.content || 'No response from backend.',
        timestamp: new Date().toISOString(),
      });
    } catch {
      addMessage({ role: 'assistant', content: 'ERROR: Voice processing failed.', timestamp: new Date().toISOString() });
    } finally {
      setStreaming(false);
    }
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || isRecording) return;

    addMessage({ role: 'user', content: trimmed, timestamp: new Date().toISOString() });
    setInput('');
    setStreaming(true);

    try {
      const response = await api.sendChat(trimmed, currentIncident?.id);
      addMessage({
        role: 'assistant',
        content: response.content || 'No response from backend.',
        timestamp: new Date().toISOString(),
      });
    } catch {
      addMessage({
        role: 'assistant',
        content: 'ERROR: Unable to reach backend. Retrying is recommended.',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
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
              <span className="uppercase font-bold text-scada-text">
                {msg.role === 'user' ? 'OFC. MARTINEZ' : msg.role === 'assistant' ? 'AI CO-PILOT' : 'SYSTEM'}
              </span>
              <span>{formatTimestamp(msg.timestamp)}</span>
            </div>
            <p className={`text-[11px] font-mono leading-relaxed whitespace-pre-wrap ${
              msg.role === 'system'
                ? 'text-scada-text-dim italic'
                : msg.role === 'user' && msg.content === '[VOICE COMMAND RECORDED]'
                  ? 'text-scada-blue italic font-bold'
                  : 'text-scada-header'
            }`}>
              {msg.content}
            </p>
          </div>
        ))}
        {isStreaming && (
          <div className="flex items-center gap-2 text-[10px] font-mono text-scada-text-dim">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>PROCESSING...</span>
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
              disabled={isStreaming || isRecording}
              placeholder={isRecording ? 'RECORDING COMMAND...' : 'ENTER COMMAND...'}
              className={`w-full bg-transparent pl-7 pr-3 py-2 text-[10px] font-mono focus:outline-none uppercase disabled:opacity-50 ${
                isRecording ? 'text-scada-red placeholder:text-scada-red animate-pulse' : 'text-scada-header placeholder:text-scada-text-dim'
              }`}
            />
          </div>
          <button
            onClick={toggleRecording}
            disabled={isStreaming}
            className={`px-3 py-2 disabled:opacity-50 transition-colors flex items-center justify-center border ${
              isRecording
                ? 'bg-scada-red text-white border-scada-red'
                : 'bg-scada-panel text-scada-text border-scada-border hover:bg-scada-bg'
            }`}
            title="Voice Command"
          >
            {isRecording ? <Square className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
          </button>
          <button
            onClick={handleSend}
            disabled={isStreaming || isRecording}
            className="bg-scada-text text-scada-bg px-4 py-2 hover:bg-scada-header transition-colors flex items-center gap-2 disabled:opacity-50"
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
