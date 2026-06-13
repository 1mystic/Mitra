'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { chat, profile, auth as authApi } from '@/lib/api';
import { getToken, getUserId, removeToken } from '@/lib/auth';
import type { SSEEvent } from '@/lib/types';
import Markdown from '@/lib/markdown';
import styles from './page.module.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  nodes?: string[];
  ts: Date;
}

const NODES: Record<string, string> = {
  memory_retriever:    'Recalling memory',
  intent_router:       'Routing intent',
  opportunity_hunter:  'Hunting opportunities',
  gap_detector:        'Detecting skill gaps',
  roadmap_planner:     'Building roadmap',
  resume_analyzer:     'Analysing resume',
  application_tracker: 'Checking applications',
  interview_coach:     'Interview coaching',
  responder:           'Composing response',
};

const ACTIONS = [
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
    ),
    title: 'Find internships',
    prompt: 'Find me ML research internships in Bangalore for 2025',
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
      </svg>
    ),
    title: 'Analyse my skill gaps',
    prompt: 'What skills am I missing for NLP engineering roles?',
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/>
      </svg>
    ),
    title: 'Build a learning roadmap',
    prompt: 'Build me an 8-week roadmap to become ready for MLOps internships',
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
      </svg>
    ),
    title: 'Prep for interview',
    prompt: 'Help me prepare for a Google ML intern interview — system design and ML fundamentals',
  },
];

