'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────
const API_BASE = window.location.port === '8080' ? '/api/v1' : 'http://localhost:8000/api/v1';

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let state = {
  token:      localStorage.getItem('pesa_token') || null,
  user:       null,
  budgets:    [],
  analytics:  null,
  txPage:     1,
  txFilter:   { category: '', type: '' },
  activeTab:  'transactions',
};

// ─────────────────────────────────────────────────────────────────────────────
// API helper
// FIX: skipAuthRedirect prevents auto-logout on login/register 401 errors.
// Without this flag, a failed login attempt would call logout() and show
// a confusing "Logged out" toast instead of an "Invalid credentials" error.
// ─────────────────────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}, skipAuthRedirect = false) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    if (res.status === 401 && !skipAuthRedirect) {
      _silentLogout();
      return;
    }
    const msg = data.detail || `HTTP ${res.status}`;
    throw new Error(Array.isArray(msg) ? msg.map(e => e.msg).join(', ') : msg);
  }
  return data;
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────────────────────────
function toast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ─────────────────────────────────────────────────────────────────────────────
// Format helpers
// ─────────────────────────────────────────────────────────────────────────────
const fmt = {
  currency: (n, cur = 'KES') =>
    new Intl.NumberFormat('en-KE', { style:'currency', currency:cur, minimumFractionDigits:2 }).format(Number(n)||0),
  relDate: d => {
    const days = Math.floor((Date.now() - new Date(d)) / 86400000);
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7)  return `${days} days ago`;
    return new Date(d).toLocaleDateString('en-KE', {day:'numeric',month:'short',year:'numeric'});
  },
};
const ICONS = { Salary:'💼',Freelance:'💻',Food:'🛒',Transport:'🚗',Rent:'🏠',Utilities:'⚡',
                Airtime:'📱',Shopping:'🛍️','Eating Out':'🍽️',Healthcare:'🏥',
                Entertainment:'🎬',Education:'📚',Savings:'🏦',Other:'📦' };
const catIcon = c => ICONS[c] || '💰';
const esc = s => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : '';

// ─────────────────────────────────────────────────────────────────────────────
// Routing — views & tabs
// ─────────────────────────────────────────────────────────────────────────────
function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(id)?.classList.add('active');
}

/**
 * FIX: Tab content panels need display:none / display:block toggling.
 * The CSS rule `.tab-content { display:none }` + `.tab-content.active { display:block }`
 * was missing, so all panels were visible simultaneously.
 * Also: animate the sliding indicator pill under the active tab.
 */
function showTab(tab) {
  state.activeTab = tab;

  // Toggle button states
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));

  // Animate indicator
  const activeBtn = document.querySelector(`.tab[data-tab="${tab}"]`);
  const indicator = document.getElementById('tab-indicator');
  if (activeBtn && indicator) {
    const barRect = activeBtn.closest('.tab-bar').getBoundingClientRect();
    const btnRect = activeBtn.getBoundingClientRect();
    indicator.style.width  = `${btnRect.width - 16}px`;
    indicator.style.left   = `${btnRect.left - barRect.left + 8}px`;
    indicator.style.opacity = '1';
  }

  // Show/hide content — THE key fix
  document.querySelectorAll('.tab-content').forEach(c =>
    c.classList.toggle('active', c.dataset.content === tab)
  );

  // Load data
  if (tab === 'transactions') loadTransactions();
  if (tab === 'budgets')      loadBudgetsWithSpend();
  if (tab === 'analytics')    renderAnalyticsPanel();
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth
// ─────────────────────────────────────────────────────────────────────────────
async function login(email, password) {
  // skipAuthRedirect=true: 401 here = wrong password, NOT expired session
  const data = await apiFetch('/auth/login', { method:'POST', body:{email,password} }, true);
  if (!data) return;
  state.token = data.access_token;
  localStorage.setItem('pesa_token', state.token);
  await loadCurrentUser();
  await loadAnalytics();          // preload analytics so budgets have spend data
  enterDashboard();
  const name = state.user?.full_name?.split(' ')[0] || 'there';
  toast(`Welcome back, ${name}! 👋`, 'success');
}

async function register(email, password, full_name) {
  await apiFetch('/auth/register', { method:'POST', body:{email,password,full_name} }, true);
  toast('Account created — please log in', 'success');
  showView('view-login');
}

async function loadCurrentUser() {
  state.user = await apiFetch('/auth/me');
  if (state.user) {
    document.getElementById('user-name').textContent =
      state.user.full_name || state.user.email.split('@')[0];
  }
}

