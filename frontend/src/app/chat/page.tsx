'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { chat } from '@/lib/api';
import type { SSEEvent } from '@/lib/types';
import styles from './page.module.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  nodes?: string[];
  ts: Date;
}

const AGENT_NODES: Record<string, { label: string; color: string }> = {
  memory_retriever:     { label: 'Memory',      color: 'var(--purple)' },
  intent_router:        { label: 'Router',      color: 'var(--blue)' },
  opportunity_hunter:   { label: 'Opportunities', color: 'var(--teal)' },
  gap_detector:         { label: 'Gap Detector', color: 'var(--amber)' },
  roadmap_planner:      { label: 'Roadmap',     color: 'var(--green)' },
  resume_analyzer:      { label: 'Resume',      color: 'var(--blue)' },
  application_tracker:  { label: 'Tracker',     color: 'var(--teal)' },
  interview_coach:      { label: 'Interview',   color: 'var(--purple)' },
  responder:            { label: 'Responder',   color: 'var(--text-primary)' },
};

const STARTERS = [
  'Find me ML research internships in Bangalore',
  'What skills am I missing for NLP roles?',
  'Build me a 8-week learning roadmap for MLOps',
  'Help me prep for a Google ML intern interview',
];

export default function ChatPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [userName, setUserName] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [activeNodes, setActiveNodes] = useState<string[]>([]);
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const id = localStorage.getItem('mitra_user_id');
    const name = localStorage.getItem('mitra_user_name') ?? 'You';
    if (!id) { router.push('/'); return; }
    setUserId(id);
    setUserName(name);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  const appendToken = useCallback((token: string) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== 'assistant') return prev;
      return [...prev.slice(0, -1), { ...last, content: last.content + token }];
    });
  }, []);

  async function sendMessage(text: string) {
    if (!userId || !text.trim() || streaming) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text.trim(), ts: new Date() };
    const assistantMsg: Message = { id: crypto.randomUUID(), role: 'assistant', content: '', ts: new Date(), nodes: [] };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInput('');
    setStreaming(true);
    setActiveNodes([]);
    setCompletedNodes([]);

    const trackedNodes: string[] = [];

    abortRef.current = chat.stream(
      { user_id: userId, message: text.trim() },
      (evt: SSEEvent) => {
        if (evt.type === 'progress' && evt.node) {
          setActiveNodes([evt.node]);
          trackedNodes.push(evt.node);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== 'assistant') return prev;
            return [...prev.slice(0, -1), { ...last, nodes: [...(last.nodes ?? []), evt.node!] }];
          });
        }
        if (evt.type === 'token' && evt.chunk) {
          appendToken(evt.chunk);
          if (trackedNodes.length > 0) {
            setCompletedNodes(prev => {
              const last = trackedNodes[trackedNodes.length - 1];
              return prev.includes(last) ? prev : [...prev, last];
            });
            setActiveNodes([]);
          }
        }
        if (evt.type === 'done') {
          setCompletedNodes(trackedNodes);
          setActiveNodes([]);
          setStreaming(false);
        }
        if (evt.type === 'error') {
          appendToken(`\n\n[Error: ${evt.message}]`);
          setStreaming(false);
        }
      }
    );
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function stopStream() {
    abortRef.current?.();
    setStreaming(false);
    setActiveNodes([]);
  }

  if (!userId) return null;

  return (
    <div className={styles.layout}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sideHeader}>
          <span className="section-label">Agent Pipeline</span>
        </div>
        <div className={styles.pipeline}>
          {Object.entries(AGENT_NODES).map(([key, { label, color }]) => {
            const isActive = activeNodes.includes(key);
            const isDone = completedNodes.includes(key);
            return (
              <div
                key={key}
                className={`${styles.pipeNode} ${isActive ? styles.nodeActive : ''} ${isDone ? styles.nodeDone : ''}`}
                style={{ '--node-color': color } as React.CSSProperties}
              >
                <span className={styles.nodeDot} />
                <span className={styles.nodeLabel}>{label}</span>
                {isActive && <span className={styles.nodeSpinner}><span className="spinner" style={{ width: 10, height: 10 }} /></span>}
                {isDone && <span className={styles.nodeCheck}>✓</span>}
              </div>
            );
          })}
        </div>

        <div className={styles.sideSection}>
          <span className="section-label">Starters</span>
          <div className={styles.starters}>
            {STARTERS.map(s => (
              <button
                key={s}
                className={styles.starter}
                onClick={() => sendMessage(s)}
                disabled={streaming}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* Chat area */}
      <div className={styles.chatArea}>
        <div className={styles.chatHeader}>
          <div>
            <span className={styles.chatTitle}>Intelligence Terminal</span>
            <span className="badge badge-teal" style={{ marginLeft: 'var(--s3)', fontSize: 10 }}>SSE Stream</span>
          </div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {userName}
          </span>
        </div>

        <div className={styles.messages}>
          {messages.length === 0 && (
            <div className={styles.empty}>
              <span className={styles.emptyIcon}>⌬</span>
              <p>Ask Mitra anything about your ML/AI career path.</p>
              <p className={styles.emptyHint}>Use the starters on the left, or type your own question.</p>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`${styles.msg} ${msg.role === 'user' ? styles.msgUser : styles.msgAssistant}`}>
              <div className={styles.msgMeta}>
                <span className={styles.msgRole}>
                  {msg.role === 'user' ? userName : '⬡ mitra'}
                </span>
                <span className={styles.msgTime}>
                  {msg.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <div className={styles.msgBody}>
                <MessageContent content={msg.content} streaming={streaming && msg.role === 'assistant' && msg === messages[messages.length - 1]} />
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className={styles.inputArea}>
          {streaming && (
            <div className={styles.streamingBar}>
              <span className="spinner" style={{ width: 12, height: 12 }} />
              <span>
                {activeNodes[0] ? `Running ${AGENT_NODES[activeNodes[0]]?.label ?? activeNodes[0]}…` : 'Streaming response…'}
              </span>
              <button className="btn btn-ghost" onClick={stopStream} style={{ padding: '2px 8px', fontSize: 11 }}>
                Stop
              </button>
            </div>
          )}
          <div className={styles.inputRow}>
            <textarea
              ref={textareaRef}
              className={styles.chatInput}
              placeholder="Ask about internships, skill gaps, roadmap, interview prep…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={streaming}
            />
            <button
              className={`btn btn-primary ${styles.sendBtn}`}
              onClick={() => sendMessage(input)}
              disabled={streaming || !input.trim()}
            >
              ↑
            </button>
          </div>
          <p className={styles.inputHint}>Enter to send · Shift+Enter for newline</p>
        </div>
      </div>
    </div>
  );
}

function MessageContent({ content, streaming }: { content: string; streaming: boolean }) {
  const lines = content.split('\n');
  return (
    <div>
      {lines.map((line, i) => (
        <span key={i}>
          {line}
          {i < lines.length - 1 && <br />}
        </span>
      ))}
      {streaming && content === '' && <span className={styles.cursor} />}
      {streaming && content !== '' && <span className={styles.cursor} />}
    </div>
  );
}
