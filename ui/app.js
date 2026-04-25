function $(id) {
  return document.getElementById(id);
}
const API_BASE = "http://127.0.0.1:8000";
let token = null;
let currentUser = null;
const autoIntervals = {}; // auctionId -> intervalId
const wsConnections = {}; // auctionId -> WebSocket
let adminSelectedCompany = null; // {id, name, cnpj, email}

function setAdminCompany(company) {
  // aceita id simples ou objeto completo
  if (typeof company === 'number') {
    adminSelectedCompany = { id: company, name: `#${company}` };
  } else {
    adminSelectedCompany = company;
  }
  const ui = $('userInfo');
  if (ui && currentUser && currentUser.is_admin) {
    const name = adminSelectedCompany?.name || `#${adminSelectedCompany?.id}`;
    ui.innerHTML = `Bem-vindo, <strong>${currentUser.full_name}</strong> — Admin • Empresa: ${name}`;
    show(ui);
  }
  const label = document.getElementById('selectedCompanyLabel');
  if (label && currentUser && currentUser.is_admin && adminSelectedCompany) {
    label.textContent = `Empresa: ${adminSelectedCompany.name} (#${adminSelectedCompany.id})`;
    label.classList.remove('hidden');
  }
  showDashboard();
  fetchAuctions();
}
window.setAdminCompany = setAdminCompany;

function clearAdminCompany() {
  adminSelectedCompany = null;
  const ui = $('userInfo');
  if (ui && currentUser) {
    const baseText = `Bem-vindo, <strong>${currentUser.full_name}</strong> — ${currentUser.company_name}`;
    ui.innerHTML = baseText;
  }
  const label = document.getElementById('selectedCompanyLabel');
  if (label) {
    label.textContent = '';
    label.classList.add('hidden');
  }
  fetchAuctions();
}
window.clearAdminCompany = clearAdminCompany;

// Persistent login functions
function saveLoginData(tokenData, userData) {
  localStorage.setItem('licita_token', tokenData);
  localStorage.setItem('licita_user', JSON.stringify(userData));
  token = tokenData;
  currentUser = userData;
}

function loadLoginData() {
  const savedToken = localStorage.getItem('licita_token');
  const savedUser = localStorage.getItem('licita_user');
  
  if (savedToken && savedUser) {
    try {
      token = savedToken;
      currentUser = JSON.parse(savedUser);
      return true;
    } catch (e) {
      clearLoginData();
      return false;
    }
  }
  return false;
}

function clearLoginData() {
  localStorage.removeItem('licita_token');
  localStorage.removeItem('licita_user');
  token = null;
  currentUser = null;
}

// Utilitário único de seleção por id
function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function setText(el, text) { el.textContent = text; }
function setFeedback(elId, text, type = 'info') {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = text || '';
  el.className = `feedback ${type}`;
  if (text) setTimeout(() => { el.textContent = ''; el.className = 'feedback'; }, 5000);
}

function onlyDigits(v) { return (v || '').replace(/\D/g, ''); }
function formatCnpj(v) {
  const d = onlyDigits(v).slice(0, 14);
  let out = '';
  for (let i = 0; i < d.length; i++) {
    out += d[i];
    if (i === 1 || i === 4) out += '.';
    else if (i === 7) out += '/';
    else if (i === 11) out += '-';
  }
  return out;
}
function validateCnpj(cnpj) {
  const d = onlyDigits(cnpj);
  if (d.length !== 14) return false;
  if (/^(\d)\1{13}$/.test(d)) return false;
  const calc = (base) => {
    let sum = 0;
    let pos = base.length - 7;
    for (let i = 0; i < base.length; i++) {
      sum += parseInt(base[i], 10) * pos--;
      if (pos < 2) pos = 9;
    }
    const res = sum % 11 < 2 ? 0 : 11 - (sum % 11);
    return res;
  };
  const base12 = d.substring(0, 12);
  const dig1 = calc(base12);
  if (dig1 !== parseInt(d[12], 10)) return false;
  const base13 = d.substring(0, 13);
  const dig2 = calc(base13);
  return dig2 === parseInt(d[13], 10);
}

