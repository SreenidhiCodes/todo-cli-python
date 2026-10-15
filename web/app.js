const API = "/api/v1";
const tokenKey = "taskflow_access_token";
const state = {
  token: localStorage.getItem(tokenKey), user: null, projects: [], tasks: [], view: "today",
  filter: "all", search: "", sort: "created", offset: 0, total: 0, limit: 100,
};

const $ = (selector) => document.querySelector(selector);
const authScreen = $("#auth-screen");
const appScreen = $("#app-screen");

function toast(message, kind = "success") {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast visible ${kind}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.className = "toast", 3200);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    if (response.status === 401 && state.token) signOut(false);
    const detail = data?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(" · ") : detail || `Request failed (${response.status})`);
  }
  return data;
}

function setAuthMode(register) {
  $("#name-field").classList.toggle("hidden", !register);
  $("#auth-name").required = register;
  $("#auth-kicker").textContent = register ? "GET STARTED" : "WELCOME BACK";
  $("#auth-title").textContent = register ? "Create your space." : "Good to see you.";
  $("#auth-subtitle").textContent = register ? "A clearer day starts with one small step." : "Sign in to pick up where you left off.";
  $("#auth-submit").innerHTML = register ? 'Create account <span>→</span>' : 'Sign in <span>→</span>';
  $("#auth-switch-text").textContent = register ? "Already have an account?" : "New to TaskFlow?";
  $("#auth-switch").textContent = register ? "Sign in" : "Create an account";
  $("#auth-password").autocomplete = register ? "new-password" : "current-password";
  $("#auth-form").dataset.mode = register ? "register" : "login";
}

function signOut(notify = true) {
  state.token = null;
  state.user = null;
  localStorage.removeItem(tokenKey);
  appScreen.classList.add("hidden");
  authScreen.classList.remove("hidden");
  setAuthMode(false);
  if (notify) toast("You’ve signed out.");
}

function showApp() {
  authScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  const now = new Date();
  $("#header-date").textContent = now.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  $("#welcome-date").textContent = now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }).toUpperCase();
}

function niceDue(dateValue) {
  if (!dateValue) return "No due date";
  const due = new Date(dateValue);
  const day = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.round((day - today) / 86400000);
  if (diff < 0) return `Overdue · ${due.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
  if (diff === 0) return "Due today";
  if (diff === 1) return "Due tomorrow";
  return `Due ${due.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

function getVisibleTasks() {
  let tasks = [...state.tasks];
  if (state.view === "today") {
    const today = new Date(); today.setHours(23, 59, 59, 999);
    tasks = tasks.filter((task) => task.status !== "done" && (!task.due_at || new Date(task.due_at) <= today));
  } else if (["todo", "in_progress", "done"].includes(state.view)) {
    tasks = tasks.filter((task) => task.status === state.view);
  } else if (state.view.startsWith("project:")) {
    const id = Number(state.view.split(":")[1]);
    tasks = tasks.filter((task) => task.project_id === id);
  }
  if (state.filter !== "all") tasks = tasks.filter((task) => task.status === state.filter);
  return tasks;
}

function renderTask(task) {
  const row = document.createElement("article");
  row.className = `task-row ${task.status === "done" ? "is-done" : ""}`;
  const check = document.createElement("button");
  check.className = `task-check ${task.status === "done" ? "checked" : ""}`;
  check.setAttribute("aria-label", task.status === "done" ? "Reopen task" : "Complete task");
  check.textContent = task.status === "done" ? "✓" : "";
  check.addEventListener("click", () => toggleTask(task));

  const content = document.createElement("div"); content.className = "task-main";
  const titleLine = document.createElement("div"); titleLine.className = "task-title-line";
  const title = document.createElement("button"); title.className = "task-title"; title.textContent = task.title;
  title.title = "Click to edit task title";
  title.addEventListener("click", () => editTask(task));
  const priority = document.createElement("span"); priority.className = `priority priority-${task.priority}`; priority.textContent = task.priority;
  titleLine.append(title, priority);
  content.append(titleLine);
  if (task.description) { const desc = document.createElement("p"); desc.className = "task-description"; desc.textContent = task.description; content.append(desc); }
  const meta = document.createElement("div"); meta.className = "task-meta";
  const due = document.createElement("span");
  const dueDate = task.due_at ? new Date(task.due_at) : null;
  const overdue = dueDate && dueDate < new Date() && task.status !== "done";
  due.className = `due-label ${overdue ? "overdue" : ""}`;
  due.innerHTML = `<span aria-hidden="true">◷</span> `;
  due.append(document.createTextNode(niceDue(task.due_at)));
  meta.append(due);
  const project = state.projects.find((item) => item.id === task.project_id);
  if (project) { const proj = document.createElement("span"); proj.className = "task-project"; proj.innerHTML = `<i></i>`; proj.lastChild.style.background = project.color; proj.append(document.createTextNode(project.name)); meta.append(proj); }
  task.tags.forEach((tag) => { const label = document.createElement("span"); label.className = "tag-label"; label.textContent = `#${tag}`; meta.append(label); });
  content.append(meta);
  const actions = document.createElement("div"); actions.className = "task-actions";
  const status = document.createElement("select"); status.className = "status-select"; status.setAttribute("aria-label", "Task status");
  [["todo", "To do"], ["in_progress", "In progress"], ["done", "Completed"]].forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; option.selected = task.status === value; status.append(option); });
  status.addEventListener("change", () => updateTask(task.id, { status: status.value }));
  const remove = document.createElement("button"); remove.className = "icon-button task-remove"; remove.title = "Delete task"; remove.setAttribute("aria-label", "Delete task"); remove.textContent = "×"; remove.addEventListener("click", () => deleteTask(task));
  actions.append(status, remove);
  row.append(check, content, actions);
  return row;
}

