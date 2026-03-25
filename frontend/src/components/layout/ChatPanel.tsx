import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Mic, Square } from 'lucide-react';
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
    <div className="flex flex-col h-full" style={{ background: 'var(--color-bg)' }}>
      {/* ── Message list ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {messages.map((msg, i) => {
          const isUser = msg.role === 'user';
          const isSystem = msg.role === 'system';
          const isVoice = isUser && msg.content === '[VOICE COMMAND RECORDED]';

          if (isSystem) {
            return (
              <div key={i} className="py-1">
                <p
                  className="text-[10px] font-mono uppercase tracking-wider text-center"
                  style={{ color: 'var(--color-text-dim)' }}
                >
                  — {msg.content} —
                </p>
              </div>
            );
          }

          return (
            <div
              key={i}
              className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}
            >
              {/* Label row */}
              <div className="flex items-center gap-2">
                {!isUser && (
                  <span
                    className="text-[9px] font-bold uppercase tracking-[0.14em] font-mono"
                    style={{ color: 'var(--color-accent)' }}
                  >
                    AI CO-PILOT
                  </span>
                )}
                <span
                  className="text-[9px] font-mono"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {formatTimestamp(msg.timestamp)}
                </span>
                {isUser && (
                  <span
                    className="text-[9px] font-bold uppercase tracking-[0.14em] font-mono"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    OPERATOR
                  </span>
                )}
              </div>

              {/* Message body */}
              {isUser ? (
                <p
                  className={`text-[11px] font-mono leading-relaxed max-w-[90%] px-3 py-2 ${isVoice ? 'italic' : ''}`}
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    color: isVoice ? 'var(--color-accent)' : 'var(--color-text)',
                  }}
                >
                  {msg.content}
                </p>
              ) : (
                <p
                  className="text-[11px] font-mono leading-relaxed max-w-[95%] px-3 py-2 whitespace-pre-wrap"
                  style={{
                    borderLeft: '2px solid var(--color-accent)',
                    paddingLeft: '12px',
                    color: 'var(--color-text)',
                    background: 'var(--color-accent-dim)',
                  }}
                >
                  {msg.content}
                </p>
              )}
            </div>
          );
        })}
        {isStreaming && (
          <div className="flex items-center gap-2">
            <Loader2 className="h-3 w-3 animate-spin" style={{ color: 'var(--color-accent)' }} />
            <span
              className="text-[10px] font-mono uppercase tracking-wider"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              PROCESSING...
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Input Area ── */}
      <div
        className="p-3 shrink-0"
        style={{ borderTop: '1px solid var(--color-border)' }}
      >
        <div className="flex gap-2">
          {/* Text input */}
          <div
            className="flex-1 flex items-center gap-2 px-3 py-2 transition-colors"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming || isRecording}
              placeholder={isRecording ? 'REC...' : 'ENTER COMMAND...'}
              className="w-full bg-transparent text-[10px] font-mono focus:outline-none uppercase disabled:opacity-40"
              style={{
                color: isRecording ? 'var(--color-danger)' : 'var(--color-text)',
              }}
            />
          </div>

          {/* Mic button */}
          <button
            onClick={toggleRecording}
            disabled={isStreaming}
            title="Voice command"
            className="h-9 w-9 flex items-center justify-center transition-colors disabled:opacity-40"
            style={{
              background: isRecording ? 'var(--color-danger)' : 'var(--color-surface)',
              border: `1px solid ${isRecording ? 'var(--color-danger)' : 'var(--color-border)'}`,
              color: isRecording ? '#fff' : 'var(--color-text-secondary)',
            }}
          >
            {isRecording ? <Square className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
          </button>

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={isStreaming || isRecording}
            className="flex items-center gap-2 px-4 h-9 text-[10px] font-bold uppercase tracking-wider font-mono transition-colors disabled:opacity-40"
            style={{
              background: 'var(--color-accent)',
              color: '#fff',
              border: '1px solid var(--color-accent)',
            }}
          >
            <span>SEND</span>
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
