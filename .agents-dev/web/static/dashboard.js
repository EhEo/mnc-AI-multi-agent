/* dashboard.js — SSE client for the 3-agent team web dashboard */

// ── Helpers ────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Convert plain agent text to minimal HTML (headings, lists, code, bold). */
function renderText(text) {
  if (!text) return '';
  return esc(text)
    .replace(/^## (.+)$/gm,  '<h3 class="md-h2">$1</h3>')
    .replace(/^### (.+)$/gm, '<h4 class="md-h3">$1</h4>')
    .replace(/^- (.+)$/gm,   '<div class="md-li">· $1</div>')
    .replace(/`([^`]+)`/g,   '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function statusClass(s) { return 'status-' + (s || 'waiting'); }

function setStatus(id, status) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = status;
  el.className = 'status-badge ' + statusClass(status);
}

function verdictClass(word) {
  return { SHIP: 'verdict-ship', 'NEEDS-FIX': 'verdict-fix', DISCUSS: 'verdict-discuss' }[word]
         || 'verdict-unknown';
}

// ── Panel updaters ─────────────────────────────────────────────────────────

function updateGemini(d) {
  setStatus('gemini-status', d.status);
  const body = document.getElementById('gemini-body');
  if (!body) return;

  if (d.status === 'waiting') {
    body.innerHTML = '<div class="empty-msg">Waiting for first call...</div>';
    return;
  }

  let html = '';
  if (d.ts) html += `<div class="meta">Started: ${esc(d.ts)}</div>`;

  if (d.query) {
    html += `<div class="section-label">Query</div>
             <div class="query-text">${esc(d.query)}</div>`;
  }

  if (d.status === 'running') {
    html += `<div class="meta" style="margin-top:10px;color:var(--yellow)">⏳ running…</div>`;
  }

  if (d.status === 'done' && d.response) {
    html += `<div class="section-label">Answer</div>
             <div class="response-text">${renderText(d.response)}</div>`;
    if (d.sources > 0)
      html += `<div class="sources">🔗 Sources cited: ${d.sources}</div>`;
  }

  if (d.status === 'failed') {
    html += `<div class="meta" style="color:var(--red)">✗ failed (rc=${d.rc})</div>`;
  }

  body.innerHTML = html;
}

function updateCodex(d) {
  setStatus('codex-status', d.status);
  const body = document.getElementById('codex-body');
  if (!body) return;

  if (d.status === 'waiting') {
    body.innerHTML = '<div class="empty-msg">Waiting for first call...</div>';
    return;
  }

  let html = '';
  if (d.ts) html += `<div class="meta">Started: ${esc(d.ts)}</div>`;

  if (d.focus) {
    html += `<div class="section-label">Focus</div>
             <div class="focus-text">${esc(d.focus)}</div>`;
  }

  if (d.status === 'running') {
    html += `<div class="meta" style="margin-top:10px;color:var(--yellow)">⏳ running…</div>`;
  }

  if (d.verdict) {
    html += `<div class="section-label">Verdict</div>
             <div class="verdict ${verdictClass(d.word)}">${esc(d.verdict)}</div>`;
  }

  if (d.findings && Object.values(d.findings).some(v => v > 0)) {
    const f = d.findings;
    const b = f['Blocker']     || 0;
    const m = f['Major']       || 0;
    const n = f['Minor / Nit'] || 0;
    html += `<div class="findings">
      <span class="finding-chip chip-blocker">${b} blocker</span>
      <span class="finding-chip chip-major">${m} major</span>
      <span class="finding-chip chip-minor">${n} minor</span>
    </div>`;
  }

  if (d.status === 'done' && d.response) {
    html += `<div class="section-label">Full Review</div>
             <div class="response-text">${renderText(d.response)}</div>`;
  }

  if (d.status === 'failed') {
    html += `<div class="meta" style="color:var(--red)">✗ failed (rc=${d.rc})</div>`;
  }

  body.innerHTML = html;
}

function addActivity(d) {
  const log = document.getElementById('activity-log');
  if (!log) return;

  // Remove placeholder
  const placeholder = log.querySelector('.empty-msg');
  if (placeholder) placeholder.remove();

  const icon  = d.agent === 'gemini' ? '🔍' : '🧐';
  const cls   = 'activity-' + d.agent;
  const entry = document.createElement('div');
  entry.className = 'activity-entry';
  entry.innerHTML = `<span class="${cls}">${icon} ${esc(d.agent)}</span>
                     <span class="activity-ts">${esc(d.ts)}</span>`;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

// ── SSE connection ─────────────────────────────────────────────────────────

function connect() {
  const dot   = document.getElementById('conn-dot');
  const label = document.getElementById('conn-label');

  const src = new EventSource('/events');

  src.onopen = () => {
    dot.className   = 'conn-dot connected';
    label.textContent = 'live';
  };

  src.addEventListener('gemini',    e => updateGemini(JSON.parse(e.data)));
  src.addEventListener('codex',     e => updateCodex(JSON.parse(e.data)));
  src.addEventListener('activity',  e => addActivity(JSON.parse(e.data)));
  src.addEventListener('heartbeat', () => {});  // keep-alive

  src.onerror = () => {
    dot.className   = 'conn-dot disconnected';
    label.textContent = 'reconnecting…';
    src.close();
    setTimeout(connect, 3000);  // auto-reconnect
  };
}

// ── Init ───────────────────────────────────────────────────────────────────

fetch('/config')
  .then(r => r.json())
  .then(cfg => {
    const badge = document.getElementById('team-name');
    if (badge) badge.textContent = cfg.team;
    document.title = `${cfg.team} — Agent Dashboard`;
  });

connect();
