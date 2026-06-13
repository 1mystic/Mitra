'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { chat, profile, auth as authApi, history as historyApi } from '@/lib/api';
import { getToken, getUserId, removeToken } from '@/lib/auth';
import type { SSEEvent, Opportunity, ConversationRead } from '@/lib/types';
import Markdown from '@/lib/markdown';
import styles from './page.module.css';

interface PipeStep {
  node: string;
  detail: string;
  done: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  nodes?: string[];
  opportunities?: Opportunity[];
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

// Opportunity card shown inline after agent finds results
function OppCard({ opp, onAction }: { opp: Opportunity; onAction: (prompt: string) => void }) {
  return (
    <div className={styles.oppCard}>
      <div className={styles.oppCardTop}>
        <span className={styles.oppCardType}>{opp.type}</span>
        {opp.stipend && <span className={styles.oppCardStipend}>{opp.stipend}</span>}
      </div>
      <div className={styles.oppCardTitle}>{opp.title}</div>
      <div className={styles.oppCardCompany}>{opp.company} · {opp.location}</div>
      {opp.required_skills?.length > 0 && (
        <div className={styles.oppCardSkills}>
          {opp.required_skills.slice(0, 4).map(s => (
            <span key={s} className={styles.oppCardSkill}>{s}</span>
          ))}
        </div>
      )}
      <div className={styles.oppCardActions}>
        <button
          className={styles.oppCardBtn}
          onClick={() => onAction(`Analyse my skill gaps for: ${opp.title} at ${opp.company}`)}
        >
          Check skill gaps
        </button>
        <button
          className={styles.oppCardBtn}
          onClick={() => onAction(`Prepare an interview plan for the role: ${opp.title} at ${opp.company}`)}
        >
          Interview prep
        </button>
        {opp.url && (
          <a
            href={opp.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`${styles.oppCardBtn} ${styles.oppCardBtnApply}`}
          >
            Apply ↗
          </a>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [userName, setUserName] = useState('');
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [activeNode, setActiveNode] = useState('');
  const [pipeSteps, setPipeSteps] = useState<PipeStep[]>([]);
  const [gapScore, setGapScore] = useState<number | null>(null);

  // Chat history sidebar
  const [conversations, setConversations] = useState<ConversationRead[]>([]);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const pendingOppsRef = useRef<Opportunity[]>([]);

  useEffect(() => {
    const token = getToken();
    const id = getUserId();
    if (!token || !id) { router.replace('/auth'); return; }
    setUserId(id);

    authApi.me()
      .then(u => setUserName(u.name ?? ''))
      .catch(() => {});

    profile.get(id)
      .then(() => setHasProfile(true))
      .catch(() => { setHasProfile(false); router.replace('/onboarding'); });

    loadConversations(id);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadConversations(uid: string) {
    setHistoryLoading(true);
    try {
      const list = await historyApi.list(uid);
      setConversations(list);
    } catch {
      // silently ignore — history is non-critical
    } finally {
      setHistoryLoading(false);
    }
  }

  async function startNewConversation() {
    setMessages([]);
    setPipeSteps([]);
    setActiveNode('');
    setGapScore(null);
    setCurrentConvId(null);
    pendingOppsRef.current = [];
  }

  async function loadConversation(convId: string) {
    try {
      const conv = await historyApi.get(convId);
      setCurrentConvId(convId);
      setMessages(
        conv.messages.map(m => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          ts: new Date(m.created_at),
        }))
      );
      setPipeSteps([]);
      setActiveNode('');
      setGapScore(null);
    } catch {
      // fall through
    }
  }

  async function deleteConversation(convId: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await historyApi.delete(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (currentConvId === convId) {
        setMessages([]);
        setCurrentConvId(null);
      }
    } catch {
      // ignore
    }
  }

  function startRename(conv: ConversationRead, e: React.MouseEvent) {
    e.stopPropagation();
    setRenamingId(conv.id);
    setRenameValue(conv.title ?? '');
  }

  async function commitRename(convId: string) {
    if (!renameValue.trim()) { setRenamingId(null); return; }
    try {
      const updated = await historyApi.rename(convId, renameValue.trim());
      setConversations(prev => prev.map(c => c.id === convId ? { ...c, title: updated.title } : c));
    } catch {
      // ignore
    }
    setRenamingId(null);
  }

  const appendToken = useCallback((token: string) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== 'assistant') return prev;
      return [...prev.slice(0, -1), { ...last, content: last.content + token }];
    });
  }, []);

