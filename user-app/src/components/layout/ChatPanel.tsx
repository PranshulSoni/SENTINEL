import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Mic, Square } from 'lucide-react';
import { useChatStore, useIncidentStore } from '../../store';
import { api } from '../../services/api';

const formatTimestamp = (iso: string): string => {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
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

  useEffect(() => {
    const incidentId = currentIncident?.id || 'general';
    api
      .getChatHistory(incidentId)
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
  }, [currentIncident?.id, addMessage]);

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
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: mediaRecorder.mimeType || 'audio/webm',
        });
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = () => {
          const base64data = (reader.result as string).split(',')[1];
          handleVoiceSend(base64data, audioBlob.type || 'audio/webm');
        };
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access denied', err);
    }
  };

  const handleVoiceSend = async (base64Audio: string, mimeType: string) => {
    if (isStreaming) return;

    addMessage({
      role: 'user',
      content: '[VOICE COMMAND RECORDED]',
      timestamp: new Date().toISOString(),
    });
    setStreaming(true);

    try {
      const response = await api.sendChat('[voice]', currentIncident?.id, {
        audio_base64: base64Audio,
        audio_mime_type: mimeType,
      });

      addMessage({
        role: 'assistant',
        content: response.content || 'No response from backend.',
        timestamp: new Date().toISOString(),
      });
    } catch {
      addMessage({
        role: 'assistant',
        content: 'ERROR: Voice processing failed.',
        timestamp: new Date().toISOString(),
      });
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
    <div className="flex flex-col h-full bg-transparent">
      <div className="flex-1 overflow-y-auto px-6 py-6 pb-28 space-y-6">
        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500">
              <span className="uppercase tracking-wider text-gray-800">
                {msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'Copilot' : 'System'}
              </span>
              <span>{formatTimestamp(msg.timestamp)}</span>
            </div>

            <div
              className={`px-4 py-3 rounded-[1.25rem] max-w-[85%] text-sm font-medium leading-relaxed shadow-sm ${
                msg.role === 'system'
                  ? 'w-full bg-gray-50 text-gray-500 italic border border-gray-100 text-center rounded-2xl'
                  : msg.role === 'user'
                    ? 'bg-[#FF5A5F] text-white rounded-tr-sm shadow-md shadow-[#FF5A5F]/20'
                    : 'bg-white text-[#1A1A1A] border border-gray-100 rounded-tl-sm shadow-sm'
              }`}
            >
              <p className={`${msg.content === '[VOICE COMMAND RECORDED]' ? 'italic font-bold' : ''} whitespace-pre-wrap`}>
                {msg.content}
              </p>
            </div>
          </div>
        ))}

        {isStreaming && (
          <div className="flex items-center gap-2 text-xs font-bold text-gray-400 pl-2">
            <Loader2 className="w-4 h-4 animate-spin text-[#A3B18A]" />
            <span className="animate-pulse">Analyzing context...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="absolute bottom-0 w-full p-6 pt-2 pb-safe bg-gradient-to-t from-[#FAFAFA] via-[#FAFAFA]/95 to-transparent">
        <div className="flex gap-2.5 max-w-md mx-auto relative">
          <div className="flex-1 relative flex items-center bg-white rounded-full border border-gray-200 shadow-sm px-4 focus-within:border-[#FF5A5F] focus-within:ring-1 focus-within:ring-[#FF5A5F] transition-all">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming || isRecording}
              placeholder={isRecording ? 'Listening...' : 'Message Copilot...'}
              className={`w-full bg-transparent py-3.5 text-xs focus:outline-none disabled:opacity-50 ${isRecording ? 'text-[#FF5A5F] placeholder:text-[#FF5A5F] animate-pulse font-bold' : 'text-[#1A1A1A] placeholder:text-gray-400 font-bold'}`}
            />
          </div>
          <button
            onClick={toggleRecording}
            disabled={isStreaming}
            className={`w-[48px] h-[48px] shrink-0 rounded-full disabled:opacity-50 transition-all flex items-center justify-center shadow-lg ${isRecording ? 'bg-[#FF5A5F] text-white shadow-[#FF5A5F]/30 hover:scale-105' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}
            title="Voice Command"
          >
            {isRecording ? <Square className="w-5 h-5 fill-current" /> : <Mic className="w-5 h-5" />}
          </button>
          <button
            onClick={handleSend}
            disabled={isStreaming || isRecording || !input.trim()}
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
