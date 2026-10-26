/* Kharcha front end.
 *
 * Plain JavaScript, no framework. The page talks to the FastAPI backend
 * with fetch(): it logs in at /auth/token, keeps the JWT in localStorage,
 * and sends it as "Authorization: Bearer <token>" on every request,
 * exactly as Swagger's Authorize button does.
 */
"use strict";

/* ================= Helpers ================= */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const TOKEN_KEY = "kharcha_token";
const VIEWS = ["dashboard", "expenses", "categories"];
const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const METHOD_LABELS = { upi: "UPI", card: "Card", cash: "Cash", netbanking: "Netbanking", other: "Other" };
const DOT_COLORS = ["#d9822b", "#2f8f6b", "#4a6fd1", "#b8487a", "#7a5bc7", "#2c9bb5", "#9a8a2a", "#c2513a"];

const now = new Date();
const state = {
  token: null,
  user: null,
  categories: [],
  view: null,
  month: { year: now.getFullYear(), month: now.getMonth() + 1 },
  expenses: { offset: 0, limit: 20, total: 0, items: [] },
  editingExpense: null,
  editingCategory: null,
};

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const money = (value) => inr.format(Number(value || 0));

/** Short Indian-style amounts for chart labels: ₹950, ₹14.5k, ₹2.3L, ₹1.1Cr */
function moneyShort(value) {
  const trim = (n) => n.toFixed(1).replace(/\.0$/, "");
  if (value >= 1e7) return `₹${trim(value / 1e7)}Cr`;
  if (value >= 1e5) return `₹${trim(value / 1e5)}L`;
  if (value >= 1e3) return `₹${trim(value / 1e3)}k`;
  return `₹${Math.round(value)}`;
}

/** Escape text before putting it into innerHTML (stops HTML injection). */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function localISO(date) {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

function formatDate(iso, withYear = true) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}),
  });
}

function dotColor(categoryId) {
  return categoryId == null ? "var(--muted)" : DOT_COLORS[categoryId % DOT_COLORS.length];
}

function categoryChip(category) {
  if (!category) return `<span class="chip none">Uncategorised</span>`;
  return `<span class="chip"><i class="dot" style="background:${dotColor(category.id)}"></i>${esc(category.name)}</span>`;
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
}

function showFormError(form, message) {
  const el = $("[data-error]", form);
  el.textContent = message || "";
  el.hidden = !message;
}

function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

/* ================= API ================= */

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** Turn FastAPI's error body into one readable message. */
function describeError(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) {
    // 422 from Pydantic: [{loc: ["body", "amount"], msg: "..."}, ...]
    return data.detail.map((e) => {
      const field = e.loc.filter((part) => part !== "body" && part !== "query").join(".");
      return field ? `${field}: ${e.msg}` : e.msg;
    }).join("\n");
  }
  return `Request failed (${status})`;
}

async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  let body;
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (form) {
    // /auth/token expects form data, not JSON (OAuth2PasswordRequestForm)
    body = new URLSearchParams(form);
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (json !== undefined) {
    body = JSON.stringify(json);
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(path, { method, headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the server. Is uvicorn running?");
  }

  if (response.status === 401 && state.token) {
    logout("Your session has expired. Please log in again.");
    throw new ApiError(401, "Not logged in");
  }
  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, describeError(data, response.status));
  return data;
}

function setToken(token) {
  state.token = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage blocked: stay logged in for this tab only */ }
}

/* ================= Auth ================= */

function showAuth() {
  $("#app-view").hidden = true;
  $("#auth-view").hidden = false;
  $("#login-username").focus();
}