function showLogin() {
  $('loginSection').classList.remove('hidden');
  $('dashboardSection').classList.add('hidden');
  $('userInfo').classList.add('hidden');
}

function showDashboard() {
  $('loginSection').classList.add('hidden');
  $('dashboardSection').classList.remove('hidden');
  if (currentUser) {
    $('userInfo').innerHTML = `
      <span>Olá, ${currentUser.full_name} (${currentUser.company_name})</span>
      <button id="logoutBtn" style="margin-left: 10px; padding: 4px 8px; background: #dc2626; color: white; border: none; border-radius: 4px; cursor: pointer;">Sair</button>
    `;
    $('userInfo').classList.remove('hidden');
    
    // Add logout functionality
    const logoutBtn = $('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', logout);
    }
  }
}

function logout() {
  clearLoginData();
  showLogin();
  $('auctionsBody').innerHTML = '';
  $('feedback').textContent = '';
}

async function loadAuctions(token) {
  try {
    await fetchAuctions();
  } catch (e) {
    console.error('Erro ao carregar leilões:', e);
  }
}

async function login(evt) {
  evt.preventDefault();
  const email = $('loginEmail').value.trim();
  const password = $('loginPassword').value;
  $('authError').textContent = '';
  const btn = document.querySelector('#loginFormElement button[type="submit"]');
  if (btn) { btn.disabled = true; btn.textContent = 'Entrando...'; }

  try {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erro ao autenticar' }));
      throw new Error(err.detail || 'Erro ao autenticar');
    }
    const data = await res.json();
    
    // Save login data to localStorage
    const userData = {
      email: email,
      full_name: data.user?.full_name || 'Usuário',
      company_name: data.user?.company_name || 'Empresa'
    };
    saveLoginData(data.access_token, userData);
    
    await fetchMe();
    await fetchAuctions();
    
    // Sincronização automática de licitações após login
    try {
      await syncLicitacoes(false); // false = não mostrar mensagem de sucesso
    } catch (syncError) {
      console.log('Erro na sincronização automática:', syncError.message);
    }
    
    showDashboard();
  } catch (e) {
    $('authError').style.color = '#b91c1c';
    $('authError').textContent = e.message;
  }
  if (btn) { btn.disabled = false; btn.textContent = 'Entrar'; }
}

async function signup(evt) {
  evt.preventDefault();
  $('authError').textContent = '';
  const btn = document.querySelector('#signupFormElement button[type="submit"]');
  if (btn) { btn.disabled = true; btn.textContent = 'Criando...'; }

  const signupData = {
    email: $('signupEmail').value.trim(),
    password: $('signupPassword').value,
    full_name: $('signupFullName').value.trim(),
    company_name: $('signupCompanyName').value.trim(),
    company_cnpj: $('signupCompanyCnpj').value.trim(),
    company_email: $('signupCompanyEmail').value.trim()
  };

  const cnpjValid = validateCnpj(signupData.company_cnpj);
  if (!cnpjValid) {
    $('authError').style.color = '#b91c1c';
    $('authError').textContent = 'CNPJ inválido. Verifique e tente novamente.';
    const cnpjEl = $('signupCompanyCnpj');
    cnpjEl.focus();
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(signupData)
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erro ao criar conta' }));
      throw new Error(err.detail || 'Erro ao criar conta');
    }

    $('loginEmail').value = signupData.email;
    $('loginPassword').value = signupData.password;
    showLoginForm();
    $('authError').style.color = '#065f46';
    $('authError').textContent = 'Conta criada com sucesso! Fazendo login...';
    setTimeout(() => {
      $('loginFormElement').dispatchEvent(new Event('submit'));
    }, 1000);

  } catch (e) {
    $('authError').style.color = '#b91c1c';
    $('authError').textContent = e.message;
  }
  if (btn) { btn.disabled = false; btn.textContent = 'Criar Conta'; }
}

function showSignupForm() {
  hide($('loginForm'));
  show($('signupForm'));
  $('authError').textContent = '';
}