function render() {
  const list = $("#task-list"); list.replaceChildren();
  const tasks = getVisibleTasks();
  tasks.forEach((task) => list.append(renderTask(task)));
  $("#result-count").textContent = `${tasks.length} ${tasks.length === 1 ? "task" : "tasks"}`;
  $("#empty-state").classList.toggle("hidden", tasks.length !== 0);
  $("#load-more-wrap").classList.toggle("hidden", state.offset + state.tasks.length >= state.total);
  $("#stat-total").textContent = state.stats?.total ?? 0;
  $("#stat-todo").textContent = state.stats?.todo ?? 0;
  $("#stat-progress").textContent = state.stats?.in_progress ?? 0;
  $("#stat-done").textContent = state.stats?.done ?? 0;
  $("#today-count").textContent = state.tasks.filter((task) => task.status !== "done" && task.due_at && new Date(task.due_at).toDateString() === new Date().toDateString()).length;
  const viewNames = { today: "Today", all: "All tasks", todo: "To do", in_progress: "In progress", done: "Completed" };
  const currentProject = state.view.startsWith("project:") ? state.projects.find((p) => p.id === Number(state.view.split(":")[1])) : null;
  const name = currentProject?.name || viewNames[state.view] || "Today";
  $("#view-crumb").textContent = name;
  $("#list-title").textContent = state.view === "today" ? "Today's focus" : name;
  $("#page-title").textContent = state.view === "today" ? "Today, at your pace." : name;
  $("#list-caption").textContent = state.view === "today" ? "Your next steps, all in one place." : "Your tasks, just the way you need them.";
  $("#empty-title").textContent = state.view === "done" ? "Nothing completed just yet." : "A little breathing room.";
  $("#empty-copy").textContent = state.view === "done" ? "Finish a task and it’ll find its way here." : "Nothing on your list yet. Add a task and make a start.";
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === state.view));
  document.querySelectorAll(".project-item").forEach((item) => item.classList.toggle("active", state.view === `project:${item.dataset.projectId}`));
}

async function loadTasks(reset = true) {
  if (reset) { state.offset = 0; state.tasks = []; }
  const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset), sort: state.sort, direction: state.sort === "created" ? "desc" : "asc" });
  if (state.search.trim()) params.set("search", state.search.trim());
  const filterStatus = state.view === "todo" || state.view === "in_progress" || state.view === "done" ? state.view : state.filter !== "all" ? state.filter : null;
  if (filterStatus) params.set("status", filterStatus);
  if (state.view.startsWith("project:")) params.set("project_id", state.view.split(":")[1]);
  const page = await api(`/tasks?${params}`);
  state.total = page.total;
  state.tasks = reset ? page.items : [...state.tasks, ...page.items];
  state.offset += page.items.length;
  render();
}

async function reloadAll() {
  try {
    const [user, projects, stats] = await Promise.all([api("/auth/me"), api("/projects"), api("/tasks/stats")]);
    state.user = user; state.projects = projects; state.stats = stats;
    $("#user-name").textContent = user.full_name;
    $("#user-email").textContent = user.email;
    $("#user-avatar").textContent = (user.full_name || user.email).charAt(0).toUpperCase();
    renderProjects(); renderProjectOptions(); showApp(); await loadTasks();
  } catch (error) {
    if (state.token) { toast(error.message, "error"); signOut(false); }
  }
}

function renderProjects() {
  const list = $("#project-list"); list.replaceChildren();
  state.projects.forEach((project) => {
    const button = document.createElement("button"); button.className = "project-item"; button.dataset.projectId = project.id;
    const dot = document.createElement("i"); dot.className = "project-dot"; dot.style.background = project.color;
    const name = document.createElement("span"); name.textContent = project.name;
    button.append(dot, name); button.addEventListener("click", () => { state.view = `project:${project.id}`; state.filter = "all"; setFilterChips(); loadTasks(); }); list.append(button);
  });
}

