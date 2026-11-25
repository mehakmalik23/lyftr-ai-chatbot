import React, { useState, useEffect, useRef } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

function generateSessionId() {
  return 's-' + Math.random().toString(36).substring(2, 10);
}

export default function App() {
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);
  const [health, setHealth] = useState(null);
  const [simulateHeader, setSimulateHeader] = useState('');
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then(r => r.json())
      .then(data => setHealth(data))
      .catch(() => setHealth({ status: 'unreachable', keys_configured: 0, cache_enabled: false }));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, errorBanner]);

  const sendMessage = async (e, overrideText = null, overrideSession = null) => {
    if (e) e.preventDefault();
    const textToSend = overrideText !== null ? overrideText : input;
    const activeSession = overrideSession || sessionId;

    if (overrideText === null) {
      setInput('');
    }
    setErrorBanner(null);
    setLoading(true);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (simulateHeader.trim()) {
        headers['X-Simulate-Failure'] = simulateHeader.trim();
      }

      const payload = {
        session_id: activeSession,
        message: textToSend
      };
      if (systemPrompt.trim()) {
        payload.system_prompt = systemPrompt.trim();
      }

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        const detail = typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data.detail || 'Request failed');
        setErrorBanner(`HTTP ${res.status}: ${detail}`);
      } else {
        setMessages(prev => [
          ...prev,
          { role: 'user', content: textToSend.trim() },
          { role: 'assistant', content: data.reply, metadata: data.metadata }
        ]);
      }
    } catch (err) {
      setErrorBanner(`Network Error: Unable to reach backend at ${API_BASE}`);
    } finally {
      setLoading(false);
    }
  };

  const handleNewSession = () => {
    setSessionId(generateSessionId());
    setMessages([]);
    setErrorBanner(null);
  };

  const triggerInstantCacheDemo = () => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    const samplePrompt = lastUserMsg ? lastUserMsg.content : 'What is the capital of France?';
    const freshSession = generateSessionId();
    setSessionId(freshSession);
    setMessages([]);
    setSimulateHeader('');
    sendMessage(null, samplePrompt, freshSession);
  };

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', padding: '20px', display: 'flex', flexDirection: 'column', minHeight: '95vh' }}>
      {/* Header & Telemetry Bar */}
      <header style={{ background: '#1e293b', padding: '16px 20px', borderRadius: '12px', marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', border: '1px solid #334155' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc' }}>
            Lyftr AI Gateway <span style={{ fontSize: '0.8rem', background: '#3b82f6', padding: '2px 8px', borderRadius: '99px', marginLeft: '8px' }}>LiteLLM + SQLite</span>
          </h1>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '4px' }}>
            Active Session: <code style={{ color: '#38bdf8' }}>{sessionId}</code>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {health && (
            <span style={{ fontSize: '0.78rem', padding: '4px 10px', borderRadius: '6px', background: health.status === 'ok' ? '#064e3b' : '#7f1d1d', color: health.status === 'ok' ? '#6ee7b7' : '#fca5a5', border: '1px solid rgba(255,255,255,0.1)' }}>
              ● {health.status === 'ok' ? `Healthy (${health.keys_configured} Keys | Cache ON)` : 'Backend Offline'}
            </span>
          )}
          <button onClick={handleNewSession} style={{ background: '#334155', color: '#f8fafc', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem' }}>
            + New Session
          </button>
          <button onClick={triggerInstantCacheDemo} title="Starts a new session and repeats the last first-message to prove cross-session LLM_CACHE" style={{ background: '#059669', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}>
            ⚡ Test Cross-Session Cache Hit
          </button>
        </div>
      </header>

      {/* Control Panel: System Prompt + Chaos Failover Hook */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div style={{ background: '#1e293b', padding: '12px 16px', borderRadius: '10px', border: '1px solid #334155' }}>
          <label style={{ display: 'block', fontSize: '0.75rem', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '6px', fontWeight: 600 }}>
            Session System Prompt (Optional)
          </label>
          <input
            data-testid="system-prompt-input"
            type="text"
            value={systemPrompt}
            onChange={e => setSystemPrompt(e.target.value)}
            placeholder="You are a helpful, concise AI assistant."
            style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: '6px', border: '1px solid #475569', background: '#0f172a', color: '#f8fafc', fontSize: '0.85rem' }}
          />
        </div>

        <div style={{ background: '#1e293b', padding: '12px 16px', borderRadius: '10px', border: '1px solid #334155' }}>
          <label style={{ display: 'block', fontSize: '0.75rem', textTransform: 'uppercase', color: '#f59e0b', marginBottom: '6px', fontWeight: 600 }}>
            Chaos Failover Hook (X-Simulate-Failure Header)
          </label>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {[
              { label: 'Normal (None)', val: '' },
              { label: 'Fail key_1 (429)', val: 'key_1=429' },
              { label: 'Fail key_1 (500)', val: 'key_1=500' },
              { label: 'Fail All (*=429 → 503)', val: '*=429' }
            ].map(preset => (
              <button
                key={preset.label}
                type="button"
                onClick={() => setSimulateHeader(preset.val)}
                style={{
                  padding: '6px 10px',
                  fontSize: '0.76rem',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  border: simulateHeader === preset.val ? '1px solid #f59e0b' : '1px solid #475569',
                  background: simulateHeader === preset.val ? '#78350f' : '#0f172a',
                  color: simulateHeader === preset.val ? '#fde68a' : '#cbd5e1'
                }}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chat Messages Area */}
      <div style={{ flex: 1, background: '#1e293b', borderRadius: '12px', padding: '20px', overflowY: 'auto', marginBottom: '16px', border: '1px solid #334155', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.length === 0 && !errorBanner && (
          <div style={{ textAlign: 'center', color: '#64748b', margin: 'auto' }}>
            <p style={{ fontSize: '1rem', marginBottom: '6px' }}>Send a message to start chatting.</p>
            <p style={{ fontSize: '0.82rem' }}>Try sending the same prompt twice across new sessions to inspect <code>LLM_CACHE</code> vs <code>LIVE_INFERENCE</code>, or toggle a Chaos Failover preset above.</p>
          </div>
        )}

        {messages.map((m, i) => (
          m.role === 'user' ? (
            <div key={i} style={{ alignSelf: 'flex-end', background: '#2563eb', color: '#ffffff', padding: '10px 14px', borderRadius: '12px 12px 2px 12px', maxWidth: '75%', lineHeight: 1.5 }}>
              {m.content}
            </div>
          ) : (
            <div
              key={i}
              data-testid="assistant-message"
              style={{ alignSelf: 'flex-start', background: '#0f172a', border: '1px solid #334155', padding: '14px 16px', borderRadius: '12px 12px 12px 2px', maxWidth: '82%' }}
            >
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.55, marginBottom: '12px', color: '#f1f5f9' }}>
                {m.content}
              </div>

              {/* Mandatory Metadata Bar */}
              {m.metadata && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', paddingTop: '10px', borderTop: '1px solid #1e293b', fontSize: '0.75rem', alignItems: 'center' }}>
                  <span
                    data-testid="meta-source"
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontWeight: 700,
                      background: m.metadata.resolution_source === 'LLM_CACHE' ? '#065f46' : '#1e3a8a',
                      color: m.metadata.resolution_source === 'LLM_CACHE' ? '#6ee7b7' : '#93c5fd'
                    }}
                  >
                    {m.metadata.resolution_source}
                  </span>

                  <span style={{ background: '#1e293b', padding: '3px 8px', borderRadius: '4px', color: '#cbd5e1' }}>
                    Model: <strong data-testid="meta-model">{m.metadata.model}</strong>
                  </span>

                  <span style={{ background: '#1e293b', padding: '3px 8px', borderRadius: '4px', color: '#cbd5e1' }}>
                    Latency: <strong data-testid="meta-latency">{m.metadata.latency_ms} ms</strong>
                  </span>

                  <span style={{ background: '#1e293b', padding: '3px 8px', borderRadius: '4px', color: '#cbd5e1' }}>
                    In Tokens: <strong data-testid="meta-input-tokens">{m.metadata.input_tokens}</strong>
                  </span>

                  <span style={{ background: '#1e293b', padding: '3px 8px', borderRadius: '4px', color: '#cbd5e1' }}>
                    Out Tokens: <strong data-testid="meta-output-tokens">{m.metadata.output_tokens}</strong>
                  </span>

                  <span style={{ background: '#1e293b', padding: '3px 8px', borderRadius: '4px', color: '#94a3b8' }}>
                    Key: <code>{m.metadata.key_id ?? 'null'}</code>
                  </span>

                  {m.metadata.fallback_attempts > 0 && (
                    <span style={{ background: '#78350f', color: '#fde68a', padding: '3px 8px', borderRadius: '4px', fontWeight: 600 }}>
                      ⚡ Failovers: {m.metadata.fallback_attempts}
                    </span>
                  )}
                </div>
              )}
            </div>
          )
        ))}

        {errorBanner && (
          <div role="alert" style={{ background: '#7f1d1d', border: '1px solid #ef4444', color: '#fecaca', padding: '12px 16px', borderRadius: '8px', fontSize: '0.88rem' }}>
            <strong>Request Error:</strong> {errorBanner}
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Chat Input Form */}
      <form onSubmit={sendMessage} style={{ display: 'flex', gap: '10px' }}>
        <input
          data-testid="chat-input"
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Type your message... (Press Enter to send)"
          style={{ flex: 1, padding: '14px 16px', borderRadius: '10px', border: '1px solid #334155', background: '#1e293b', color: '#f8fafc', fontSize: '0.95rem' }}
        />
        <button
          data-testid="send-button"
          type="submit"
          disabled={loading}
          style={{ padding: '0 24px', borderRadius: '10px', border: 'none', background: '#2563eb', color: '#ffffff', fontWeight: 600, fontSize: '0.95rem', cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.7 : 1 }}
        >
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
    </div>
  );
}