  const attachOpportunities = useCallback((opps: Opportunity[]) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== 'assistant') return prev;
      return [...prev.slice(0, -1), { ...last, opportunities: opps }];
    });
  }, []);

  async function ensureConversation(uid: string, firstMessage: string): Promise<string> {
    if (currentConvId) return currentConvId;
    const title = firstMessage.slice(0, 60);
    const conv = await historyApi.create(uid, title);
    setCurrentConvId(conv.id);
    setConversations(prev => [conv, ...prev]);
    return conv.id;
  }

  async function sendMessage(text: string) {
    if (!userId || !text.trim() || streaming) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text.trim(), ts: new Date() };
    const asstMsg: Message  = { id: crypto.randomUUID(), role: 'assistant', content: '', nodes: [], ts: new Date() };
    setMessages(prev => [...prev, userMsg, asstMsg]);
    setInput('');
    setStreaming(true);
    setActiveNode('');
    pendingOppsRef.current = [];

    let finalText = '';

    // Ensure a conversation record exists
    const convId = await ensureConversation(userId, text.trim());

    // Persist user message
    historyApi.addMessage(convId, 'user', text.trim()).catch(() => {});

    // Reset pipeline
    setPipeSteps([]);
    setGapScore(null);

    abortRef.current = chat.stream(
      { user_id: userId, message: text.trim() },
      async (evt: SSEEvent) => {
        if (evt.type === 'progress' && evt.node) {
          const node = evt.node;
          const detail = evt.detail || NODES[node] || node;
          setActiveNode(node);

          // Add step to pipeline list (or update existing if duplicate node)
          setPipeSteps(prev => {
            const existing = prev.findIndex(s => s.node === node);
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = { node, detail, done: false };
              return updated;
            }
            // Mark previous active step as done
            const updated = prev.map(s => ({ ...s, done: true }));
            return [...updated, { node, detail, done: false }];
          });

          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (!last || last.role !== 'assistant') return prev;
            return [...prev.slice(0, -1), { ...last, nodes: [...(last.nodes ?? []), node] }];
          });
        }

        if (evt.type === 'data') {
          if (evt.key === 'opportunities' && Array.isArray(evt.value)) {
            pendingOppsRef.current = evt.value as Opportunity[];
          }
          if (evt.key === 'gap_score' && typeof evt.value === 'number') {
            setGapScore(evt.value);
          }
        }

        if (evt.type === 'token' && evt.chunk) {
          finalText += evt.chunk;
          appendToken(evt.chunk);
          // Mark active step done when tokens start flowing
          setPipeSteps(prev => prev.map(s => ({ ...s, done: true })));
          setActiveNode('');
        }

        if (evt.type === 'done') {
          setPipeSteps(prev => prev.map(s => ({ ...s, done: true })));
          setActiveNode('');
          setStreaming(false);

          if (pendingOppsRef.current.length > 0) {
            attachOpportunities(pendingOppsRef.current);
          }

          if (finalText.trim()) {
            historyApi.addMessage(convId, 'assistant', finalText.trim()).catch(() => {});
          }

          if (userId) loadConversations(userId);
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
            onClick={startNewConversation}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            New chat
          </button>
        </div>

        {/* Conversation history list */}
        <div className={styles.historyList}>
          {historyLoading && (
            <div className={styles.historyLoading}>
              <span className="spinner spinner-sm" />
            </div>
          )}
          {!historyLoading && conversations.length === 0 && (
            <p className={styles.historyEmpty}>No conversations yet</p>
          )}
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`${styles.historyItem} ${currentConvId === conv.id ? styles.historyItemActive : ''}`}
              onClick={() => loadConversation(conv.id)}
            >
              {renamingId === conv.id ? (
                <input
                  className={styles.historyRenameInput}
                  value={renameValue}
                  autoFocus
                  onChange={e => setRenameValue(e.target.value)}
                  onBlur={() => commitRename(conv.id)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') commitRename(conv.id);
                    if (e.key === 'Escape') setRenamingId(null);
                  }}
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <span className={styles.historyTitle}>{conv.title || 'Untitled chat'}</span>
              )}
              <div className={styles.historyActions}>
                <button
                  className={styles.historyActionBtn}
                  title="Rename"
                  onClick={e => startRename(conv, e)}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button
                  className={styles.historyActionBtn}
                  title="Delete"
                  onClick={e => deleteConversation(conv.id, e)}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                    <path d="M10 11v6M14 11v6"/>
                  </svg>
                </button>
              </div>
            </div>
          ))}
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
        {(streaming || pipeSteps.length > 0) && (
          <div className={styles.pipeSection}>
            <span className={styles.pipeLabel}>Agent pipeline</span>
            {gapScore !== null && (
              <div className={styles.pipeScoreBadge}>
                <span className={styles.pipeScoreNum}>{gapScore}%</span>
                <span className={styles.pipeScoreLabel}>skill match</span>
              </div>
            )}
            <div className={styles.pipe}>
              {pipeSteps.filter(s => s.node !== 'memory_writer').map((step) => (
                <div key={step.node} className={`${styles.pipeStep} ${!step.done ? styles.pipeActive : styles.pipeDone}`}>
                  <span className={styles.pipeDot} />
                  <span className={styles.pipeStepLabel}>{step.detail || NODES[step.node] || step.node}</span>
                  {!step.done && <span className="spinner spinner-sm spinner-accent" style={{ marginLeft: 'auto' }} />}
                  {step.done && (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ marginLeft: 'auto', color: 'var(--green)' }}>
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  )}
                </div>
              ))}
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

                      {/* Opportunity cards */}
                      {msg.opportunities && msg.opportunities.length > 0 && (
                        <div className={styles.oppCards}>
                          {msg.opportunities.map(opp => (
                            <OppCard
                              key={opp.id}
                              opp={opp}
                              onAction={(prompt) => sendMessage(prompt)}
                            />
                          ))}
                        </div>
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
                <span>
                  {pipeSteps.find(s => !s.done)?.detail
                    || (activeNode ? NODES[activeNode] ?? activeNode : 'Thinking')}…
                </span>
                <button
                  className={styles.stopBtn}
                  onClick={() => { abortRef.current?.(); setStreaming(false); setActiveNode(''); setPipeSteps(prev => prev.map(s => ({...s, done: true}))); }}
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