function _silentLogout() {
  state.token = null; state.user = null; state.analytics = null;
  localStorage.removeItem('pesa_token');
  document.getElementById('nav-auth-actions').style.display = 'none';
  showView('view-login');
}

function logout() {
  _silentLogout();
  toast('You have been logged out', 'info');
}

function enterDashboard() {
  document.getElementById('nav-auth-actions').style.display = 'flex';
  showView('view-dashboard');
  showTab('transactions');
}

// ─────────────────────────────────────────────────────────────────────────────
// Transactions
// ─────────────────────────────────────────────────────────────────────────────
async function loadTransactions(page = 1) {
  state.txPage = page;
  document.getElementById('tx-list').innerHTML =
    '<div class="loading-overlay"><div class="spinner"></div></div>';

  const p = new URLSearchParams({ page, size: 15 });
  if (state.txFilter.category) p.set('category', state.txFilter.category);
  if (state.txFilter.type)     p.set('type',     state.txFilter.type);

  try {
    const data = await apiFetch(`/transactions?${p}`);
    if (!data) return;
    renderTransactions(data);
  } catch (e) { toast(e.message, 'error'); }
}

function renderTransactions({ items, total, page, size }) {
  document.getElementById('tx-count').textContent = `${total} total`;

  document.getElementById('tx-list').innerHTML = !items.length
    ? '<div class="empty"><div class="empty-icon">💸</div>No transactions yet. Add your first one!</div>'
    : items.map(tx => `
        <div class="tx-item">
          <div class="tx-icon ${tx.type}">${catIcon(tx.category)}</div>
          <div class="tx-body">
            <div class="tx-desc">${esc(tx.description || tx.category)}<span class="tx-cat">${esc(tx.category)}</span></div>
            <div class="tx-meta">${fmt.relDate(tx.created_at)} · ${tx.currency}</div>
          </div>
          <div class="tx-amount ${tx.type}">${tx.type==='income'?'+':'−'}${fmt.currency(tx.amount, tx.currency)}</div>
          <button class="btn btn-ghost btn-sm btn-icon" onclick="deleteTx('${tx.id}')" title="Delete">🗑</button>
        </div>`).join('');

  const pages = Math.ceil(total / size);
  document.getElementById('tx-pager').innerHTML = pages <= 1 ? '' : `
    <div style="display:flex;gap:8px;justify-content:center;margin-top:16px">
      <button class="btn btn-ghost btn-sm" onclick="loadTransactions(${page-1})" ${page<=1?'disabled':''}>← Prev</button>
      <span style="padding:6px 12px;color:var(--text-muted);font-size:.82rem">${page} / ${pages}</span>
      <button class="btn btn-ghost btn-sm" onclick="loadTransactions(${page+1})" ${page>=pages?'disabled':''}>Next →</button>
    </div>`;
}