function showLoginForm() {
  hide($('signupForm'));
  show($('loginForm'));
  $('authError').textContent = '';
}

async function fetchMe() {
  const res = await fetch(`${API_BASE}/me`, { headers: { 'Authorization': `Bearer ${token}` } });
  if (!res.ok) throw new Error('Falha ao obter usuário');
  currentUser = await res.json();
  const ui = $('userInfo');
  const baseText = `Bem-vindo, <strong>${currentUser.full_name}</strong> — ${currentUser.company_name}`;
  const suffix = currentUser.is_admin && adminSelectedCompany ? ` • Empresa: ${adminSelectedCompany.name} (#${adminSelectedCompany.id})` : '';
  ui.innerHTML = baseText + suffix;
  show(ui);
  // Mostrar Admin embutido apenas para administrador
  const adminPanel = document.getElementById('adminPanel');
  if (adminPanel) {
    if (currentUser.is_admin) {
      adminPanel.classList.remove('hidden');
      if (typeof initializeAdmin === 'function') {
        // Evita re-inicializar várias vezes
        if (!window.__admin_initialized) {
          window.__admin_initialized = true;
          initializeAdmin();
        }
      }
    } else {
      adminPanel.classList.add('hidden');
    }
  }
}

async function fetchAuctions() {
  const filterEl = document.getElementById('statusFilter');
  const status = filterEl ? filterEl.value : '';
  let url;
  if (currentUser && currentUser.is_admin && adminSelectedCompany) {
    const base = `${API_BASE}/admin/auctions?company_id=${encodeURIComponent(adminSelectedCompany.id)}`;
    url = status ? `${base}&status=${encodeURIComponent(status)}` : base;
  } else {
    url = status ? `${API_BASE}/auctions?status=${encodeURIComponent(status)}` : `${API_BASE}/auctions`;
  }
  // Garantir que há token válido
  if (!token) {
    const el = $('feedback');
    el.textContent = 'Sessão não autenticada. Faça login para ver os leilões.';
    el.classList.add('error');
    throw new Error('Não autenticado');
  }
  const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      if (body?.detail) detail = ` — ${body.detail}`;
    } catch {}
    const msg = `Falha ao obter leilões (HTTP ${res.status})${detail}`;
    const el = $('feedback');
    el.textContent = msg;
    el.classList.add('error');
    throw new Error(msg);
  }
  const auctions = await res.json();
  const portalEl = document.getElementById('portalFilter');
  const portal = portalEl ? portalEl.value : '';
  const filtered = portal ? auctions.filter(a => a.portal === portal) : auctions;
  renderAuctions(filtered);
}

