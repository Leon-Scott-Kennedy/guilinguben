'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  AnalyzeResponse,
  analyzeQuestionStream,
  Citation,
  clearAuth,
  fetchSessionHistory,
  fetchSessionList,
  getStoredUsername,
  getToken,
  HistoryMessage,
  login,
  SessionSummary,
  setUnauthorizedHandler,
  StreamCallbacks,
  StreamInterruptedError,
} from '@/lib/api';

// 动态导入 PdfViewer 并禁用 SSR
const PdfViewer = dynamic(() => import('@/components/PdfViewer'), {
  ssr: false,
  loading: () => <div className="p-4 text-center text-zinc-500">正在加载 PDF 阅读器...</div>
});

// 聊天消息结构：用户与 AI 消息统一建模，AI 消息附带引用与警告；
// streaming/statusText 为 B5 流式专用：打字机渲染与阶段状态提示
interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  citations?: Citation[];
  warnings?: string[];
  isError?: boolean;
  streaming?: boolean;
  statusText?: string;
}

// 会话 ID 的 localStorage 键名：跨刷新保持同一会话，多轮对话历史不丢失
const SESSION_STORAGE_KEY = 'guilinguben_session_id';

// 历史分页每页条数（与后端 limit 上限 200 无关，前端每页 50 条，16.32）
const HISTORY_PAGE_SIZE = 50;

// 历史记录 → 聊天消息：一条记录拆成 user+ai 两条消息（与后端落库结构对应）
function historyToMessages(history: HistoryMessage[]): ChatMessage[] {
  const loaded: ChatMessage[] = [];
  for (const h of history) {
    loaded.push({ role: 'user', content: h.question });
    loaded.push({
      role: 'ai',
      content: h.answer,
      citations: h.citations,
      isError: h.answer.startsWith('分析失败:'),
    });
  }
  return loaded;
}

