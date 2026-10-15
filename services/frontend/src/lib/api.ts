export interface Citation {
  title: string;
  content: string;
  score: number;
  document_id: string;
  /** C 轮 16.36：PDF 页（前端跳转）；历史数据可能缺失 */
  pdf_page_start?: number;
  pdf_page_end?: number;
  book_page_start?: number;
  book_page_end?: number;
}

export interface AnalyzeRequest {
  sessionId: string;
  question: string;
  strictMode?: boolean;
  topK?: number;
}

export interface AnalyzeResponse {
  answer: string;
  intent: string;
  citations: Citation[];
  warnings: string[];
  status: string;
  request_id: string;
}

// ---------- 登录态与鉴权（D 轮 16.40 JWT） ----------

const TOKEN_STORAGE_KEY = 'guilinguben_token';
const USERNAME_STORAGE_KEY = 'guilinguben_username';

export interface LoginResponse {
  token: string;
  username: string;
  roles: string[];
}

// 401 全局回调：页面注册后，任何业务接口返回 401 时触发（清登录态回登录页）
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function getStoredUsername(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(USERNAME_STORAGE_KEY);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USERNAME_STORAGE_KEY);
}

/** 登录：成功后将 token/username 存入 localStorage（后续请求自动携带） */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await fetch('http://localhost:8080/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    // 登录失败 401 不触发全局登出回调（本就未登录），读取后端 message 抛给登录表单展示
    const text = await response.text().catch(() => '');
    let message = '登录失败，请稍后重试';
    try {
      const parsed = JSON.parse(text);
      if (parsed?.message) message = parsed.message;
    } catch {
      /* 非 JSON 响应保持默认提示 */
    }
    throw new Error(message);
  }
  const result = await response.json();
  const data = result.data as LoginResponse;
  localStorage.setItem(TOKEN_STORAGE_KEY, data.token);
  localStorage.setItem(USERNAME_STORAGE_KEY, data.username);
  return data;
}

/** 统一请求头：已登录时自动携带 Bearer token（业务请求均需鉴权） */
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

/** 401 统一处理：清本地登录态并触发全局回调（页面层回登录页）；返回 true 表示是 401 */
function handleUnauthorized(status: number): boolean {
  if (status !== 401) return false;
  clearAuth();
  onUnauthorized?.();
  return true;
}

export async function analyzeQuestion(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const startTime = Date.now();
  console.log('[全链路] 前端发送分析请求:', JSON.stringify(request));

  const response = await fetch('http://localhost:8080/api/analysis', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    if (handleUnauthorized(response.status)) throw new Error('登录已过期，请重新登录');
    const errorText = await response.text().catch(() => '');
    console.error('[全链路] 前端分析请求失败:', response.status, errorText.slice(0, 200));
    throw new Error(`API error: ${response.statusText}`);
  }

  const result = await response.json();
  const data = result.data as AnalyzeResponse;
  console.log(
    `[全链路] 前端收到分析响应: intent=${data.intent}, citations数=${data.citations.length}, ` +
    `warnings数=${data.warnings.length}, 回答长度=${data.answer.length}, 耗时=${Date.now() - startTime}ms`
  );
  return data;
}

// ---------- B5 SSE 流式（断连三件套：事件 id 去重、Last-Event-ID 断点续传、历史兜底） ----------

export interface StreamCallbacks {
  /** 阶段状态事件（stage: guardrail_blocked / tool_calling / generating） */
  onStatus?: (stage: string, message: string) => void;
  /** 回答 token 增量（打字机渲染） */
  onDelta?: (text: string) => void;
  /** 最终完整结果（含 citations/warnings，渲染证据卡） */
  onDone?: (result: AnalyzeResponse) => void;
  /** 错误事件；recoverable=true 时页面应走历史接口兜底 */
  onError?: (message: string, recoverable: boolean) => void;
}

/** 流式中断异常：携带已收到的最后事件 id，供页面层断点续传（16.30 Layer 2） */
export class StreamInterruptedError extends Error {
  constructor(public readonly lastEventId: number) {
    super('stream interrupted');
    this.name = 'StreamInterruptedError';
  }
}

/**
 * SSE 流式分析：POST 请求（问题在请求体，浏览器 EventSource 只支持 GET，故用 fetch 手动解析）。
 * 断连时抛出 StreamInterruptedError(lastEventId)，由页面层带 Last-Event-ID 重连续传。
 */