function renderAuctions(auctions) {
  const tbody = $('auctionsBody');
  tbody.innerHTML = '';
  auctions.forEach(a => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${a.id}</td>
      <td>${a.portal}</td>
      <td>${a.item}</td>
      <td id="price-${a.id}">R$ ${a.current_price.toFixed(2)}</td>
      <td>${a.status}</td>
      <td>
        <input type="number" step="0.01" id="floor-${a.id}" value="${Math.max(0, a.current_price - 1).toFixed(2)}" />
      </td>
      <td>
        <input type="number" step="0.01" id="dec-${a.id}" value="0.01" />
      </td>
      <td>
        <select id="strat-${a.id}">
          <option value="incremental">incremental</option>
          <option value="agressivo">agressivo</option>
          <option value="conservador">conservador</option>
        </select>
      </td>
      <td>
        <div class="btns">
          <button class="btn btn-primary" id="bid-${a.id}">Lance</button>
          <button class="btn btn-secondary" id="play-${a.id}">Play</button>
          <button class="btn btn-danger" id="stop-${a.id}">Stop</button>
          <button class="btn" id="reset-${a.id}">Reset</button>
          <button class="btn" id="hist-${a.id}">Histórico</button>
          <button class="btn" id="room-${a.id}">Sala</button>
        </div>
        <div class="row-feedback" id="fb-${a.id}"></div>
        <div class="history hidden" id="history-${a.id}"></div>
        <div class="history hidden" id="dispute-${a.id}"></div>
      </td>
    `;
    tbody.appendChild(tr);

    $('bid-' + a.id).onclick = () => manualBid(a.id);
    $('play-' + a.id).onclick = () => startAutoBid(a.id);
    $('stop-' + a.id).onclick = () => stopAutoBid(a.id);
    $('reset-' + a.id).onclick = () => resetAuction(a.id);
    $('hist-' + a.id).onclick = () => toggleHistory(a.id);
    $('room-' + a.id).onclick = () => openDispute(a.id);
  });
}

function readInputs(id) {
  const floor = parseFloat($('floor-' + id).value);
  const dec = parseFloat($('dec-' + id).value);
  const strat = $('strat-' + id).value;
  return { floor_price: floor, decrement: dec, strategy: strat };
}

async function manualBid(auctionId) {
  const inputs = readInputs(auctionId);
  const fb = $('fb-' + auctionId);
  try {
    const isAdminScope = currentUser && currentUser.is_admin && adminSelectedCompany;
    const endpoint = isAdminScope ? `${API_BASE}/admin/bid` : `${API_BASE}/bid`;
    const payload = isAdminScope ? { auction_id: auctionId, company_id: adminSelectedCompany.id, ...inputs } : { auction_id: auctionId, ...inputs };
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao enviar lance');

    setText($('price-' + auctionId), `R$ ${data.new_bid.toFixed(2)}`);
    fb.textContent = data.accepted ? 'Lance aceito' : (data.reason || 'Lance recusado');
    await refreshAuctionRow(auctionId);
  } catch (e) {
    fb.textContent = e.message;
  }
}

async function refreshAuctionRow(auctionId) {
  const isAdminScope = currentUser && currentUser.is_admin && adminSelectedCompany;
  const url = isAdminScope ? `${API_BASE}/admin/auctions/${auctionId}` : `${API_BASE}/auctions/${auctionId}`;
  const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
  if (!res.ok) return;
  const a = await res.json();
  setText($('price-' + auctionId), `R$ ${a.current_price.toFixed(2)}`);
}

function openDispute(auctionId) {
  const panel = document.getElementById('dispute-' + auctionId);
  const isHidden = panel.classList.contains('hidden');
  if (!isHidden) {
    // Fechar sala e desconectar
    panel.classList.add('hidden');
    panel.innerHTML = '';
    if (wsConnections[auctionId]) {
      try { wsConnections[auctionId].close(); } catch (e) {}
      delete wsConnections[auctionId];
    }
    return;
  }
  panel.classList.remove('hidden');
  panel.innerHTML = `<div style="padding:8px;border:1px solid #ccc;margin-top:6px">
    <div><strong>Sala de Disputa #${auctionId}</strong></div>
    <div id="room-feed-${auctionId}" style="max-height:120px;overflow:auto;font-size:12px;color:#333;margin-top:6px"></div>
    <div style="margin-top:6px">
      <button class="btn" id="room-close-${auctionId}">Fechar</button>
    </div>
  </div>`;
  document.getElementById('room-close-' + auctionId).onclick = () => openDispute(auctionId);
  const feed = document.getElementById('room-feed-' + auctionId);
  const wsUrl = `ws://127.0.0.1:8000/ws/auction/${auctionId}?token=${encodeURIComponent(token)}`;
  try {
    const ws = new WebSocket(wsUrl);
    wsConnections[auctionId] = ws;
    ws.onopen = () => {
      const div = document.createElement('div');
      div.textContent = 'Conectado à sala.';
      feed.appendChild(div);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.auction && typeof msg.auction.current_price === 'number') {
          setText($('price-' + auctionId), `R$ ${msg.auction.current_price.toFixed(2)}`);
        }
        const div = document.createElement('div');
        const label = msg.event || 'evento';
        const price = msg.auction && msg.auction.current_price;
        div.textContent = `[${label}] preço atual: ${price !== undefined ? 'R$ ' + price.toFixed(2) : '-'}${msg.message ? ' - ' + msg.message : ''}`;
        feed.appendChild(div);
        feed.scrollTop = feed.scrollHeight;
      } catch (e) {
        const div = document.createElement('div');
        div.textContent = 'Mensagem inválida';
        feed.appendChild(div);
      }
    };
    ws.onerror = () => {
      const div = document.createElement('div');
      div.textContent = 'Erro na conexão da sala.';
      feed.appendChild(div);
    };
    ws.onclose = () => {
      const div = document.createElement('div');
      div.textContent = 'Sala desconectada.';
      feed.appendChild(div);
    };
  } catch (e) {
    const div = document.createElement('div');
    div.textContent = 'Falha ao abrir sala: ' + e.message;
    feed.appendChild(div);
  }
}

