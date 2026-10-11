const state = {
  currentSessionId: null,
  sessions: [],
  messages: [],
  provider: 'ollama',
  config: null,
  artifact: null,
  artifactView: 'preview',
  isBusy: false,
};

const elements = {
  appShell: document.getElementById('appShell'),
  sidebar: document.getElementById('sidebar'),
  sidebarBackdrop: document.getElementById('sidebarBackdrop'),
  mobileSidebarBtn: document.getElementById('mobileSidebarBtn'),
  collapseSidebarBtn: document.getElementById('collapseSidebarBtn'),
  sessionSearch: document.getElementById('sessionSearch'),
  providerSelect: document.getElementById('providerSelect'),
  providerStatus: document.getElementById('providerStatus'),
  providerStatusDot: document.getElementById('providerStatusDot'),
  currentTitle: document.getElementById('currentTitle'),
  themeToggle: document.getElementById('themeToggle'),
  openArtifactBtn: document.getElementById('openArtifactBtn'),
  artifactPanel: document.getElementById('artifactPanel'),
  artifactTitle: document.getElementById('artifactTitle'),
  closeArtifactBtn: document.getElementById('closeArtifactBtn'),
  conversationScroll: document.getElementById('conversationScroll'),
  newSessionBtn: document.getElementById('newSessionBtn'),
  sessionsList: document.getElementById('sessionsList'),
  messages: document.getElementById('messages'),
  chatForm: document.getElementById('chatForm'),
  promptInput: document.getElementById('promptInput'),
  artifactFrame: document.getElementById('artifactFrame'),
  artifactCode: document.getElementById('artifactCode'),
  artifactBtn: document.getElementById('artifactBtn'),
  artifactEmptyState: document.getElementById('artifactEmptyState'),
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  let json;
  try {
    json = await response.json();
  } catch (error) {
    json = {};
  }

  if (!response.ok) {
    throw new Error(json.detail || 'Request failed');
  }

  return json;
}

function setBusyState(isBusy) {
  state.isBusy = isBusy;
  elements.chatForm.classList.toggle('is-loading', isBusy);
  elements.artifactBtn.disabled = isBusy;
  elements.providerSelect.disabled = isBusy;
  const submitButton = elements.chatForm.querySelector('button[type="submit"]');
  if (submitButton) {
    submitButton.disabled = isBusy;
    submitButton.setAttribute('aria-label', isBusy ? 'Sending message' : 'Send message');
  }
}