export async function analyzeQuestionStream(
  request: AnalyzeRequest,
  callbacks: StreamCallbacks,
  lastEventId?: number
): Promise<void> {
  const startTime = Date.now();
  console.log('[全链路] 前端发送流式分析请求: lastEventId=', lastEventId ?? 0);

  const headers: Record<string, string> = authHeaders({ 'Content-Type': 'application/json' });
  if (lastEventId && lastEventId > 0) {
    // SSE 规范的断点续传：EventSource 会自动携带，fetch 需手动设置
    headers['Last-Event-ID'] = String(lastEventId);
  }

  const response = await fetch('http://localhost:8080/api/analysis/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    if (handleUnauthorized(response.status)) throw new Error('登录已过期，请重新登录');
    // 限流 429（⑤Redis 16.35）：后端返回友好 JSON，前端透出可读提示（其余错误保持原逻辑）
    if (response.status === 429) {
      throw new Error('请求过于频繁，请稍后再试');
    }
    throw new Error(`API error: ${response.statusText}`);
  }
  if (!response.body) {
    throw new Error('流式响应无 body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentId = lastEventId ?? 0;
  const seenIds = new Set<number>();

  // 解析一个 SSE 事件块（id:/event:/data: 行），按 event_id 去重后分发回调
  const handleBlock = (block: string) => {
    let id = 0;
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('id:')) {
        id = parseInt(line.slice(3).trim(), 10);
      } else if (line.startsWith('event:')) {
        event = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        data += line.slice(5).trim();
      }
    }
    if (id > 0) {
      currentId = id;
      if (seenIds.has(id)) return; // Layer 1 去重：重连重放时按 event_id 幂等合并
      seenIds.add(id);
    }
    if (!data) return;

    let payload: AnalyzeResponse | { text?: string; stage?: string; message?: string; recoverable?: boolean };
    try {
      payload = JSON.parse(data);
    } catch {
      return;
    }
    switch (event) {
      case 'status':
        callbacks.onStatus?.((payload as { stage: string }).stage, (payload as { message: string }).message);
        break;
      case 'answer_delta':
        callbacks.onDelta?.((payload as { text: string }).text);
        break;
      case 'done':
        callbacks.onDone?.(payload as AnalyzeResponse);
        break;
      case 'error':
        callbacks.onError?.(
          (payload as { message: string }).message,
          (payload as { recoverable: boolean }).recoverable
        );
        break;
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (block.trim()) handleBlock(block);
      }
    }
    if (buffer.trim()) handleBlock(buffer); // 末尾无空行分隔的残留块
    console.log(`[全链路] 流式响应结束: 最后事件id=${currentId}, 耗时=${Date.now() - startTime}ms`);
  } catch (err) {
    console.warn('[全链路] 流式连接中断:', err, '最后事件id=', currentId);
    throw new StreamInterruptedError(currentId);
  }
}

export interface HistoryMessage {
  question: string;
  answer: string;
  citations: Citation[];
  created_at: string;
}

// 会话历史分页响应（历史接口分页 16.32）：messages 为当前页（升序），hasMore 表示是否还有更早记录
export interface HistoryPage {
  messages: HistoryMessage[];
  total: number;
  hasMore: boolean;
}

export async function fetchSessionHistory(
  sessionId: string,
  limit = 50,
  offset = 0
): Promise<HistoryPage> {
  console.log(`[全链路] 前端拉取会话历史: sessionId=${sessionId}, limit=${limit}, offset=${offset}`);

  const response = await fetch(
    `http://localhost:8080/api/analysis/history?sessionId=${encodeURIComponent(sessionId)}&limit=${limit}&offset=${offset}`,
    { headers: authHeaders() }
  );

  if (!response.ok) {
    if (handleUnauthorized(response.status)) throw new Error('登录已过期，请重新登录');
    console.error('[全链路] 前端拉取历史失败:', response.status);
    throw new Error(`API error: ${response.statusText}`);
  }

  const result = await response.json();
  const page = result.data as HistoryPage;
  console.log(`[全链路] 前端历史加载完成: 本页=${page.messages.length}, 总数=${page.total}, hasMore=${page.hasMore}`);
  return page;
}

// ---------- 会话列表侧栏（A 轮：DeepSeek 风格左侧会话列表） ----------

// 会话摘要：title 为首条提问（空会话为 null），message_count 为记录数（一问一答计 1 条）
export interface SessionSummary {
  session_id: string;
  title: string | null;
  message_count: number;
  updated_at: string;
}

export async function fetchSessionList(): Promise<SessionSummary[]> {
  const response = await fetch('http://localhost:8080/api/analysis/sessions', {
    headers: authHeaders(),
  });

  if (!response.ok) {
    if (handleUnauthorized(response.status)) throw new Error('登录已过期，请重新登录');
    console.error('[全链路] 前端拉取会话列表失败:', response.status);
    throw new Error(`API error: ${response.statusText}`);
  }

  const result = await response.json();
  return result.data as SessionSummary[];
}

export interface ExplainTextRequest {
  question: string;
}

export interface ExplainTextResponse {
  answer: string;
}

export async function explainText(request: ExplainTextRequest): Promise<ExplainTextResponse> {
  const response = await fetch('http://localhost:8080/api/explain', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    if (handleUnauthorized(response.status)) throw new Error('登录已过期，请重新登录');
    throw new Error(`API error: ${response.statusText}`);
  }

  const result = await response.json();
  return result.data as ExplainTextResponse;
}
