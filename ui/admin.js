const BASE = window.API_BASE || "http://127.0.0.1:8000";
function setStatus(text, ok) {
  const el = document.getElementById("admin-status");
  if (!el) return;
  el.textContent = text;
  el.style.background = ok ? "#e6ffed" : "#ffefef";
  el.style.color = ok ? "#03610e" : "#8a0215";
  el.style.border = ok ? "1px solid #b7f5c4" : "1px solid #ffd0d0";
}

function friendlyStatus(status) {
  if (status === 401) return "Não autorizado. Faça login com uma conta de administrador.";
  if (status === 403) return "Acesso negado. Conta não tem privilégios de administrador.";
  return `Erro ${status}`;
}

async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/health`, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Falha de saúde");
    setStatus("API: online", true);
  } catch (e) {
    setStatus("API: offline", false);
  }
}

// Usa token JWT salvo pelo app principal
function getAuthToken() {
  return localStorage.getItem("licita_token") || null;
}

function setMessage(msg) {
  const el = document.getElementById("adminMessage");
  if (el) el.textContent = msg || "";
}

async function fetchCompanies() {
  const token = getAuthToken();
  if (!token) {
    setMessage("Faça login para acessar o Painel Admin.");
    return;
  }
  setMessage("Carregando empresas...");
  try {
    const res = await fetch(`${BASE}/admin/companies`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
    if (!res.ok) throw new Error(friendlyStatus(res.status));
    const companies = await res.json();
    renderCompanies(companies);
    setMessage(`Total de empresas: ${companies.length}`);
  } catch (e) {
    setMessage(`Erro ao carregar empresas: ${e.message}`);
  }
}

function renderCompanies(companies) {
  const tbody = document.querySelector("#companiesTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  companies.forEach((c) => {
    const tr = document.createElement("tr");
    const payPill = `<span class="pill ${c.is_paid ? "active" : "blocked"}">${c.is_paid ? "Pago" : "Em atraso"}</span>`;
    const created = new Date(c.created_at).toLocaleString();
    tr.innerHTML = `
      <td>${c.id}</td>
      <td>${c.name}</td>
      <td>${c.cnpj}</td>
      <td>${c.email}</td>
      <td>${payPill}</td>
      <td>${created}</td>
      <td>
        <button class="btn pay-toggle" data-id="${c.id}" data-paid="${c.is_paid ? "1" : "0"}">${c.is_paid ? "Marcar em atraso" : "Marcar como pago"}</button>
        <button class="btn open-auctions" data-id="${c.id}" data-name="${c.name}" data-cnpj="${c.cnpj}" data-email="${c.email}" style="margin-left:8px;">Abrir Leilões</button>
        <button class="btn btn-danger delete-company" data-id="${c.id}" style="margin-left:8px;">Excluir</button>
      </td>
    `;
    if (!c.is_paid) tr.classList.add("company-overdue");
    tbody.appendChild(tr);
  });
  // Bind para alternar pagamento
  document.querySelectorAll(".pay-toggle").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const id = parseInt(e.currentTarget.getAttribute("data-id"), 10);
      const paid = e.currentTarget.getAttribute("data-paid") === "1";
      await updateCompanyPayment(id, !paid);
    });
  });
  // Bind para abrir leilões no contexto Admin, sem trocar login
  document.querySelectorAll(".open-auctions").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const el = e.currentTarget;
      const id = parseInt(el.getAttribute("data-id"), 10);
      const name = el.getAttribute("data-name");
      const cnpj = el.getAttribute("data-cnpj");
      const email = el.getAttribute("data-email");
      try {
        if (typeof window.setAdminCompany === "function") {
          window.setAdminCompany({ id, name, cnpj, email });
          setMessage(`Empresa selecionada: ${name} (#${id}). Dashboard exibindo leilões da empresa.`);
        } else {
          await selectCompanyAuctions(id);
        }
      } catch (err) {
        setMessage(`Erro ao selecionar empresa: ${err.message}`);
      }
    });
  });
  // Bind excluir empresa
  document.querySelectorAll(".delete-company").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const id = parseInt(e.currentTarget.getAttribute("data-id"), 10);
      await deleteCompany(id);
    });
  });
}

// Atualiza pagamento por empresa
async function updateCompanyPayment(companyId, isPaid) {
  const token = getAuthToken();
  if (!token) {
    setMessage("Faça login.");
    return;
  }
  try {
    const url = `${BASE}/admin/companies/${companyId}/payment`;
    const res = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ is_paid: !!isPaid })
    });
    if (!res.ok) throw new Error(friendlyStatus(res.status));
    await fetchCompanies();
    setMessage(`Pagamento marcado como ${isPaid ? "pago" : "em atraso"} para a empresa.`);
  } catch (e) {
    setMessage(`Erro ao atualizar pagamento: ${e.message}`);
  }
}

// Faz login como o cliente da empresa usando senha padrão e abre leilões
async function impersonateCompany(email) {
  try {
    setMessage(`Entrando como cliente: ${email}…`);
    const body = new URLSearchParams({ username: email, password: "cliente123" });
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Erro ao autenticar cliente" }));
      throw new Error(err.detail || "Erro ao autenticar cliente");
    }
    const data = await res.json();
    // Reusa funções globais do app para trocar o contexto
    const userData = { email, full_name: "Cliente", company_name: "Empresa" };
    if (typeof saveLoginData === "function") {
      saveLoginData(data.access_token, userData);
    } else {
      localStorage.setItem('licita_token', data.access_token);
      localStorage.setItem('licita_user', JSON.stringify(userData));
    }
    if (typeof fetchMe === "function") await fetchMe();
    if (typeof fetchAuctions === "function") await fetchAuctions();
    if (typeof showDashboard === "function") showDashboard();
    setMessage(`Contexto alterado para o cliente ${email}.`);
  } catch (e) {
    setMessage(`Falha ao abrir leilões do cliente: ${e.message}`);
  }
}