function formatTimestamp(value) {
  if (!value) return 'Just now';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Just now';
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function renderProviderOptions(config) {
  state.config = config;
  const names = {
    ollama: 'Ollama',
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    claude_agent_sdk: 'Claude Agent SDK',
  };
  const availability = config.provider_availability || {
    ollama: Boolean(config.ollama_available),
    openai: false,
    anthropic: false,
    claude_agent_sdk: false,
  };
  const providers = (config.available_providers || Object.keys(names)).filter((provider) => names[provider]);
  elements.providerSelect.replaceChildren();
  providers.forEach((provider) => {
    const option = document.createElement('option');
    option.value = provider;
    option.textContent = availability[provider] ? names[provider] : `${names[provider]} (unavailable)`;
    option.disabled = availability[provider] === false;
    elements.providerSelect.append(option);
  });
  const configured = config.provider && providers.includes(config.provider) ? config.provider : 'ollama';
  elements.providerSelect.value = configured;
  state.provider = configured;
  updateProviderStatus();
}

function updateProviderStatus() {
  const provider = elements.providerSelect.value || 'ollama';
  const available = state.config?.provider_availability?.[provider];
  const isAvailable = available !== false;
  elements.providerStatus.textContent = isAvailable ? 'Ready' : (provider === 'ollama' ? 'Offline' : 'Not configured');
  elements.providerStatus.classList.toggle('is-unavailable', !isAvailable);
  elements.providerStatusDot.classList.toggle('is-unavailable', !isAvailable);
  elements.providerStatus.title = provider === 'ollama' && !isAvailable
    ? (state.config?.ollama_detail || 'Ollama is unavailable')
    : (isAvailable ? `${provider} is available` : `${provider} credentials or runtime are unavailable`);
}

function renderEmptyState() {
  const examples = [
    'What does product-market fit look like in a durable growth engine?',
    'How should we think about distribution as a product decision?',
    'What are the strongest writing principles for a Ship 30 for 30 habit?',
  ];

  elements.messages.innerHTML = `
    <div class="empty-state">
      <span class="welcome-mark" aria-hidden="true">L</span>
      <p class="welcome-eyebrow">Product, growth, and craft</p>
      <h2>What would you like to explore?</h2>
      <p>Ask a question grounded in Lenny’s podcast and newsletter transcripts.</p>
      <div class="example-prompt-list">
        ${examples
          .map(
            (example) => `
              <button class="example-prompt" type="button" data-example="${escapeAttribute(example)}">
                <span>${escapeHtml(example)}</span>
                <span class="example-arrow" aria-hidden="true">↗</span>
              </button>
            `,
          )
          .join('')}
      </div>
    </div>
  `;

  elements.messages.querySelectorAll('.example-prompt').forEach((button) => {
    button.addEventListener('click', () => {
      const prompt = button.dataset.example || button.textContent.trim();
      elements.promptInput.value = prompt;
      resizeComposer();
      elements.promptInput.focus();
    });
  });
}

async function loadConfig() {
  const config = await fetchJson('/api/v1/config');
  renderProviderOptions(config);
  return config;
}

function sessionGroup(dateValue) {
  const date = new Date(dateValue || 0);
  if (Number.isNaN(date.getTime())) return 'Older';
  const today = new Date();
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const daysAgo = Math.floor((startToday - startDate) / 86400000);
  if (daysAgo <= 0) return 'Today';
  if (daysAgo === 1) return 'Yesterday';
  if (daysAgo <= 7) return 'Previous 7 Days';
  return 'Older';
}

function sessionLabel(session) {
  if (session.title && session.title !== 'New Lenny conversation' && session.title !== 'New conversation') {
    return session.title;
  }
  return session.preview || 'New chat';
}

function renderSessions() {
  const query = elements.sessionSearch.value.trim().toLocaleLowerCase();
  const filtered = state.sessions.filter((session) => {
    const haystack = `${session.title || ''} ${session.preview || ''}`.toLocaleLowerCase();
    return !query || haystack.includes(query);
  });

  if (!filtered.length) {
    elements.sessionsList.innerHTML = `<div class="session-placeholder">${state.sessions.length ? 'No matching chats' : 'Your conversations will appear here'}</div>`;
    return;
  }

  const groups = ['Today', 'Yesterday', 'Previous 7 Days', 'Older'];
  elements.sessionsList.innerHTML = groups.map((group) => {
    const items = filtered.filter((session) => sessionGroup(session.updated_at || session.created_at) === group);
    if (!items.length) return '';
    return `
      <section class="session-group" aria-label="${group}">
        <h2 class="session-group-title">${group}</h2>
        <div class="session-group-items">
          ${items.map((session) => {
            const id = escapeAttribute(session.id);
            const label = sessionLabel(session);
            const preview = session.preview && session.preview !== label ? session.preview : '';
            return `
              <div class="session-item ${session.id === state.currentSessionId ? 'active' : ''}" data-session-id="${id}">
                <button class="session-open" type="button" data-session-open="${id}" aria-current="${session.id === state.currentSessionId ? 'page' : 'false'}">
                  <span class="session-title">${escapeHtml(label)}</span>
                  ${preview ? `<span class="session-preview">${escapeHtml(preview)}</span>` : ''}
                </button>
                <div class="session-actions">
                  <button class="session-action" type="button" data-session-action="rename" data-session-id="${id}" aria-label="Rename ${escapeAttribute(label)}" title="Rename chat">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 5 5 5M4 20l4.2-.8L19 8.4a2.1 2.1 0 0 0-3-3L5.2 16.2 4 20Z"></path></svg>
                  </button>
                  <button class="session-action" type="button" data-session-action="delete" data-session-id="${id}" aria-label="Delete ${escapeAttribute(label)}" title="Delete chat">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3"></path></svg>
                  </button>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </section>
    `;
  }).join('');
}

async function refreshSessions() {
  state.sessions = await fetchJson('/api/v1/sessions');
  renderSessions();
}

function setCurrentSession(sessionId) {
  state.currentSessionId = sessionId;
  try {
    if (sessionId) localStorage.setItem('lenny-current-session', sessionId);
    else localStorage.removeItem('lenny-current-session');
  } catch (error) {
    console.warn('Could not persist selected conversation', error);
  }
  renderSessions();
}

function closeMobileSidebar() {
  elements.appShell.classList.remove('sidebar-open');
}

function clearArtifact() {
  state.artifact = null;
  elements.openArtifactBtn.hidden = true;
  elements.artifactPanel.hidden = true;
  elements.appShell.classList.remove('artifact-open');
  elements.artifactEmptyState.hidden = false;
  elements.artifactFrame.hidden = true;
  elements.artifactCode.hidden = true;
}

async function loadSessions() {
  try {
    state.sessions = await fetchJson('/api/v1/sessions');
    const storedId = (() => {
      try { return localStorage.getItem('lenny-current-session'); } catch (error) { return null; }
    })();
    const selected = state.sessions.find((session) => session.id === storedId) || state.sessions[0];
    setCurrentSession(selected?.id || null);
    renderSessions();
    if (state.currentSessionId) {
      await loadSession(state.currentSessionId);
    } else {
      elements.currentTitle.textContent = 'New chat';
      state.messages = [];
      renderEmptyState();
    }
  } catch (error) {
    console.error(error);
    renderErrorMessage('Unable to load conversations. Check the backend and database, then retry.');
  }
}

async function createSession() {
  const response = await fetchJson('/api/v1/sessions', {
    method: 'POST',
    body: JSON.stringify({ user_name: 'internal-user' }),
  });
  state.sessions.unshift({ ...response, preview: null, updated_at: response.created_at });
  setCurrentSession(response.id);
  state.messages = [];
  state.currentSession = response;
  elements.currentTitle.textContent = 'New chat';
  clearArtifact();
  renderEmptyState();
  closeMobileSidebar();
  elements.promptInput.focus();
}

async function loadSession(sessionId) {
  try {
    const session = await fetchJson(`/api/v1/sessions/${sessionId}`);
    state.currentSession = session;
    state.messages = session.messages || [];
    setCurrentSession(session.id);
    const firstUserMessage = state.messages.find((message) => message.role === 'user')?.content;
    elements.currentTitle.textContent = session.title && session.title !== 'New Lenny conversation'
      ? session.title
      : (firstUserMessage || 'New chat');
    renderMessages(state.messages);
    const savedArtifact = [...state.messages].reverse().find((message) => message.artifact);
    if (savedArtifact) {
      renderArtifact(savedArtifact.artifact.type, savedArtifact.artifact.content, session.title || 'Generated artifact');
    } else {
      clearArtifact();
    }
    closeMobileSidebar();
  } catch (error) {
    console.error(error);
    renderErrorMessage('This conversation could not be loaded. It may have been removed.');
  }
}

function renderInlineText(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');
}

function renderInline(value) {
  const input = String(value || '');
  const links = /\[([^\]]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)/gi;
  let result = '';
  let cursor = 0;
  let match;
  while ((match = links.exec(input))) {
    result += renderInlineText(input.slice(cursor, match.index));
    result += `<a href="${escapeAttribute(match[2])}" target="_blank" rel="noopener noreferrer">${renderInlineText(match[1])}</a>`;
    cursor = match.index + match[0].length;
  }
  return result + renderInlineText(input.slice(cursor));
}

function markdownTableCells(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

function isMarkdownBlockStart(lines, index) {
  const line = lines[index] || '';
  return /^\s*(```|#{1,6}\s|>|[-*+]\s|\d+\.\s|---+\s*$)/.test(line)
    || (line.includes('|') && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1]));
}

function renderMarkdown(text) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index += 1; continue; }

    const fence = line.match(/^\s*```([\w+-]*)\s*$/);
    if (fence) {
      const code = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index += 1;
      const language = fence[1] ? ` class="language-${escapeAttribute(fence[1])}"` : '';
      blocks.push(`<pre><code${language}>${escapeHtml(code.join('\n'))}</code></pre>`);
      continue;
    }

    const heading = line.match(/^\s*(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      index += 1;
      continue;
    }

    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) {
      blocks.push('<hr>');
      index += 1;
      continue;
    }

    if (line.includes('|') && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1])) {
      const headers = markdownTableCells(line);
      index += 2;
      const rows = [];
      while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
        rows.push(markdownTableCells(lines[index++]));
      }
      blocks.push(`<div class="markdown-table-wrap"><table><thead><tr>${headers.map((cell) => `<th>${renderInline(cell)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map((_, cellIndex) => `<td>${renderInline(row[cellIndex] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }

    if (/^\s*>/.test(line)) {
      const quote = [];
      while (index < lines.length && /^\s*>/.test(lines[index])) quote.push(lines[index++].replace(/^\s*>\s?/, ''));
      blocks.push(`<blockquote>${quote.map((part) => `<p>${renderInline(part)}</p>`).join('')}</blockquote>`);
      continue;
    }

    const listMatch = line.match(/^\s*([-*+]\s|\d+\.\s)/);
    if (listMatch) {
      const ordered = /^\d/.test(listMatch[1]);
      const tag = ordered ? 'ol' : 'ul';
      const items = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*(?:[-*+]\s|\d+\.\s)(.+)$/);
        if (!item || /^\d/.test(item[0]) !== ordered) break;
        items.push(`<li>${renderInline(item[1])}</li>`);
        index += 1;
      }
      blocks.push(`<${tag}>${items.join('')}</${tag}>`);
      continue;
    }

    const paragraph = [];
    while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines, index)) {
      paragraph.push(lines[index++]);
    }
    if (!paragraph.length) paragraph.push(lines[index++]);
    blocks.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`);
  }
  return blocks.join('');
}

function scrollConversationToBottom() {
  elements.conversationScroll.scrollTo({
    top: elements.conversationScroll.scrollHeight,
    behavior: 'smooth',
  });
}

function renderMessages(messages) {
  state.messages = messages || [];
  if (!state.messages.length) {
    renderEmptyState();
    return;
  }

  elements.messages.innerHTML = state.messages.map((message) => {
    const isAssistant = message.role === 'assistant';
    const citations = Array.isArray(message.citations) ? message.citations : [];
    const citationsHtml = citations.length ? `
      <div class="citation-stack" aria-label="Sources">
        ${citations.map((item) => `<span class="citation-chip">Source: ${escapeHtml(String(item).replace(/\.(txt|md)$/i, ''))}</span>`).join('')}
      </div>` : '';
    const copyAction = isAssistant && message.id ? `
      <button class="message-copy" type="button" data-copy-message="${escapeAttribute(message.id)}" aria-label="Copy response" title="Copy response">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="12" rx="2"></rect><path d="M16 8V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2"></path></svg>
      </button>` : '';
    return `
      <article class="message-row ${isAssistant ? 'assistant' : 'user'}">
        <div class="message-avatar ${isAssistant ? 'assistant-avatar' : 'user-avatar'}" aria-hidden="true">${isAssistant ? 'L' : 'Y'}</div>
        <div class="message-content">
          <header class="message-header"><strong>${isAssistant ? 'Lenny Growth Assistant' : 'You'}</strong><time>${formatTimestamp(message.created_at)}</time></header>
          <div class="message-body">${renderMarkdown(message.content)}</div>
          ${citationsHtml}
          ${copyAction ? `<div class="message-actions">${copyAction}</div>` : ''}
        </div>
      </article>
    `;
  }).join('');
  scrollConversationToBottom();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttribute(value) {
  return escapeHtml(value)
    .replace(/\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function addLoadingIndicator() {
  const marker = `
    <article class="message-row assistant loading" aria-live="polite">
      <div class="message-avatar assistant-avatar" aria-hidden="true">L</div>
      <div class="message-content"><header class="message-header"><strong>Lenny Growth Assistant</strong></header>
      <div class="typing-indicator" aria-label="Assistant is thinking">
        <span></span>
        <span></span>
        <span></span>
      </div>
      </div>
    </article>
  `;
  elements.messages.insertAdjacentHTML('beforeend', marker);
  scrollConversationToBottom();
}

function removeLoadingIndicator() {
  const loadingMessage = elements.messages.querySelector('.message.loading');
  if (loadingMessage) loadingMessage.remove();
}

function renderErrorMessage(message) {
  const content = `
    <article class="system-error" role="alert">
      <strong>Request failed</strong>
      <p>${escapeHtml(message)}</p>
      <button class="retry-link" type="button" data-retry="prompt">Retry</button>
    </article>
  `;
  elements.messages.insertAdjacentHTML('beforeend', content);
  scrollConversationToBottom();
}

async function sendPrompt(message, artifactType = null) {
  if (!message || !message.trim() || state.isBusy) return;
  if (!state.currentSessionId) {
    await createSession();
  }

  const sessionId = state.currentSessionId;
  const provider = elements.providerSelect.value || state.provider;
  state.messages = [...state.messages, {
    id: `pending-${Date.now()}`,
    role: 'user',
    content: message,
    created_at: new Date().toISOString(),
  }];
  renderMessages(state.messages);
  setBusyState(true);
  addLoadingIndicator();

  try {
    const body = {
      message,
      provider,
      artifact_type: artifactType,
    };

    const result = await fetchJson(`/api/v1/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify(body),
    });

    elements.promptInput.value = '';
    resizeComposer();
    await loadSession(sessionId);
    await refreshSessions();

    if (result.artifact) {
      renderArtifact(result.artifact.type, result.artifact.content, result.artifact.title || message, true);
    }
  } catch (error) {
    console.error(error);
    removeLoadingIndicator();
    try { await loadSession(sessionId); } catch (loadError) { console.error(loadError); }
    renderErrorMessage(error.message || 'The assistant could not complete that request.');
  } finally {
    removeLoadingIndicator();
    setBusyState(false);
  }
}