export default function ChatPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [userName, setUserName] = useState('');
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [activeNode, setActiveNode] = useState('');
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const token = getToken();
    const id = getUserId();
    if (!token || !id) { router.replace('/auth'); return; }
    setUserId(id);

    // Resolve display name from /me, fall back to a cached value
    authApi.me()
      .then(u => setUserName(u.name ?? ''))
      .catch(() => {});

    // Onboarding is required — bounce to it if no profile exists yet
    profile.get(id)
      .then(() => setHasProfile(true))
      .catch(() => { setHasProfile(false); router.replace('/onboarding'); });
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const appendToken = useCallback((token: string) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== 'assistant') return prev;
      return [...prev.slice(0, -1), { ...last, content: last.content + token }];
    });
  }, []);

  function sendMessage(text: string) {
    if (!userId || !text.trim() || streaming) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text.trim(), ts: new Date() };
    const asstMsg: Message  = { id: crypto.randomUUID(), role: 'assistant', content: '', nodes: [], ts: new Date() };
    setMessages(prev => [...prev, userMsg, asstMsg]);
    setInput('');
    setStreaming(true);
    setActiveNode('');
    setCompletedNodes([]);

    const tracked: string[] = [];

    abortRef.current = chat.stream(
      { user_id: userId, message: text.trim() },
      (evt: SSEEvent) => {
        if (evt.type === 'progress' && evt.node) {
          setActiveNode(evt.node);
          tracked.push(evt.node);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== 'assistant') return prev;
            return [...prev.slice(0, -1), { ...last, nodes: [...(last.nodes ?? []), evt.node!] }];
          });
        }
        if (evt.type === 'token' && evt.chunk) {
          appendToken(evt.chunk);
          if (tracked.length > 0 && !completedNodes.includes(tracked[tracked.length - 1])) {
            setCompletedNodes([...tracked]);
            setActiveNode('');
          }
        }
        if (evt.type === 'done') {
          setCompletedNodes([...tracked]);
          setActiveNode('');
          setStreaming(false);
        }
        if (evt.type === 'error') {
          appendToken(`\n\n**Error:** ${evt.message}`);
          setStreaming(false);
        }
      }
    );
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  // Auto-resize textarea
  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  if (!userId) return null;

  const isEmpty = messages.length === 0;

  return (
    <div className={styles.layout}>
      {/* Left sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sideTop}>
          <button
            className={styles.newChat}
            onClick={() => { setMessages([]); setCompletedNodes([]); setActiveNode(''); }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            New chat
          </button>
        </div>

        {/* Resume prompt if no profile */}
        {hasProfile === false && (
          <a href="/profile" className={styles.resumePrompt}>
            <div className={styles.resumePromptIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                <polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
            </div>
            <div>
              <div className={styles.resumePromptTitle}>Upload your resume</div>
              <div className={styles.resumePromptSub}>Unlock gap analysis and personalised recommendations</div>
            </div>
          </a>
        )}

        {/* Pipeline status */}
        {(streaming || completedNodes.length > 0) && (
          <div className={styles.pipeSection}>
            <span className={styles.pipeLabel}>Agent pipeline</span>
            <div className={styles.pipe}>
              {Object.entries(NODES).map(([key, label]) => {
                const isActive = activeNode === key;
                const isDone   = completedNodes.includes(key);
                if (!isActive && !isDone) return null;
                return (
                  <div key={key} className={`${styles.pipeStep} ${isActive ? styles.pipeActive : styles.pipeDone}`}>
                    <span className={styles.pipeDot} />
                    <span className={styles.pipeStepLabel}>{label}</span>
                    {isActive && <span className="spinner spinner-sm spinner-accent" style={{ marginLeft: 'auto' }} />}
                    {isDone && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ marginLeft: 'auto', color: 'var(--green)' }}>
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className={styles.sideFooter}>
          <span className={styles.sideUser}>{userName}</span>
          <button
            className={styles.sideSignout}
            onClick={() => { removeToken(); router.push('/auth'); }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main chat */}
      <div className={styles.main}>
        {/* Empty state */}
        {isEmpty && (
          <div className={styles.emptyState}>
            <h2 className={styles.emptyTitle}>How can I help?</h2>
            <p className={styles.emptySub}>
              {hasProfile === false
                ? 'Upload your resume first for personalised skill gap analysis and recommendations.'
                : `Ask about internships, skills, roadmaps, or interview prep, ${userName.split(' ')[0]}.`}
            </p>

            {/* Action cards */}
            <div className={styles.actionCards}>
              {hasProfile === false && (
                <a href="/profile" className={`${styles.actionCard} ${styles.actionCardHighlight}`}>
                  <div className={styles.actionCardIcon}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="12" y1="18" x2="12" y2="12"/>
                      <line x1="9" y1="15" x2="15" y2="15"/>
                    </svg>
                  </div>
                  <div className={styles.actionCardText}>
                    <span className={styles.actionCardTitle}>Upload resume</span>
                    <span className={styles.actionCardSub}>Enable skill gap analysis</span>
                  </div>
                </a>
              )}
              {ACTIONS.map(a => (
                <button
                  key={a.title}
                  className={styles.actionCard}
                  onClick={() => sendMessage(a.prompt)}
                  disabled={streaming}
                >
                  <div className={styles.actionCardIcon}>{a.icon}</div>
                  <div className={styles.actionCardText}>
                    <span className={styles.actionCardTitle}>{a.title}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {!isEmpty && (
          <div className={styles.messages}>
            {messages.map((msg, idx) => (
              <div
                key={msg.id}
                className={`${styles.msg} ${msg.role === 'user' ? styles.msgUser : styles.msgAsst}`}
              >
                <div className={styles.msgAvatar}>
                  {msg.role === 'user'
                    ? <span className={styles.avatarUser}>{userName.charAt(0).toUpperCase()}</span>
                    : (
                      <span className={styles.avatarMitra}>
                        <svg width="14" height="14" viewBox="0 0 22 22" fill="none">
                          <polygon points="11,1 20.5,6 20.5,16 11,21 1.5,16 1.5,6" stroke="currentColor" strokeWidth="1.5" fill="rgba(255,255,255,0.06)" />
                        </svg>
                      </span>
                    )
                  }
                </div>
                <div className={styles.msgContent}>
                  {msg.role === 'user' ? (
                    <p className={styles.userText}>{msg.content}</p>
                  ) : (
                    <div className={styles.asstText}>
                      <Markdown content={msg.content} />
                      {streaming && idx === messages.length - 1 && msg.content === '' && (
                        <span className={styles.thinkDots}>
                          <span /><span /><span />
                        </span>
                      )}
                      {streaming && idx === messages.length - 1 && msg.content !== '' && (
                        <span className={styles.cursor} />
                      )}
                      {/* Inline resume prompt if gap_detector ran without profile */}
                      {!streaming && !hasProfile && msg.nodes?.includes('gap_detector') && (
                        <a href="/profile" className={styles.inlineResumeCard}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                          </svg>
                          Upload your resume for personalised gap analysis
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M5 12h14M12 5l7 7-7 7"/>
                          </svg>
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}

        {/* Input */}
        <div className={styles.inputWrap}>
          <div className={styles.inputBox}>
            {streaming && (
              <div className={styles.streamStatus}>
                <span className="spinner spinner-sm spinner-accent" />
                <span>{activeNode ? NODES[activeNode] ?? activeNode : 'Thinking'}…</span>
                <button
                  className={styles.stopBtn}
                  onClick={() => { abortRef.current?.(); setStreaming(false); setActiveNode(''); }}
                >
                  Stop
                </button>
              </div>
            )}
            <div className={styles.inputRow}>
              <textarea
                ref={textareaRef}
                className={styles.textarea}
                placeholder="Ask about internships, skill gaps, roadmaps, interview prep…"
                value={input}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={streaming}
              />
              <button
                className={styles.sendBtn}
                onClick={() => sendMessage(input)}
                disabled={streaming || !input.trim()}
                aria-label="Send"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 19V5M5 12l7-7 7 7"/>
                </svg>
              </button>
            </div>
            <p className={styles.inputHint}>Enter to send &nbsp;·&nbsp; Shift + Enter for new line</p>
          </div>
        </div>
      </div>
    </div>
  );
}