async function selectCompanyAuctions(companyId) {
  try {
    if (typeof window.setAdminCompany === "function") {
      window.setAdminCompany(companyId);
      setMessage(`Empresa #${companyId} selecionada. Dashboard exibindo leilões da empresa.`);
    } else {
      setMessage("Função de seleção de empresa indisponível no app.");
    }
  } catch (e) {
    setMessage(`Erro ao selecionar empresa: ${e.message}`);
  }
}

async function deleteCompany(companyId) {
  const token = getAuthToken();
  if (!token) return setMessage("Faça login.");
  const ok = window.confirm(`Confirma excluir a empresa #${companyId}? Esta ação remove usuários, leilões e histórico relacionados.`);
  if (!ok) return;
  try {
    const res = await fetch(`${BASE}/admin/companies/${companyId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
    if (!res.ok) throw new Error(friendlyStatus(res.status));
    const info = await res.json();
    setMessage(info.message || "Empresa excluída.");
    // Se empresa selecionada, limpar contexto do dashboard
    try {
      if (typeof window.clearAdminCompany === "function") {
        window.clearAdminCompany();
      }
    } catch {}
    await fetchCompanies();
  } catch (e) {
    setMessage(`Erro ao excluir empresa: ${e.message}`);
  }
}

function bindEvents() {
  const refreshBtn = document.getElementById("refreshBtn");
  refreshBtn?.addEventListener("click", () => fetchCompanies());
  document.getElementById("btnImportAuctions")?.addEventListener("click", importAuctions);
}

// Removido fluxo antigo de pagamento por usuário; tudo via empresa

async function createCompany() {
  const token = getAuthToken();
  if (!token) return setMessage("Faça login para criar empresa.");
  const company_name = document.getElementById("adminCompanyName")?.value.trim();
  const company_cnpj = document.getElementById("adminCompanyCnpj")?.value.trim();
  const company_email = document.getElementById("adminCompanyEmail")?.value.trim();
  const comprasnet_username = document.getElementById("comprasnetUser")?.value.trim();
  const comprasnet_password = document.getElementById("comprasnetPass")?.value.trim();
  if (!company_name || !company_cnpj || !company_email || !comprasnet_username || !comprasnet_password) {
    return setMessage("Preencha todos os campos para criar a empresa.");
  }
  // Validação simples de email e CNPJ para evitar 422 do backend
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(company_email);
  const cnpjDigits = (company_cnpj || "").replace(/\D/g, "");
  if (!emailOk) {
    return setMessage("Email inválido. Informe um email no formato nome@dominio.com.");
  }
  if (cnpjDigits.length !== 14) {
    return setMessage("CNPJ inválido. Informe 14 dígitos (com ou sem máscara).");
  }
  try {
    const btn = document.getElementById("createCompanyBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Cadastrando..."; }
    const res = await fetch(`${BASE}/admin/companies/create`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ company_name, company_cnpj, company_email, comprasnet_username, comprasnet_password })
    });
    if (!res.ok) {
      let errMsg = friendlyStatus(res.status);
      try {
        const errBody = await res.json();
        if (errBody?.detail) errMsg += `: ${errBody.detail}`;
      } catch {}
      throw new Error(errMsg);
    }
    const company = await res.json();
    setMessage(`Empresa criada: ${company.name}. Usuário padrão criado: ${company.email} / senha temporária: cliente123.`);
    // Importa licitações iniciais para a empresa
    try {
      await fetch(`${BASE}/admin/auctions/import`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ cnpj: company.cnpj, quantity: 3, portal: "Comprasnet" })
      });
    } catch (e) {
      console.warn("Falha ao importar licitações iniciais:", e);
    }
    try {
      if (typeof window.setAdminCompany === "function") {
        window.setAdminCompany(company);
      }
    } catch {}
    // Limpa campos
    ["adminCompanyName","adminCompanyCnpj","adminCompanyEmail","comprasnetUser","comprasnetPass"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    await fetchCompanies();
  } catch (e) {
    setMessage(`Erro ao criar empresa: ${e.message}`);
  } finally {
    const btn = document.getElementById("createCompanyBtn");
    if (btn) { btn.disabled = false; btn.textContent = "Cadastrar Empresa"; }
  }
}

function initializeAdmin() {
  checkHealth();
  bindEvents();
  fetchCompanies();
  document.getElementById("createCompanyBtn")?.addEventListener("click", createCompany);
}
// A inicialização do Admin ocorre dentro do fluxo de login do app principal

async function importAuctions() {
  const token = getAuthToken();
  if (!token) return setMessage("Faça login.");
  const email = document.getElementById("importEmail")?.value.trim();
  const cnpj = document.getElementById("importCnpj")?.value.trim();
  if (!email && !cnpj) return setMessage("Informe email do usuário ou CNPJ.");
  try {
    const btn = document.getElementById("btnImportAuctions");
    if (btn) { btn.disabled = true; btn.textContent = "Importando..."; }
    const payload = { quantity: 3, portal: "Comprasnet" };
    if (email) payload.email = email;
    if (cnpj) payload.cnpj = cnpj;
    const res = await fetch(`${BASE}/admin/auctions/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(friendlyStatus(res.status));
    const data = await res.json();
    setMessage(data.message || "Licitações importadas.");
  } catch (e) {
    setMessage(`Erro ao importar licitações: ${e.message}`);
  } finally {
    const btn = document.getElementById("btnImportAuctions");
    if (btn) { btn.disabled = false; btn.textContent = "Importar Licitações"; }
  }
}