function renderArtifact(type, content, title, open = false) {
  state.artifact = { type, content, title };
  elements.artifactTitle.textContent = title || 'Generated artifact';
  elements.openArtifactBtn.hidden = false;
  elements.artifactEmptyState.hidden = true;

  if (type === 'markdown') {
    elements.artifactFrame.srcdoc = buildArtifactDocument(renderMarkdown(content));
    elements.artifactCode.textContent = content;
  } else {
    elements.artifactFrame.srcdoc = buildArtifactDocument(content);
    elements.artifactCode.textContent = content;
  }

  applyArtifactView(state.artifactView);
  if (open) setArtifactPanel(true);
}

function setArtifactPanel(isOpen) {
  elements.artifactPanel.hidden = !isOpen;
  elements.appShell.classList.toggle('artifact-open', isOpen);
  if (isOpen) elements.openArtifactBtn.setAttribute('aria-expanded', 'true');
  else elements.openArtifactBtn.setAttribute('aria-expanded', 'false');
}

function buildArtifactDocument(htmlContent) {
  return `
    <html>
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: https:; style-src 'unsafe-inline';" />
        <style>
          body {
            font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            max-width: 760px;
            margin: 0 auto;
            padding: 32px 28px;
            color: #252525;
            line-height: 1.72;
            background: #fff;
          }
          h1, h2, h3 { color: #202123; line-height: 1.3; }
          code { background: #f1f1ef; padding: .15rem .35rem; border-radius: 5px; }
          pre { background: #f1f1ef; padding: 1rem; border-radius: 8px; overflow: auto; }
          table { border-collapse: collapse; width: 100%; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          blockquote { border-left: 3px solid #c9c9c4; padding-left: 1rem; color: #666; }
          a { color: #176b65; }
        </style>
      </head>
      <body>${htmlContent}</body>
    </html>
  `;
}

