import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Send, Terminal, Loader2, Mic, Square, MessageSquare, FileText, Zap } from 'lucide-react';
import { useChatStore, useIncidentStore, useUIStore } from '../../store';
import { api } from '../../services/api';
import { Card, ActionButton, StatusDot } from '../UIKit';

const formatTimestamp = (iso: string): string => {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
};

const ChatPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'logs' | 'ai'>('chat');
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  
  const { messages, addMessage, isStreaming, setStreaming } = useChatStore();
  const { currentIncident, llmOutput } = useIncidentStore();
  const { focusMode } = useUIStore();
  
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

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeTab]);

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

  const logMessages = useMemo(() => messages.filter(m => m.role === 'system'), [messages]);
  const aiNarratives = useMemo(() => messages.filter(m => m.role === 'assistant'), [messages]);
  const chatMessages = useMemo(() => messages.filter(m => m.role !== 'system'), [messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-panel">
      {/* TABS HEADER */}
      <div className="flex border-b border-border-dim bg-bg p-1">
        {[
          { id: 'chat', label: 'CHAT', icon: <MessageSquare className="h-3 w-3" /> },
          { id: 'logs', label: 'SYSTEM LOGS', icon: <FileText className="h-3 w-3" /> },
          { id: 'ai', label: 'AI FEED', icon: <Zap className="h-3 w-3" /> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex-1 flex items-center justify-center gap-2 py-2 text-[10px] font-mono font-bold uppercase transition-all ${
              activeTab === tab.id 
                ? 'bg-panel text-text-bright border-b-2 border-info' 
                : 'text-text-dim hover:text-text-main'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Messages Area */}
      <div className={`flex-1 overflow-y-auto p-4 space-y-4 transition-all duration-300 ${focusMode === 'incident' && activeTab === 'chat' ? 'opacity-60' : 'opacity-100'}`}>
        {(activeTab === 'chat' ? chatMessages : activeTab === 'logs' ? logMessages : aiNarratives).map((msg, i) => (
          <div key={i} className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className="flex items-center gap-2 text-[9px] font-mono text-text-dim">
              <span className={`uppercase font-bold ${msg.role === 'assistant' ? 'text-ai-accent' : 'text-text-main'}`}>
                {msg.role === 'user' ? 'OPERATOR' : msg.role === 'assistant' ? 'AI CO-PILOT' : 'SYSTEM'}
              </span>
              <span>{formatTimestamp(msg.timestamp)}</span>
            </div>
            
            <Card 
              variant={msg.role === 'assistant' ? 'ai' : msg.role === 'system' ? 'info' : 'normal'}
              className={`!p-3 !max-w-[85%] border-transparent ${
                msg.role === 'user' ? 'bg-info/10' : ''
              } ${msg.role === 'system' ? 'italic' : ''}`}
            >
              <p className={`text-[11px] font-mono leading-relaxed whitespace-pre-wrap ${
                msg.role === 'user' && msg.content === '[VOICE COMMAND RECORDED]' 
                  ? 'text-info italic font-bold' 
                  : 'text-text-bright'
              }`}>
                {msg.content}
              </p>
            </Card>
          </div>
        ))}
        {isStreaming && (
          <div className="flex items-center gap-2 text-[10px] font-mono text-ai-accent animate-pulse">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>AI THINKING...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-border-dim bg-bg">
        <div className="flex gap-2">
          <div className="flex-1 relative flex items-center bg-panel border border-border-dim focus-within:border-info transition-colors rounded-sm">
            <Terminal className="absolute left-2.5 h-3 w-3 text-text-dim" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming || isRecording}
              placeholder={isRecording ? 'RECORDING COMMAND...' : 'ENTER COMMAND...'}
              className={`w-full bg-transparent pl-8 pr-3 py-2 text-[11px] font-mono focus:outline-none uppercase disabled:opacity-50 ${
                isRecording ? 'text-critical placeholder:text-critical animate-pulse' : 'text-text-bright'
              }`}
            />
          </div>
          
          <button
            onClick={toggleRecording}
            disabled={isStreaming}
            className={`w-10 h-10 flex items-center justify-center border transition-all rounded-sm ${
              isRecording
                ? 'bg-critical text-bg border-critical animate-pulse-live'
                : 'bg-panel text-text-dim border-border-dim hover:text-text-bright'
            }`}
          >
            {isRecording ? <Square className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
          </button>
          
          <ActionButton
            label="Send"
            onClick={handleSend}
            disabled={isStreaming || isRecording}
            icon={<Send className="h-3 w-3" />}
            className="!px-5 !py-0 h-10"
          />
        </div>
        <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
                <StatusDot status={isStreaming ? 'live' : 'idle'} />
                <span className="text-[9px] font-mono text-text-dim uppercase tracking-widest">
                    {isStreaming ? 'AI Online' : 'AI Latent'}
                </span>
            </div>
            <span className="text-[9px] font-mono text-text-dim uppercase">Term ID: SC-721</span>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