function renderProjectOptions() {
  const select = $("#task-project"); select.replaceChildren();
  const none = document.createElement("option"); none.value = ""; none.textContent = "No project"; select.append(none);
  state.projects.forEach((project) => { const option = document.createElement("option"); option.value = project.id; option.textContent = project.name; select.append(option); });
}

function setFilterChips() {
  document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip.dataset.filter === state.filter));
}

async function toggleTask(task) {
  try {
    if (task.status === "done") await api(`/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ status: "todo" }) });
    else await api(`/tasks/${task.id}/complete`, { method: "POST" });
    toast(task.status === "done" ? "Task moved back to to do." : "Task completed. Nice work!"); await refreshData();
  } catch (error) { toast(error.message, "error"); }
}

async function updateTask(taskId, changes) {
  try { await api(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(changes) }); toast("Task updated."); await refreshData(); }
  catch (error) { toast(error.message, "error"); }
}

async function editTask(task) {
  const title = prompt("Edit task name:", task.title);
  if (title === null || title.trim() === task.title) return;
  if (!title.trim()) { toast("Task name can’t be empty.", "error"); return; }
  await updateTask(task.id, { title: title.trim() });
}

async function deleteTask(task) {
  if (!confirm(`Delete “${task.title}”? This can’t be undone.`)) return;
  try { await api(`/tasks/${task.id}`, { method: "DELETE" }); toast("Task deleted."); await refreshData(); }
  catch (error) { toast(error.message, "error"); }
}

async function refreshData() {
  state.stats = await api("/tasks/stats");
  await loadTasks();
}

function openTaskDialog() {
  $("#task-form").reset();
  $("#task-project").value = state.view.startsWith("project:") ? state.view.split(":")[1] : "";
  $("#task-dialog").showModal();
  setTimeout(() => $("#task-title").focus(), 50);
}

$("#auth-switch").addEventListener("click", () => setAuthMode($("#auth-form").dataset.mode !== "register"));
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const register = event.currentTarget.dataset.mode === "register";
  const email = $("#auth-email").value.trim(); const password = $("#auth-password").value;
  const button = $("#auth-submit"); button.disabled = true;
  try {
    if (register) {
      await api("/auth/register", { method: "POST", body: JSON.stringify({ email, password, full_name: $("#auth-name").value.trim() }) });
    }
    const result = await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    state.token = result.access_token; localStorage.setItem(tokenKey, state.token);
    await reloadAll();
    toast(register ? "Your account is ready. Welcome to TaskFlow!" : "Welcome back.");
  } catch (error) { toast(error.message, "error"); }
  finally { button.disabled = false; }
});

$("#signout").addEventListener("click", () => signOut());
$("#quick-add").addEventListener("click", openTaskDialog);
$("#empty-add").addEventListener("click", openTaskDialog);
$("#load-more").addEventListener("click", () => loadTasks(false).catch((error) => toast(error.message, "error")));
$("#sort-select").addEventListener("change", (event) => { state.sort = event.target.value; loadTasks(); });
$("#task-search").addEventListener("input", (event) => { clearTimeout(state.searchTimer); state.search = event.target.value; state.searchTimer = setTimeout(() => loadTasks(), 300); });
document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => { state.view = item.dataset.view; state.filter = "all"; setFilterChips(); loadTasks(); }));
document.querySelectorAll(".filter-chip").forEach((chip) => chip.addEventListener("click", () => { state.filter = chip.dataset.filter; setFilterChips(); loadTasks(); }));
$("#add-project-open").addEventListener("click", () => $("#project-dialog").showModal());
$("#project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const project = await api("/projects", { method: "POST", body: JSON.stringify({ name: $("#project-name").value.trim(), description: $("#project-description").value.trim(), color: $("#project-color").value }) });
    $("#project-dialog").close(); state.projects.push(project); renderProjects(); renderProjectOptions(); toast("Project created.");
  } catch (error) { toast(error.message, "error"); }
});
$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const dueDate = $("#task-due").value;
  const body = {
    title: $("#task-title").value.trim(), description: $("#task-description").value.trim(),
    priority: $("#task-priority").value,
    tags: $("#task-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
    due_at: dueDate ? new Date(`${dueDate}T12:00:00`).toISOString() : null,
    project_id: $("#task-project").value ? Number($("#task-project").value) : null,
  };
  try { await api("/tasks", { method: "POST", body: JSON.stringify(body) }); $("#task-dialog").close(); toast("Task added to your list."); await refreshData(); }
  catch (error) { toast(error.message, "error"); }
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.close}`).close()));
document.querySelectorAll("dialog").forEach((dialog) => dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); }));

setAuthMode(false);
if (state.token) reloadAll();