function applyArtifactView(view) {
  state.artifactView = view;
  const tabButtons = document.querySelectorAll('.tab-button');
  tabButtons.forEach((button) => {
    const isActive = button.dataset.view === view;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-selected', String(isActive));
  });

  if (!state.artifact) {
    elements.artifactEmptyState.hidden = false;
    elements.artifactFrame.hidden = true;
    elements.artifactCode.hidden = true;
    return;
  }

  elements.artifactEmptyState.hidden = true;
  const isPreview = view === 'preview';
  elements.artifactFrame.hidden = !isPreview;
  elements.artifactCode.hidden = isPreview;
}

async function generateArtifact() {
  const prompt = elements.promptInput.value.trim();
  if (!prompt) {
    elements.promptInput.focus();
    return;
  }
  await sendPrompt(prompt, 'html');
}

async function copyArtifact() {
  if (!state.artifact) return;
  try {
    const text = state.artifact.content || '';
    await navigator.clipboard.writeText(text);
  } catch (error) {
    console.warn('Copy failed', error);
  }
}

function downloadArtifact() {
  if (!state.artifact) return;
  const fileName = `${(state.artifact.title || 'artifact').replace(/\s+/g, '-').toLowerCase()}.txt`;
  const blob = new Blob([state.artifact.content || ''], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function renameSession(sessionId) {
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!session) return;
  const item = elements.sessionsList.querySelector(`.session-item[data-session-id="${CSS.escape(sessionId)}"]`);
  const opener = item?.querySelector('.session-open');
  if (!opener) return;

  const form = document.createElement('form');
  form.className = 'session-rename-form';
  const input = document.createElement('input');
  input.className = 'session-rename-input';
  input.type = 'text';
  input.maxLength = 255;
  input.value = sessionLabel(session);
  input.setAttribute('aria-label', 'Conversation title');
  form.append(input);
  opener.replaceWith(form);
  input.focus();
  input.select();

  const cancel = () => renderSessions();
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      cancel();
    }
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const title = input.value.trim();
    if (!title) {
      input.setCustomValidity('Enter a conversation title.');
      input.reportValidity();
      return;
    }
    try {
      await fetchJson(`/api/v1/sessions/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      });
      await refreshSessions();
      if (sessionId === state.currentSessionId) elements.currentTitle.textContent = title;
    } catch (error) {
      renderErrorMessage(error.message || 'Conversation could not be renamed.');
    }
  });
}

function deleteSession(sessionId) {
  const session = state.sessions.find((item) => item.id === sessionId);
  const item = elements.sessionsList.querySelector(`.session-item[data-session-id="${CSS.escape(sessionId)}"]`);
  const actions = item?.querySelector('.session-actions');
  if (!session || !actions || actions.querySelector('.delete-confirm')) return;

  actions.replaceChildren();
  const prompt = document.createElement('span');
  prompt.className = 'delete-confirm-label';
  prompt.textContent = 'Delete?';
  const confirmButton = document.createElement('button');
  confirmButton.className = 'delete-confirm';
  confirmButton.type = 'button';
  confirmButton.textContent = 'Yes';
  confirmButton.setAttribute('aria-label', `Confirm delete ${sessionLabel(session)}`);
  const cancelButton = document.createElement('button');
  cancelButton.className = 'delete-cancel';
  cancelButton.type = 'button';
  cancelButton.textContent = 'No';
  cancelButton.setAttribute('aria-label', 'Cancel delete');
  actions.append(prompt, confirmButton, cancelButton);

  cancelButton.addEventListener('click', renderSessions, { once: true });
  confirmButton.addEventListener('click', async () => {
    confirmButton.disabled = true;
    try {
      await fetchJson(`/api/v1/sessions/${sessionId}`, { method: 'DELETE' });
      state.sessions = state.sessions.filter((item) => item.id !== sessionId);
      if (sessionId === state.currentSessionId) {
        setCurrentSession(null);
        state.currentSession = null;
        state.messages = [];
        elements.currentTitle.textContent = 'New chat';
        clearArtifact();
        renderEmptyState();
      } else {
        renderSessions();
      }
    } catch (error) {
      confirmButton.disabled = false;
      renderErrorMessage(error.message || 'Conversation could not be deleted.');
    }
  }, { once: true });
}

function resizeComposer() {
  elements.promptInput.style.height = 'auto';
  elements.promptInput.style.height = `${Math.min(elements.promptInput.scrollHeight, 200)}px`;
  elements.promptInput.style.overflowY = elements.promptInput.scrollHeight > 200 ? 'auto' : 'hidden';
}

async function copyMessage(messageId) {
  const message = state.messages.find((item) => String(item.id) === String(messageId));
  if (!message) return;
  try {
    await navigator.clipboard.writeText(message.content || '');
  } catch (error) {
    renderErrorMessage('Clipboard access is unavailable in this browser.');
  }
}

function attachEvents() {
  elements.newSessionBtn.addEventListener('click', () => {
    createSession().catch((error) => renderErrorMessage(error.message || 'A new conversation could not be created.'));
  });

  elements.chatForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const message = elements.promptInput.value.trim();
    if (!message) return;
    sendPrompt(message).catch((error) => renderErrorMessage(error.message || 'The message could not be sent.'));
  });

  elements.promptInput.addEventListener('input', resizeComposer);
  elements.promptInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      elements.chatForm.requestSubmit();
    }
  });

  elements.providerSelect.addEventListener('change', () => {
    state.provider = elements.providerSelect.value;
    updateProviderStatus();
  });

  elements.sessionSearch.addEventListener('input', renderSessions);
  elements.sessionsList.addEventListener('click', (event) => {
    const action = event.target.closest('[data-session-action]');
    if (action) {
      event.stopPropagation();
      if (action.dataset.sessionAction === 'rename') renameSession(action.dataset.sessionId);
      if (action.dataset.sessionAction === 'delete') deleteSession(action.dataset.sessionId);
      return;
    }
    const opener = event.target.closest('[data-session-open]');
    if (opener && opener.dataset.sessionOpen !== state.currentSessionId) {
      loadSession(opener.dataset.sessionOpen);
    }
  });

  elements.collapseSidebarBtn.addEventListener('click', () => {
    elements.appShell.classList.toggle('sidebar-collapsed');
    try { localStorage.setItem('lenny-sidebar-collapsed', String(elements.appShell.classList.contains('sidebar-collapsed'))); } catch (error) { /* storage is optional */ }
  });
  elements.mobileSidebarBtn.addEventListener('click', () => elements.appShell.classList.add('sidebar-open'));
  elements.sidebarBackdrop.addEventListener('click', closeMobileSidebar);
  elements.themeToggle.addEventListener('click', () => {
    const nextTheme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
    document.body.dataset.theme = nextTheme;
    elements.themeToggle.setAttribute('aria-label', `Switch to ${nextTheme === 'dark' ? 'light' : 'dark'} theme`);
    try { localStorage.setItem('lenny-theme', nextTheme); } catch (error) { /* storage is optional */ }
  });

  elements.openArtifactBtn.addEventListener('click', () => setArtifactPanel(elements.artifactPanel.hidden));
  elements.closeArtifactBtn.addEventListener('click', () => setArtifactPanel(false));
  elements.artifactBtn.addEventListener('click', generateArtifact);
  document.addEventListener('click', (event) => {
    const suggestion = event.target.closest('[data-example]');
    if (suggestion) {
      elements.promptInput.value = suggestion.dataset.example || '';
      resizeComposer();
      elements.promptInput.focus();
    }
    const tab = event.target.closest('.tab-button');
    if (tab) applyArtifactView(tab.dataset.view || 'preview');
    const copyButton = event.target.closest('[data-action="copy-artifact"]');
    if (copyButton) copyArtifact();
    const downloadButton = event.target.closest('[data-action="download-artifact"]');
    if (downloadButton) downloadArtifact();
    const messageCopy = event.target.closest('[data-copy-message]');
    if (messageCopy) copyMessage(messageCopy.dataset.copyMessage);
  });

  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-retry]');
    if (!target) return;
    const message = elements.promptInput.value.trim();
    if (message) sendPrompt(message);
    else if (state.currentSessionId) loadSession(state.currentSessionId);
    else loadSessions();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      event.preventDefault();
      elements.sessionSearch.focus();
    }
    if (event.key === 'Escape') {
      closeMobileSidebar();
      setArtifactPanel(false);
    }
  });
}

async function init() {
  try {
    const savedTheme = localStorage.getItem('lenny-theme');
    if (savedTheme === 'dark') document.body.dataset.theme = 'dark';
    if (localStorage.getItem('lenny-sidebar-collapsed') === 'true') elements.appShell.classList.add('sidebar-collapsed');
  } catch (error) {
    // Preferences are optional; the app remains usable when storage is blocked.
  }
  attachEvents();
  await loadConfig();
  await loadSessions();
  applyArtifactView('preview');
}

init().catch((error) => {
  console.error(error);
  renderEmptyState();
  elements.messages.insertAdjacentHTML(
    'beforeend',
    `<div class="message system error"><p>Unable to load the app: ${escapeHtml(error.message)}</p></div>`,
  );
});