async function createTransaction(form) {
  try {
    await apiFetch('/transactions', { method:'POST', body:{
      amount:      parseFloat(form.amount.value),
      currency:    form.currency.value || 'KES',
      category:    form.category.value,
      description: form.description.value || null,
      type:        form.type.value,
    }});
    toast('Transaction added ✅', 'success');
    closeModal('modal-add-tx');
    form.reset();
    // Refresh analytics so stat cards + budget bars update immediately
    await loadAnalytics();
    loadTransactions();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteTx(id) {
  if (!confirm('Delete this transaction?')) return;
  try {
    await apiFetch(`/transactions/${id}`, { method:'DELETE' });
    toast('Deleted', 'info');
    await loadAnalytics();
    loadTransactions(state.txPage);
  } catch (e) { toast(e.message, 'error'); }
}

// ─────────────────────────────────────────────────────────────────────────────
// Budgets
// FIX: fetch analytics alongside budgets so progress bars have spend data.
// ─────────────────────────────────────────────────────────────────────────────
async function loadBudgetsWithSpend() {
  document.getElementById('budget-grid').innerHTML =
    '<div class="loading-overlay"><div class="spinner"></div></div>';
  try {
    const [budgets] = await Promise.all([
      apiFetch('/budgets'),
      state.analytics ? Promise.resolve() : loadAnalytics(),
    ]);
    if (!budgets) return;
    state.budgets = budgets;
    document.getElementById('stat-budgets').textContent = budgets.filter(b=>b.is_active).length;
    renderBudgets(budgets);
  } catch (e) { toast(e.message, 'error'); }
}

function renderBudgets(budgets) {
  if (!budgets.length) {
    document.getElementById('budget-grid').innerHTML =
      '<div class="empty"><div class="empty-icon">🎯</div>No budgets yet. Set spending limits!</div>';
    return;
  }
  document.getElementById('budget-grid').innerHTML = budgets.map(b => {
    const spent = state.analytics?.top_categories?.find(c=>c.category===b.category);
    const spentAmt = spent ? parseFloat(spent.total) : 0;
    const pct = b.limit_amount > 0 ? Math.min((spentAmt/b.limit_amount)*100, 100) : 0;
    const cls = pct >= 100 ? 'danger' : pct >= 80 ? 'warning' : '';
    const over = spentAmt > parseFloat(b.limit_amount);
    return `
      <div class="glass budget-card">
        <div class="budget-card-header">
          <span class="budget-cat">${catIcon(b.category)} ${esc(b.category)}</span>
          <span class="budget-period">${b.period}</span>
        </div>
        <div class="progress-bar"><div class="progress-fill ${cls}" style="width:${pct.toFixed(1)}%"></div></div>
        <div class="budget-numbers">
          <span class="budget-spent">${fmt.currency(spentAmt)} spent</span>
          <span class="budget-limit">of ${fmt.currency(b.limit_amount)}</span>
        </div>
        ${over
          ? `<div class="overage-badge">⚠️ Over by ${fmt.currency(spentAmt - b.limit_amount)}</div>`
          : `<div style="font-size:.75rem;color:var(--text-muted);margin-top:6px">${fmt.currency(parseFloat(b.limit_amount)-spentAmt)} remaining · ${pct.toFixed(0)}% used</div>`
        }
        <div style="margin-top:12px">
          <button class="btn btn-danger btn-sm" onclick="deleteBudget('${b.id}')">Remove</button>
        </div>
      </div>`;
  }).join('');
}

async function createBudget(form) {
  try {
    await apiFetch('/budgets', { method:'POST', body:{
      category:     form.category.value,
      limit_amount: parseFloat(form.limit_amount.value),
      period:       form.period.value,
      start_date:   form.start_date.value,
    }});
    toast('Budget created ✅', 'success');
    closeModal('modal-add-budget');
    form.reset();
    document.querySelector('[name="start_date"]').valueAsDate = new Date();
    loadBudgetsWithSpend();
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteBudget(id) {
  if (!confirm('Remove this budget?')) return;
  try {
    await apiFetch(`/budgets/${id}`, { method:'DELETE' });
    toast('Budget removed', 'info');
    loadBudgetsWithSpend();
  } catch (e) { toast(e.message, 'error'); }
}

// ─────────────────────────────────────────────────────────────────────────────
// Analytics
// ─────────────────────────────────────────────────────────────────────────────
async function loadAnalytics() {
  try {
    const data = await apiFetch('/analytics?months=3');
    if (!data) return;
    state.analytics = data;
    updateStatCards();
    return data;
  } catch (e) { console.error('Analytics error:', e.message); }
}

function renderAnalyticsPanel() {
  const el = document.getElementById('analytics-content');
  if (!state.analytics) {
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
    loadAnalytics().then(d => { if(d) renderAnalyticsPanel(); });
    return;
  }
  const a = state.analytics;
  const topCats = a.top_categories?.length
    ? a.top_categories.map(c=>`
        <div class="ma-row">
          <span class="ma-month">${catIcon(c.category)} ${esc(c.category)}</span>
          <div class="ma-values">
            <span class="ma-total">${fmt.currency(c.total)}</span>
            <span style="color:var(--text-muted);font-size:.78rem">${parseFloat(c.percentage).toFixed(1)}%</span>
          </div>
        </div>`).join('')
    : '<div class="empty" style="padding:16px 0">No expense data yet</div>';

  const maRows = a.monthly_moving_avg?.length
    ? a.monthly_moving_avg.map(m=>`
        <div class="ma-row">
          <span class="ma-month">${m.month}</span>
          <div class="ma-values">
            <span class="ma-total">${fmt.currency(m.total_expense)}</span>
            <span class="ma-avg">${m.moving_avg!=null ? fmt.currency(m.moving_avg) : '<span style="color:var(--text-muted)">—</span>'}</span>
          </div>
        </div>`).join('')
    : '<div class="empty" style="padding:16px 0">Need 3+ months of data</div>';

  const burnHtml = a.burn_rate
    ? `<div class="glass burn-card">
        <div class="burn-label">🔥 Burn Rate Forecast</div>
        <div class="burn-value">${a.burn_rate.daily_rate>0?fmt.currency(a.burn_rate.daily_rate)+'/day':'—'}</div>
        <div class="burn-sub">${esc(a.burn_rate.forecast_label)}</div>
       </div>`
    : `<div class="glass burn-card"><div class="burn-label">🔥 Burn Rate</div>
       <div class="burn-sub text-muted" style="margin-top:8px">Set a budget to see your forecast.</div></div>`;

  const alerts = a.overage_alerts?.filter(o=>o.is_over)||[];
  const alertHtml = alerts.length ? `
    <div class="glass" style="padding:18px;margin-top:14px">
      <div class="section-title" style="margin-bottom:12px"><span class="icon">🚨</span> Budget Alerts</div>
      ${alerts.map(o=>`
        <div class="tx-item" style="background:rgba(248,113,113,0.06);border-radius:12px;margin-bottom:4px">
          <div class="tx-icon expense">⚠️</div>
          <div class="tx-body">
            <div class="tx-desc">${esc(o.category)} budget exceeded</div>
            <div class="tx-meta">Limit: ${fmt.currency(o.limit_amount)} · Spent: ${fmt.currency(o.total_spent)}</div>
          </div>
          <div class="tx-amount expense">+${fmt.currency(o.overage)}</div>
        </div>`).join('')}
    </div>` : '';

  el.innerHTML = `
    <div class="analytics-grid">
      <div class="glass" style="padding:22px">
        <div class="section-title" style="margin-bottom:14px"><span class="icon">📊</span> Top Spending Categories</div>
        ${topCats}
      </div>
      <div>${burnHtml}${alertHtml}</div>
    </div>
    <div class="glass mt-2" style="padding:22px">
      <div class="section-title" style="margin-bottom:14px">
        <span class="icon">📈</span> Monthly Expenses + 3-Month Moving Average
        <span style="font-size:.7rem;color:var(--text-muted);font-weight:400;margin-left:6px">(C++ engine)</span>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:20px;margin-bottom:10px;font-size:.76rem">
        <span style="color:var(--accent-red)">● Expenses</span>
        <span style="color:var(--accent-violet)">● 3-Mo MA</span>
      </div>
      ${maRows}
    </div>`;
}

function updateStatCards() {
  if (!state.analytics) return;
  const a = state.analytics;
  const net = parseFloat(a.net);
  document.getElementById('stat-income').textContent  = fmt.currency(a.total_income);
  document.getElementById('stat-expense').textContent = fmt.currency(a.total_expense);
  document.getElementById('stat-net').textContent     = (net>=0?'+':'') + fmt.currency(Math.abs(net));
  document.getElementById('stat-net').className       = `stat-value net ${net>=0?'positive':'negative'}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Modals
// ─────────────────────────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});

// ─────────────────────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const startDate = document.querySelector('[name="start_date"]');
  if (startDate) startDate.valueAsDate = new Date();

  document.getElementById('form-login').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target, btn = f.querySelector('[type=submit]');
    btn.textContent = 'Signing in…'; btn.disabled = true;
    try { await login(f.email.value, f.password.value); }
    catch (err) { toast(err.message, 'error'); }
    finally { btn.textContent = 'Sign In →'; btn.disabled = false; }
  });

  document.getElementById('form-register').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target, btn = f.querySelector('[type=submit]');
    btn.textContent = 'Creating…'; btn.disabled = true;
    try { await register(f.email.value, f.password.value, f.full_name.value); }
    catch (err) { toast(err.message, 'error'); }
    finally { btn.textContent = 'Create Account →'; btn.disabled = false; }
  });

  document.getElementById('form-add-tx').addEventListener('submit', async e => {
    e.preventDefault(); await createTransaction(e.target);
  });
  document.getElementById('form-add-budget').addEventListener('submit', async e => {
    e.preventDefault(); await createBudget(e.target);
  });

  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => showTab(t.dataset.tab)));
  document.getElementById('filter-type').addEventListener('change', e => { state.txFilter.type = e.target.value; loadTransactions(1); });
  document.getElementById('filter-category').addEventListener('change', e => { state.txFilter.category = e.target.value; loadTransactions(1); });
  document.getElementById('btn-logout').addEventListener('click', logout);

  if (state.token) {
    try { await loadCurrentUser(); await loadAnalytics(); enterDashboard(); }
    catch { _silentLogout(); }
  } else {
    showView('view-login');
  }
});