function startAutoBid(auctionId) {
  if (autoIntervals[auctionId]) return; // já rodando
  const fb = $('fb-' + auctionId);
  fb.textContent = 'Auto-lance iniciado';
  autoIntervals[auctionId] = setInterval(async () => {
    const isAdminScope = currentUser && currentUser.is_admin && adminSelectedCompany;
    const url = isAdminScope ? `${API_BASE}/admin/auctions/${auctionId}` : `${API_BASE}/auctions/${auctionId}`;
    const resA = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
    if (!resA.ok) return;
    const a = await resA.json();
    if (a.status !== 'running') { fb.textContent = 'Leilão não está em execução'; return stopAutoBid(auctionId); }
    await manualBid(auctionId);
    // Para quando atingir o piso
    const inputs = readInputs(auctionId);
    const currentText = $('price-' + auctionId).textContent.replace('R$', '').trim();
    const current = parseFloat(currentText.replace(',', '.')) || a.current_price;
    if (current <= inputs.floor_price) { fb.textContent = 'Atingiu o piso'; stopAutoBid(auctionId); }
  }, 1000);
}

function stopAutoBid(auctionId) {
  const id = autoIntervals[auctionId];
  if (id) { clearInterval(id); delete autoIntervals[auctionId]; }
  const fb = $('fb-' + auctionId);
  fb.textContent = 'Auto-lance parado';
}

async function resetAuction(auctionId) {
  const isAdminScope = currentUser && currentUser.is_admin && adminSelectedCompany;
  const url = isAdminScope ? `${API_BASE}/admin/auctions/${auctionId}/reset` : `${API_BASE}/auctions/${auctionId}/reset`;
  const res = await fetch(url, {
    method: 'POST', headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) return;
  const a = await res.json();
  setText($('price-' + auctionId), `R$ ${a.current_price.toFixed(2)}`);
  $('fb-' + auctionId).textContent = 'Reset realizado';
}

async function toggleHistory(auctionId) {
  const box = $('history-' + auctionId);
  if (!box.classList.contains('hidden')) { box.classList.add('hidden'); return; }
  const isAdminScope = currentUser && currentUser.is_admin && adminSelectedCompany;
  const url = isAdminScope ? `${API_BASE}/admin/history/${auctionId}` : `${API_BASE}/history/${auctionId}`;
  const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
  if (!res.ok) return;
  const items = await res.json();
  box.innerHTML = items.slice(-10).map(h => `
    <div class="history-item">
      <strong>${h.timestamp}</strong> • ${h.portal}
      <br/>Prev: R$ ${h.prev_price.toFixed(2)} ⇒ Prop.: R$ ${h.proposed.toFixed(2)} • ${h.accepted ? 'Aceito' : 'Recusado'}
      ${h.reason ? `<br/><em>${h.reason}</em>` : ''}
    </div>
  `).join('');
  box.classList.remove('hidden');
}

// Sincronizar licitações:
// - Se admin com empresa selecionada: importa licitações para essa empresa
// - Caso contrário: sincroniza para a empresa do usuário logado
async function syncLicitacoes(showMessage = true) {
  try {
    let data;
    if (currentUser && currentUser.is_admin && adminSelectedCompany) {
      const res = await fetch(`${API_BASE}/admin/auctions/import`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ cnpj: adminSelectedCompany.cnpj, quantity: 4, portal: 'Comprasnet' })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro ao importar licitações para a empresa selecionada' }));
        throw new Error(err.detail || 'Erro ao importar licitações');
      }
      data = await res.json();
    } else {
      const res = await fetch(`${API_BASE}/sync/licitacoes`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro na sincronização' }));
        throw new Error(err.detail || 'Erro na sincronização');
      }
      data = await res.json();
    }
    if (showMessage) {
      let msg = data.message || 'Licitações sincronizadas';
      if (currentUser && currentUser.is_admin && adminSelectedCompany && Array.isArray(data.created)) {
        msg = `${msg} — ${data.created.length} novas para ${adminSelectedCompany.name}`;
      } else if (typeof data.novas_adicionadas === 'number' && typeof data.total_encontradas === 'number') {
        msg = `${msg} — ${data.novas_adicionadas} novas de ${data.total_encontradas} encontradas`;
      }
      setFeedback('feedback', msg, 'success');
    }
    await fetchAuctions();
    return data;
  } catch (e) {
    if (showMessage) setFeedback('feedback', `Erro na sincronização: ${e.message}`, 'error');
    throw e;
  }
}