function setAuthTab(tab) {
  $$("[data-auth-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.authTab === tab)));
  $("#login-form").hidden = tab !== "login";
  $("#register-form").hidden = tab !== "register";
  showFormError($("#login-form"), "");
  showFormError($("#register-form"), "");
}

async function login(username, password) {
  const data = await api("/auth/token", { method: "POST", form: { username, password } });
  setToken(data.access_token);
  await startApp();
}

function logout(message) {
  setToken(null);
  state.user = null;
  $$("dialog[open]").forEach((d) => d.close());
  showAuth();
  if (message) toast(message, true);
}

async function startApp() {
  state.user = await api("/auth/me");
  $("#user-name").textContent = state.user.full_name || state.user.username;
  $("#auth-view").hidden = true;
  $("#app-view").hidden = false;
  await loadCategories();
  if (VIEWS.includes(location.hash.replace(/^#\//, ""))) route();
  else location.hash = "#/dashboard"; // triggers route() via hashchange
}

/* ================= Routing ================= */

function route() {
  if (!state.user) return;
  let view = location.hash.replace(/^#\//, "");
  if (!VIEWS.includes(view)) view = "dashboard";
  state.view = view;
  VIEWS.forEach((v) => { $(`#view-${v}`).hidden = v !== view; });
  $$("[data-nav]").forEach((a) => {
    if (a.dataset.nav === view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  refreshView();
}

function refreshView() {
  const loaders = { dashboard: loadDashboard, expenses: loadExpenses, categories: loadCategoriesView };
  loaders[state.view]().catch((err) => {
    if (err.status !== 401) toast(err.message, true);
  });
}

/* ================= Categories (shared) ================= */

async function loadCategories() {
  state.categories = await api("/categories");
  fillCategorySelects();
}

function fillCategorySelects() {
  const options = state.categories
    .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  $("#e-category").innerHTML = `<option value="">No category</option>${options}`;

  const filter = $("#f-category");
  const current = filter.value;
  filter.innerHTML = `<option value="">All categories</option><option value="none">Uncategorised</option>${options}`;
  filter.value = current;
  if (filter.value !== current) filter.value = "";
}

/* ================= Dashboard ================= */

function isCurrentMonth({ year, month }) {
  const today = new Date();
  return year === today.getFullYear() && month === today.getMonth() + 1;
}

function shiftMonth({ year, month }, delta) {
  const d = new Date(year, month - 1 + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

async function loadDashboard() {
  const { year, month } = state.month;
  const prev = shiftMonth(state.month, -1);
  $("#dash-month").textContent = `${MONTHS[month - 1]} ${year}`;
  $('[data-action="next-month"]').disabled = isCurrentMonth(state.month);

  const [report, prevReport, yearly, recent] = await Promise.all([
    api(`/reports/monthly?year=${year}&month=${month}`),
    api(`/reports/monthly?year=${prev.year}&month=${prev.month}`),
    api(`/reports/yearly?year=${year}`),
    api("/expenses?limit=6&sort=newest"),
  ]);

  renderStats(report, prevReport, prev);
  renderBudgets(report);
  renderYearChart(yearly);
  renderRecent(recent.items);
}

function renderStats(report, prevReport, prev) {
  const { year, month } = state.month;
  const total = Number(report.total);
  const prevTotal = Number(prevReport.total);

  $("#stat-total").textContent = money(total);
  $("#stat-count").textContent = report.count;

  const daysInMonth = new Date(year, month, 0).getDate();
  const daysSoFar = isCurrentMonth(state.month) ? new Date().getDate() : daysInMonth;
  $("#stat-daily").textContent = money(total / daysSoFar);

  const prevName = MONTHS[prev.month - 1];
  let compare;
  if (prevTotal > 0) {
    const pct = Math.round(((total - prevTotal) / prevTotal) * 100);
    compare = pct === 0 ? `Same as ${prevName}` : `${Math.abs(pct)}% ${pct > 0 ? "more" : "less"} than ${prevName}`;
  } else {
    compare = total > 0 ? `Nothing recorded in ${prevName}` : "No expenses yet";
  }
  $("#stat-compare").textContent = compare;

  // "Budget used" only counts categories that have a budget.
  const budgeted = state.categories.filter((c) => c.monthly_budget !== null);
  const budgetIds = new Set(budgeted.map((c) => c.id));
  const budgetTotal = budgeted.reduce((sum, c) => sum + Number(c.monthly_budget), 0);
  const spentInBudgeted = report.by_category
    .filter((r) => budgetIds.has(r.category_id))
    .reduce((sum, r) => sum + Number(r.total), 0);
  const overCount = report.by_category.filter((r) => r.over_budget).length;

  const note = $("#stat-budget-note");
  if (budgetTotal > 0) {
    $("#stat-budget").textContent = `${Math.round((spentInBudgeted / budgetTotal) * 100)}%`;
    note.textContent = overCount
      ? `${overCount} ${overCount === 1 ? "category" : "categories"} over budget`
      : `${money(spentInBudgeted)} of ${money(budgetTotal)}`;
    note.classList.toggle("bad", overCount > 0);
  } else {
    $("#stat-budget").textContent = "—";
    note.textContent = "No budgets set";
    note.classList.remove("bad");
  }
}

function renderBudgets(report) {
  const byId = new Map(report.by_category.map((r) => [r.category_id, r]));
  const rows = [];
  for (const c of state.categories) {
    const spent = byId.has(c.id) ? Number(byId.get(c.id).total) : 0;
    const budget = c.monthly_budget === null ? null : Number(c.monthly_budget);
    if (budget === null && spent === 0) continue;
    rows.push({ id: c.id, name: c.name, spent, budget });
  }
  if (byId.has(null)) rows.push({ id: null, name: "Uncategorised", spent: Number(byId.get(null).total), budget: null });
  rows.sort((a, b) => b.spent - a.spent);

  const list = $("#budget-list");
  if (!rows.length) {
    list.innerHTML = `<li class="empty-inline">Nothing spent this month yet. Give your categories a monthly budget and they'll show up here.</li>`;
    return;
  }

  list.innerHTML = rows.map((row) => {
    const name = `<span class="budget-name"><i class="dot" style="background:${dotColor(row.id)}"></i>${esc(row.name)}</span>`;
    if (row.budget === null) {
      return `<li>
        <div class="budget-top">${name}<span class="budget-figures"><b>${money(row.spent)}</b></span></div>
        <div class="budget-state">No budget set</div>
      </li>`;
    }
    const ratio = row.budget > 0 ? row.spent / row.budget : (row.spent > 0 ? Infinity : 0);
    const level = ratio > 1 ? "over" : ratio >= 0.8 ? "warn" : "";
    const width = Math.min(ratio, 1) * 100;
    const stateText = ratio > 1
      ? `${money(row.spent - row.budget)} over budget`
      : `${money(row.budget - row.spent)} left`;
    return `<li>
      <div class="budget-top">${name}<span class="budget-figures"><b>${money(row.spent)}</b> of ${money(row.budget)}</span></div>
      <div class="bar ${level}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(Math.min(ratio, 9.99) * 100)}"><i style="width:${width}%"></i></div>
      <div class="budget-state ${ratio > 1 ? "over" : ""}">${stateText}</div>
    </li>`;
  }).join("");
}

function renderYearChart(yearly) {
  $("#year-title").textContent = String(yearly.year);
  $("#year-total").textContent = `${money(yearly.total)} total`;

  const W = 560, H = 210, top = 26, bottom = 26, side = 6;
  const plotH = H - top - bottom;
  const slot = (W - side * 2) / 12;
  const barW = slot * 0.62;
  const totals = yearly.months.map((m) => Number(m.total));
  const max = Math.max(...totals, 1);
  const selected = yearly.year === state.month.year ? state.month.month : null;
  const maxMonth = totals.indexOf(Math.max(...totals)) + 1;

  const bars = yearly.months.map((m, i) => {
    const value = totals[i];
    const h = value > 0 ? Math.max((value / max) * plotH, 3) : 0;
    const x = side + i * slot + (slot - barW) / 2;
    const y = top + plotH - h;
    const isSelected = m.month === selected;
    const showValue = value > 0 && (isSelected || m.month === maxMonth);
    return `
      <g data-month="${m.month}" style="cursor:pointer">
        <title>${MONTHS[i]}: ${money(value)} (${m.count} expense${m.count === 1 ? "" : "s"})</title>
        <rect x="${side + i * slot}" y="${top}" width="${slot}" height="${plotH}" fill="transparent"></rect>
        <rect class="bar-rect ${isSelected ? "current" : ""}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="3"></rect>
        ${showValue ? `<text class="value-label" x="${(x + barW / 2).toFixed(1)}" y="${(y - 7).toFixed(1)}" text-anchor="middle">${moneyShort(value)}</text>` : ""}
        <text class="axis-label" x="${(x + barW / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${MONTHS[i].slice(0, 3)}</text>
      </g>`;
  }).join("");

  $("#year-chart").innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Spending per month in ${yearly.year}">
      <line class="gridline" x1="0" x2="${W}" y1="${top + plotH + 0.5}" y2="${top + plotH + 0.5}"></line>
      ${bars}
    </svg>`;
}

function renderRecent(items) {
  const list = $("#recent-list");
  if (!items.length) {
    list.innerHTML = `<li class="empty-inline">No expenses yet. Use <b>+ Add expense</b> to log your first one.</li>`;
    return;
  }
  list.innerHTML = items.map((e) => `
    <li><button type="button" class="recent-item" data-edit="${e.id}">
      <span class="recent-desc">${esc(e.description)}</span>
      <span class="recent-meta">${formatDate(e.spent_on, false)} · ${esc(e.category ? e.category.name : "Uncategorised")} · ${METHOD_LABELS[e.payment_method] || esc(e.payment_method)}</span>
      <span class="amount">${money(e.amount)}</span>
    </button></li>`).join("");
  state.recentItems = items;
}

/* ================= Expenses list ================= */

function filterParams() {
  const params = new URLSearchParams();
  const start = $("#f-start").value;
  const end = $("#f-end").value;
  const category = $("#f-category").value;
  const method = $("#f-method").value;
  const search = $("#f-search").value.trim();

  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  if (category === "none") params.set("uncategorised", "true");
  else if (category) params.set("category_id", category);
  if (method) params.set("payment_method", method);
  if (search) params.set("search", search);
  params.set("sort", $("#f-sort").value);
  params.set("limit", state.expenses.limit);
  params.set("offset", state.expenses.offset);
  return params;
}

function hasFilters() {
  return Boolean($("#f-start").value || $("#f-end").value || $("#f-category").value
    || $("#f-method").value || $("#f-search").value.trim());
}

async function loadExpenses() {
  const page = await api(`/expenses?${filterParams()}`);
  const { items, total, offset } = page;
  state.expenses.total = total;
  state.expenses.items = items;

  $("#exp-summary").textContent = `${total} expense${total === 1 ? "" : "s"}${hasFilters() ? " match" : ""}`;

  $("#exp-rows").innerHTML = items.map((e) => `
    <tr>
      <td class="date">${formatDate(e.spent_on)}</td>
      <td class="desc">${esc(e.description)}</td>
      <td class="cat">${categoryChip(e.category)}</td>
      <td class="method">${METHOD_LABELS[e.payment_method] || esc(e.payment_method)}</td>
      <td class="num amount">${money(e.amount)}</td>
      <td class="actions"><button type="button" class="btn btn-quiet" data-edit="${e.id}">Edit</button></td>
    </tr>`).join("");

  const empty = $("#exp-empty");
  empty.hidden = total > 0;
  $(".ledger", $("#view-expenses")).hidden = total === 0;
  if (total === 0) {
    empty.innerHTML = hasFilters()
      ? `<strong>No expenses match these filters.</strong><button type="button" class="btn btn-quiet" data-action="clear-filters">Clear filters</button>`
      : `<strong>No expenses yet.</strong><span>Log what you spend and it will appear here.</span><button type="button" class="btn btn-primary" data-action="add-expense">+ Add your first expense</button>`;
  }

  $("#page-info").textContent = total
    ? `${offset + 1}–${offset + items.length} of ${total}`
    : "";
  $('[data-action="page-prev"]').disabled = offset === 0;
  $('[data-action="page-next"]').disabled = offset + state.expenses.limit >= total;
  $(".pager").hidden = total <= state.expenses.limit;
}

function reloadFromFirstPage() {
  state.expenses.offset = 0;
  refreshView();
}

/* ================= Categories page ================= */

async function loadCategoriesView() {
  const today = new Date();
  const [categories, report] = await Promise.all([
    api("/categories"),
    api(`/reports/monthly?year=${today.getFullYear()}&month=${today.getMonth() + 1}`),
  ]);
  state.categories = categories;
  fillCategorySelects();
  const spent = new Map(report.by_category.map((r) => [r.category_id, Number(r.total)]));

  $("#cat-rows").innerHTML = categories.map((c) => {
    const thisMonth = spent.get(c.id) || 0;
    const budget = c.monthly_budget === null ? null : Number(c.monthly_budget);
    const over = budget !== null && thisMonth > budget;
    return `<tr>
      <td>${categoryChip(c)}</td>
      <td class="num amount ${over ? "over-text" : ""}" data-label="This month">${money(thisMonth)}</td>
      <td class="num" data-label="Budget">${budget === null ? '<span class="muted">No budget</span>' : money(budget)}</td>
      <td class="actions">
        <button type="button" class="btn btn-quiet" data-edit-category="${c.id}">Edit</button>
        <button type="button" class="btn btn-danger-quiet" data-delete-category="${c.id}">Delete</button>
      </td>
    </tr>`;
  }).join("") || `<tr><td colspan="4" class="empty-inline">No categories yet. Add one above.</td></tr>`;
}

/* ================= Dialogs ================= */

function confirmDialog(title, text, okLabel = "Delete") {
  const dialog = $("#confirm-dialog");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  $("#confirm-ok").textContent = okLabel;
  dialog.returnValue = "";
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true });
    dialog.showModal();
  });
}

function openExpenseDialog(expense = null) {
  state.editingExpense = expense;
  const form = $("#expense-form");
  form.reset();
  showFormError(form, "");
  $("#expense-dialog-title").textContent = expense ? "Edit expense" : "Add expense";
  $("#e-submit").textContent = expense ? "Save changes" : "Save expense";
  $("#e-delete").hidden = !expense;

  $("#e-amount").value = expense ? expense.amount : "";
  $("#e-description").value = expense ? expense.description : "";
  $("#e-date").value = expense ? expense.spent_on : localISO(new Date());
  $("#e-category").value = expense && expense.category ? String(expense.category.id) : "";
  form.elements.payment_method.value = expense ? expense.payment_method : "upi";

  $("#expense-dialog").showModal();
  $("#e-amount").focus();
}

function openCategoryDialog(category) {
  state.editingCategory = category;
  const form = $("#category-edit-form");
  showFormError(form, "");
  $("#c-name").value = category.name;
  $("#c-budget").value = category.monthly_budget ?? "";
  $("#category-dialog").showModal();
  $("#c-name").focus();
}

/* ================= Event wiring ================= */

// Login / register
$$("[data-auth-tab]").forEach((b) => b.addEventListener("click", () => setAuthTab(b.dataset.authTab)));

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  showFormError(form, "");
  button.disabled = true;
  try {
    await login(form.elements.username.value.trim(), form.elements.password.value);
    form.reset();
  } catch (err) {
    showFormError(form, err.message);
  } finally {
    button.disabled = false;
  }
});

$("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const username = form.elements.username.value.trim();
  const password = form.elements.password.value;
  showFormError(form, "");
  button.disabled = true;
  try {
    await api("/auth/register", {
      method: "POST",
      json: {
        username,
        email: form.elements.email.value.trim(),
        full_name: form.elements.full_name.value.trim() || null,
        password,
      },
    });
    await login(username, password);
    form.reset();
    setAuthTab("login");
    toast(`Welcome, ${username}! We've added some starter categories.`);
  } catch (err) {
    showFormError(form, err.message);
  } finally {
    button.disabled = false;
  }
});

// Buttons with data-action, anywhere on the page
document.addEventListener("click", async (event) => {
  const actionEl = event.target.closest("[data-action]");
  if (actionEl) {
    const action = actionEl.dataset.action;
    if (action === "add-expense") openExpenseDialog();
    if (action === "logout") logout();
    if (action === "prev-month") { state.month = shiftMonth(state.month, -1); refreshView(); }
    if (action === "next-month") { state.month = shiftMonth(state.month, 1); refreshView(); }
    if (action === "page-prev") { state.expenses.offset = Math.max(0, state.expenses.offset - state.expenses.limit); refreshView(); }
    if (action === "page-next") { state.expenses.offset += state.expenses.limit; refreshView(); }
    if (action === "clear-filters") $("#filters").reset();
    return;
  }

  const editEl = event.target.closest("[data-edit]");
  if (editEl) {
    const id = Number(editEl.dataset.edit);
    const pool = state.view === "dashboard" ? state.recentItems : state.expenses.items;
    const expense = (pool || []).find((e) => e.id === id);
    if (expense) openExpenseDialog(expense);
    return;
  }

  const editCat = event.target.closest("[data-edit-category]");
  if (editCat) {
    const category = state.categories.find((c) => c.id === Number(editCat.dataset.editCategory));
    if (category) openCategoryDialog(category);
    return;
  }

  const deleteCat = event.target.closest("[data-delete-category]");
  if (deleteCat) {
    const category = state.categories.find((c) => c.id === Number(deleteCat.dataset.deleteCategory));
    if (!category) return;
    const ok = await confirmDialog(`Delete “${category.name}”?`,
      "Its expenses are kept and marked as Uncategorised.");
    if (!ok) return;
    try {
      await api(`/categories/${category.id}`, { method: "DELETE" });
      toast(`Deleted “${category.name}”`);
      refreshView();
    } catch (err) {
      toast(err.message, true);
    }
    return;
  }

  // Click on a year-chart bar: jump to that month
  const bar = event.target.closest("#year-chart [data-month]");
  if (bar) {
    state.month = { year: state.month.year, month: Number(bar.dataset.month) };
    const today = new Date();
    if (state.month.year === today.getFullYear() && state.month.month > today.getMonth() + 1) {
      state.month.month = today.getMonth() + 1;
    }
    refreshView();
  }
});

// Close buttons and clicks on the dark backdrop close dialogs
$$("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target.closest("[data-close]")) { dialog.close(); return; }
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    const inside = event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom;
    if (!inside) dialog.close();
  });
});

// Save expense (add or edit)
$("#expense-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const editing = state.editingExpense;
  const body = {
    amount: form.elements.amount.value,
    description: form.elements.description.value.trim(),
    spent_on: form.elements.spent_on.value,
    payment_method: form.elements.payment_method.value,
    category_id: form.elements.category_id.value ? Number(form.elements.category_id.value) : null,
  };
  showFormError(form, "");
  try {
    if (editing) await api(`/expenses/${editing.id}`, { method: "PATCH", json: body });
    else await api("/expenses", { method: "POST", json: body });
    $("#expense-dialog").close();
    toast(editing ? "Expense updated" : `Added ${money(body.amount)} · ${body.description}`);
    refreshView();
  } catch (err) {
    showFormError(form, err.message);
  }
});

$("#e-delete").addEventListener("click", async () => {
  const expense = state.editingExpense;
  if (!expense) return;
  const ok = await confirmDialog("Delete this expense?", `${expense.description} · ${money(expense.amount)}`);
  if (!ok) return;
  try {
    await api(`/expenses/${expense.id}`, { method: "DELETE" });
    $("#expense-dialog").close();
    toast("Expense deleted");
    refreshView();
  } catch (err) {
    showFormError($("#expense-form"), err.message);
  }
});

// Add category
$("#category-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const budget = form.elements.monthly_budget.value;
  try {
    const created = await api("/categories", {
      method: "POST",
      json: { name: form.elements.name.value.trim(), monthly_budget: budget === "" ? null : budget },
    });
    form.reset();
    toast(`Added “${created.name}”`);
    refreshView();
  } catch (err) {
    toast(err.message, true);
  }
});

// Edit category
$("#category-edit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const category = state.editingCategory;
  const budget = form.elements.monthly_budget.value;
  try {
    await api(`/categories/${category.id}`, {
      method: "PATCH",
      json: { name: form.elements.name.value.trim(), monthly_budget: budget === "" ? null : budget },
    });
    $("#category-dialog").close();
    toast("Category saved");
    refreshView();
  } catch (err) {
    showFormError(form, err.message);
  }
});

// Filters: reload whenever something changes (search waits until you stop typing)
const filters = $("#filters");
filters.addEventListener("change", (event) => { if (event.target.id !== "f-search") reloadFromFirstPage(); });
$("#f-search").addEventListener("input", debounce(reloadFromFirstPage, 350));
filters.addEventListener("submit", (event) => { event.preventDefault(); reloadFromFirstPage(); });
filters.addEventListener("reset", () => setTimeout(reloadFromFirstPage)); // after the fields clear

window.addEventListener("hashchange", route);

/* ================= Start ================= */

(async function boot() {
  try { state.token = localStorage.getItem(TOKEN_KEY); } catch { state.token = null; }
  if (!state.token) { showAuth(); return; }
  try {
    await startApp();
  } catch (err) {
    if (err.status !== 401) { showAuth(); toast(err.message, true); }
  }
})();