// 侧栏会话时间显示：近一周内用相对时间，更早显示日期
function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} 天前`;
  return new Date(iso).toLocaleDateString('zh-CN');
}

export default function Home() {
  // 登录态（D 轮 16.40 JWT）：{ username } 非空即已登录（token 由 api.ts 存 localStorage 自动携带）
  const [auth, setAuth] = useState<{ username: string } | null>(null);
  const [mounted, setMounted] = useState(false);
  // 登录表单状态
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [strictMode, setStrictMode] = useState(true);
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  // 历史分页状态（16.32）：historyOffset 为已加载条数（下次请求的 offset），historyHasMore 表示是否还有更早记录
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  // 侧栏会话列表（DeepSeek 风格）：全部历史会话摘要，最近活跃在前
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  
  // PDF 预览状态
  const [showPdf, setShowPdf] = useState(false);
  const [targetPage, setTargetPage] = useState(1);
  // 跨页条文结束页（C 轮 16.36）：与 targetPage 构成 PDF 渲染区间，null 表示单页
  const [targetEndPage, setTargetEndPage] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  // 加载更早页时的滚动锚点（prepend 前的高度与视口位置，用于恢复视口不被推离）
  const anchorRef = useRef<{ height: number; top: number } | null>(null);

  // 0. 恢复登录态（token + username 从 localStorage 读，刷新保持登录）；mounted 避免 SSR/客户端首帧不一致
  useEffect(() => {
    setMounted(true);
    const token = getToken();
    const username = getStoredUsername();
    if (token && username) {
      setAuth({ username });
    }
  }, []);

  // 0.1 注册 401 全局回调：任意业务接口返回 401（token 失效/过期）时清登录态回登录页
  useEffect(() => {
    setUnauthorizedHandler(() => setAuth(null));
  }, []);

  // 1. 浏览器环境下从 localStorage 读取或创建 sessionId（SSR 阶段不执行，避免 window 未定义）
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let id = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!id) {
      id = 'web-session-' + Date.now();
      localStorage.setItem(SESSION_STORAGE_KEY, id);
    }
    setSessionId(id);
  }, []);

  // 2. 加载侧栏会话列表（需登录态）；后端未启动时静默降级为空列表（A 轮搁置项确认：不阻塞提问）
  useEffect(() => {
    if (!auth) return;
    fetchSessionList()
      .then(setSessions)
      .catch(() => console.warn('[前端] 会话列表加载失败，侧栏显示空列表'));
  }, [auth]);
  useEffect(() => {
    if (!auth || !sessionId) return; // 未登录不拉历史（否则必然 401）；登录后 sessionId 就绪才拉取
    fetchSessionHistory(sessionId, HISTORY_PAGE_SIZE, 0)
      .then((page) => {
        setMessages(historyToMessages(page.messages));
        setHistoryOffset(page.messages.length);
        setHistoryHasMore(page.hasMore);
        setHistoryLoaded(true);
      })
      .catch(() => {
        // 历史加载失败（如后端未启动）不阻塞提问，静默降级为空会话
        setHistoryLoaded(true);
      });
  }, [sessionId, auth]);

  // 3. 新消息到达后自动滚动到底部；若本次是 prepend 更早页（存在锚点），则恢复视口位置保持阅读位置不变
  useEffect(() => {
    const main = mainRef.current;
    if (!main) return;
    if (anchorRef.current) {
      main.scrollTop = anchorRef.current.top + (main.scrollHeight - anchorRef.current.height);
      anchorRef.current = null;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // 刷新侧栏会话列表（新会话首次提问落库后出现在列表顶部；静默降级不阻塞提问）
  const refreshSessions = () => {
    fetchSessionList().then(setSessions).catch(() => {});
  };

  const handleAnalyze = async () => {
    if (!question.trim() || !sessionId) return;

    const userMessage: ChatMessage = { role: 'user', content: question };
    // 流式 AI 消息：先占位，随 delta 事件逐 token 填充（打字机渲染）
    const aiMessage: ChatMessage = { role: 'ai', content: '', streaming: true, statusText: '分析中...' };
    setMessages((prev) => [...prev, userMessage, aiMessage]);
    const asked = userMessage.content;
    setQuestion('');
    setLoading(true);

    // 更新当前流式 AI 消息（从尾部找最后一条 streaming 消息）
    const updateLastAi = (updater: (m: ChatMessage) => ChatMessage) => {
      setMessages((prev) => {
        const copy = [...prev];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].role === 'ai' && copy[i].streaming) {
            copy[i] = updater(copy[i]);
            break;
          }
        }
        return copy;
      });
    };

    // record-level 兜底恢复：断连且服务端缓冲不可用时，重载会话历史（最新一页）补齐
    const recoverFromHistory = () => {
      updateLastAi((m) => ({ ...m, statusText: '连接中断，正在从会话历史恢复...' }));
      fetchSessionHistory(sessionId, HISTORY_PAGE_SIZE, 0)
        .then((page) => {
          setMessages(historyToMessages(page.messages));
          setHistoryOffset(page.messages.length);
          setHistoryHasMore(page.hasMore);
          setLoading(false);
          refreshSessions(); // 落库后刷新侧栏（新会话出现/更新时间更新）
        })
        .catch(() => {
          updateLastAi((m) => ({
            ...m,
            content: '连接中断且历史恢复失败，请稍后刷新重试',
            isError: true,
            streaming: false,
            statusText: '',
          }));
          setLoading(false);
        });
    };

    const callbacks: StreamCallbacks = {
      onStatus: (stage: string, statusMsg: string) => {
        updateLastAi((m) => {
          if (stage === 'tool_calling') {
            // 工具决策轮：清空已积累增量（模型决策轮输出内容的罕见场景，与后端丢弃语义一致）
            return { ...m, content: '', statusText: statusMsg };
          }
          // 其他阶段（生成中）：仅当尚无正文时显示提示
          return m.content ? m : { ...m, statusText: statusMsg };
        });
      },
      onDelta: (text: string) => {
        updateLastAi((m) => ({ ...m, content: m.content + text, statusText: '' }));
      },
      onDone: (result: AnalyzeResponse) => {
        // 用 done 的完整结果覆盖（保证与落库内容一致），渲染证据卡与警告
        updateLastAi((m) => ({
          ...m,
          content: result.answer,
          citations: result.citations,
          warnings: result.warnings,
          streaming: false,
          statusText: '',
        }));
        setLoading(false);
        refreshSessions(); // 落库后刷新侧栏会话列表
      },
      onError: (message: string, recoverable: boolean) => {
        if (recoverable) {
          recoverFromHistory();
        } else {
          updateLastAi((m) => ({ ...m, content: message, isError: true, streaming: false, statusText: '' }));
          setLoading(false);
          refreshSessions(); // 失败记录也会落库，同步刷新侧栏
        }
      },
    };

    const streamRequest = (lastEventId?: number) =>
      analyzeQuestionStream(
        { sessionId, question: asked, strictMode, topK: 3 },
        callbacks,
        lastEventId
      );

    try {
      await streamRequest();
    } catch (err) {
      if (err instanceof StreamInterruptedError && err.lastEventId > 0) {
        // Layer 2 短断连恢复：带 Last-Event-ID 重连，从 Java 端缓冲续发剩余事件
        updateLastAi((m) => ({ ...m, statusText: '连接中断，正在断点续传...' }));
        console.warn('[前端] 流式中断，尝试断点续传: lastEventId=', err.lastEventId);
        try {
          await streamRequest(err.lastEventId);
        } catch {
          recoverFromHistory();
        }
      } else {
        const message = err instanceof Error ? err.message : '请求失败，请检查后端服务是否运行';
        updateLastAi((m) => ({ ...m, content: message, isError: true, streaming: false, statusText: '' }));
        setLoading(false);
      }
    }
  };

  // 新建会话（DeepSeek 风格左上角按钮）：重新生成 sessionId 并清空当前视图；旧会话数据保留在库中（侧栏可见）
  const handleNewSession = () => {
    if (loading) return; // 生成中禁止新建，避免流式回调串会话
    const id = 'web-session-' + Date.now();
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    setSessionId(id);
    setMessages([]);
    setHistoryOffset(0);
    setHistoryHasMore(false);
    setHistoryLoaded(true); // 新会话无历史，直接显示欢迎语（sessionId effect 会再拉一次空历史）
  };

  // 切换历史会话：更新 localStorage 与 sessionId，历史加载 effect 自动拉取该会话记录
  const handleSelectSession = (id: string) => {
    if (loading || id === sessionId) return;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    setSessionId(id);
    setMessages([]);
    setHistoryOffset(0);
    setHistoryHasMore(false);
    setHistoryLoaded(false); // 显示“正在加载会话历史...”提示
  };

  // 加载更早一页历史（16.32）：后端按 offset 返回更早页（页内升序），prepend 到现有列表头部
  const loadEarlier = async () => {
    if (loadingEarlier || !historyHasMore || !sessionId) return;
    setLoadingEarlier(true);
    try {
      // 记录 prepend 前滚动容器的高度与视口位置，prepend 后由自动滚动 effect 恢复（滚动锚定）
      const main = mainRef.current;
      if (main) anchorRef.current = { height: main.scrollHeight, top: main.scrollTop };
      const page = await fetchSessionHistory(sessionId, HISTORY_PAGE_SIZE, historyOffset);
      setMessages((prev) => [...historyToMessages(page.messages), ...prev]);
      setHistoryOffset((prev) => prev + page.messages.length);
      setHistoryHasMore(page.hasMore);
    } catch {
      // 加载失败静默降级：保留已有消息，不弹错（可重试）
      console.error('[前端] 加载更早历史失败: offset=', historyOffset);
    } finally {
      setLoadingEarlier(false);
    }
  };

  const handleCitationClick = (cite: Citation) => {
    // 优先用 C 轮页码字段跳转（检索证据与方剂库证据均带 pdf_page_start）；
    // 旧历史数据无此字段时回退从 document_id 解析（格式 "guilinguben.pdf:p73:c0"）
    if (cite.pdf_page_start) {
      setTargetPage(cite.pdf_page_start);
      setTargetEndPage(cite.pdf_page_end ?? null);
      setShowPdf(true);
      return;
    }
    if (cite.document_id.startsWith('formula_db:')) return;
    const match = cite.document_id.match(/p(\d+)/);
    if (match) {
      setTargetPage(parseInt(match[1]));
      setTargetEndPage(null);
      setShowPdf(true);
    }
  };

  // 登录提交（D 轮 16.40）：成功后 token/username 已入 localStorage，置 auth 渲染主界面
  const handleLogin = async () => {
    if (!loginUsername.trim() || !loginPassword || loggingIn) return;
    setLoggingIn(true);
    setLoginError('');
    try {
      const data = await login(loginUsername.trim(), loginPassword);
      setAuth({ username: data.username });
      setLoginPassword('');
    } catch (e) {
      setLoginError(e instanceof Error ? e.message : '登录失败，请稍后重试');
    } finally {
      setLoggingIn(false);
    }
  };

  // 登出：清本地登录态回登录页；会话列表保留在库中，下次登录仍可见；登录表单一并清空
  const handleLogout = () => {
    clearAuth();
    setAuth(null);
    setMessages([]);
    setSessions([]);
    setLoginUsername('');
    setLoginPassword('');
  };

  // 未挂载（SSR/首帧）与未登录均不渲染主界面；登录卡片为全屏居中表单（D 轮 16.40）
  if (!mounted) return null;
  if (!auth) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-lg dark:bg-zinc-900">
          <h1 className="mb-1 text-center text-2xl font-bold text-zinc-900 dark:text-zinc-50">桂林古本智能辅助诊疗</h1>
          <p className="mb-6 text-center text-sm text-zinc-500">登录后开始使用</p>
          {loginError && (
            <div className="mb-3 rounded-md bg-red-50 p-2 text-center text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">{loginError}</div>
          )}
          <input
            type="text"
            value={loginUsername}
            onChange={(e) => setLoginUsername(e.target.value)}
            placeholder="用户名"
            className="mb-3 w-full rounded-lg border border-zinc-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white"
          />
          <input
            type="password"
            value={loginPassword}
            onChange={(e) => setLoginPassword(e.target.value)}
            placeholder="密码"
            className="mb-4 w-full rounded-lg border border-zinc-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white"
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
          />
          <button
            onClick={handleLogin}
            disabled={loggingIn || !loginUsername.trim() || !loginPassword}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loggingIn ? '登录中...' : '登录'}
          </button>
          <p className="mt-4 text-center text-xs text-zinc-400">演示账号：admin / admin123</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-50 dark:bg-black">
      {/* 左侧会话列表侧栏（DeepSeek 风格）：小屏（<md）隐藏，桌面端常显 */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-zinc-200 bg-zinc-900 md:flex dark:border-zinc-800">
        <div className="p-3">
          <button
            onClick={handleNewSession}
            disabled={loading}
            className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
          >
            + 新建会话
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
          {sessions.map((s) => (
            <button
              key={s.session_id}
              onClick={() => handleSelectSession(s.session_id)}
              className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${
                s.session_id === sessionId ? 'bg-zinc-700/60' : 'hover:bg-zinc-800'
              }`}
            >
              <div className="truncate text-sm text-zinc-100">{s.title || '新会话'}</div>
              <div className="mt-0.5 truncate text-xs text-zinc-400">
                {formatRelativeTime(s.updated_at)} · {s.message_count} 轮
              </div>
            </button>
          ))}
          {sessions.length === 0 && (
            <div className="px-3 py-8 text-center text-xs text-zinc-500">暂无历史会话</div>
          )}
        </nav>
      </aside>

      {/* 右侧主区：标题栏 + 聊天列表 + 输入区 */}
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 py-6">
        <header className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">桂林古本智能辅助诊疗</h1>
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-500">{auth.username}</span>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-zinc-300 px-3 py-1 text-sm text-zinc-600 transition-colors hover:border-red-400 hover:text-red-500 dark:border-zinc-700 dark:text-zinc-400"
            >
              登出
            </button>
            <span className={`text-sm ${strictMode ? 'text-emerald-600' : 'text-zinc-500'}`}>
              {strictMode ? '严格模式 (RAG)' : '自由模式'}
            </span>
            <button
              onClick={() => setStrictMode(!strictMode)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                strictMode ? 'bg-emerald-600' : 'bg-zinc-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  strictMode ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </header>

        {/* 聊天消息列表 */}
        <main ref={mainRef} className="flex-1 space-y-4 overflow-y-auto pb-4" style={{ maxHeight: 'calc(100vh - 200px)' }}>
          {!historyLoaded && (
            <div className="p-4 text-center text-zinc-500">正在加载会话历史...</div>
          )}

          {historyLoaded && historyHasMore && (
            <div className="flex justify-center">
              <button
                onClick={loadEarlier}
                disabled={loadingEarlier}
                className="rounded-full border border-zinc-300 bg-white px-4 py-1.5 text-sm text-zinc-600 transition-colors hover:border-emerald-500 hover:text-emerald-600 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
              >
                {loadingEarlier ? '加载中...' : '加载更早消息'}
              </button>
            </div>
          )}

          {historyLoaded && messages.length === 0 && (
            <div className="rounded-xl bg-white p-8 text-center text-zinc-500 shadow-sm dark:bg-zinc-900">
              开始提问吧，例如：伤寒论中关于发热的辨证要点...
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'user' ? (
                <div className="max-w-[80%] rounded-2xl rounded-br-md bg-emerald-600 px-4 py-3 text-white">
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              ) : (
                <div className="max-w-[85%] space-y-3">
                  <div
                    className={`rounded-2xl rounded-bl-md bg-white p-4 shadow-sm dark:bg-zinc-900 ${
                      msg.isError ? 'border border-red-300 text-red-700 dark:border-red-800 dark:text-red-400' : ''
                    }`}
                  >
                    <h2 className="mb-1 text-sm font-semibold text-zinc-900 dark:text-zinc-50">AI 辅助分析</h2>
                    {msg.content ? (
                      <p className="whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
                        {msg.content}
                        {msg.streaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-emerald-500 align-text-bottom" />}
                      </p>
                    ) : (
                      <p className="text-sm italic text-zinc-400 dark:text-zinc-500">{msg.statusText || '...'}</p>
                    )}

                    {msg.warnings && msg.warnings.length > 0 && (
                      <div className="mt-3 rounded-md bg-yellow-50 p-3 text-sm text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400">
                        <strong>提示：</strong> {msg.warnings.join(' ')}
                      </div>
                    )}
                  </div>

                  {msg.citations && msg.citations.length > 0 && (
                    <div className="space-y-2">
                      {msg.citations.map((cite, cIdx) => (
                        <div
                          key={cIdx}
                          className="cursor-pointer rounded-lg border border-zinc-200 bg-white p-3 transition-all hover:border-emerald-500 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
                          onClick={() => handleCitationClick(cite)}
                        >
                          <div className="mb-1 flex items-center justify-between">
                            <span className="font-mono text-xs font-medium text-emerald-600">{cite.title}</span>
                            {cite.document_id.startsWith('formula_db:')
                              ? <span className="text-xs text-amber-600">方剂库精确匹配</span>
                              : <span className="text-xs text-zinc-500">匹配度: {(cite.score * 100).toFixed(1)}%</span>}
                          </div>
                          <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-3">{cite.content}</p>
                          <div className="mt-1 text-xs font-medium text-emerald-600">点击此处查看原文 →</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && !messages.some((m) => m.streaming) && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm dark:bg-zinc-900">
                <p className="text-zinc-500">分析中，请稍候...</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </main>

        {/* 输入区 */}
        <div className="flex gap-2 pt-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="请输入症状或问题，例如：伤寒论中关于发热的辨证要点..."
            className="flex-1 rounded-lg border border-zinc-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
          />
          <button
            onClick={handleAnalyze}
            disabled={loading || !question.trim() || !sessionId}
            className="rounded-lg bg-emerald-600 px-6 py-2 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? '分析中...' : '发送'}
          </button>
        </div>
      </div>

      {/* PDF 预览模态框 */}
      {showPdf && (
        <PdfViewer 
          pageNumber={targetPage} 
          endPage={targetEndPage ?? undefined}
          onClose={() => { setShowPdf(false); setTargetEndPage(null); }} 
        />
      )}
    </div>
  );
}