// Health check indicator
async function checkHealth() {
  const el = document.getElementById("healthStatus");
  if (!el) return;
  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (res.ok) {
      el.textContent = "API: online";
      el.classList.remove("status-offline");
      el.classList.add("status-online");
    } else {
      el.textContent = "API: offline";
      el.classList.remove("status-online");
      el.classList.add("status-offline");
    }
  } catch (e) {
    el.textContent = "API: offline";
    el.classList.remove("status-online");
    el.classList.add("status-offline");
  }
}

// Auto-login and initialization
function initializeApp() {
  checkHealth();
  
  // Try to auto-login from saved data
  if (loadLoginData()) {
    // Validar token e status com /me
    fetchMe()
      .then(() => {
        showDashboard();
        loadAuctions(token);
      })
      .catch(async (e) => {
        console.warn('Auto-login bloqueado ou inválido:', e);
        clearLoginData();
        showLogin();
        const msg = (e && e.message) ? e.message : 'Acesso bloqueado ou sessão expirada';
        const el = $('authError');
        el.textContent = msg;
        el.classList.add('error');
      });
  } else {
    showLogin();
  }
}

// run on page load
document.addEventListener("DOMContentLoaded", initializeApp);

$('loginFormElement').addEventListener('submit', login);
$('refreshAuctions').addEventListener('click', fetchAuctions);
$('syncLicitacoes').addEventListener('click', () => syncLicitacoes(true));
const syncBtn = document.getElementById('syncLicitacoes');
if (syncBtn) {
  syncBtn.addEventListener('click', async () => {
    syncBtn.disabled = true;
    const original = syncBtn.textContent;
    syncBtn.textContent = 'Sincronizando...';
    try { await syncLicitacoes(true); } finally {
      syncBtn.disabled = false;
      syncBtn.textContent = original;
    }
  });
}
const cnpjInput = document.getElementById('signupCompanyCnpj');
if (cnpjInput) {
  cnpjInput.addEventListener('input', (e) => {
    e.target.value = formatCnpj(e.target.value);
  });
}
const statusFilterEl = document.getElementById('statusFilter');
if (statusFilterEl) {
  statusFilterEl.addEventListener('change', () => fetchAuctions());
}
const portalFilterEl = document.getElementById('portalFilter');
if (portalFilterEl) {
  portalFilterEl.addEventListener('change', () => fetchAuctions());
}
const labelEl = document.getElementById('selectedCompanyLabel');
if (labelEl) {
  labelEl.style.cursor = 'pointer';
  labelEl.title = 'Clique para importar licitações desta empresa';
  const triggerImport = async () => {
    if (!adminSelectedCompany) return;
    setFeedback('feedback', `Importando licitações para ${adminSelectedCompany.name}...`, 'info');
    try { await syncLicitacoes(true); } catch {}
  };
  labelEl.addEventListener('click', triggerImport);
  labelEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); triggerImport(); }
  });
}
console.log("Frontend carregado com sucesso");
