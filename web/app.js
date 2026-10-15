const API = "/api/v1";
const tokenKey = "taskflow_access_token";
const state = {
  token: localStorage.getItem(tokenKey), user: null, projects: [], tasks: [], view: "today",
  filter: "all", search: "", sort: "created", offset: 0, total: 0, limit: 100,
  households: [], groceryLists: [], householdId: null, groceryListId: null, groceryItems: [],
  groceryFilter: "needed", grocerySearch: "", editingGroceryItem: null,
  familyTasks: [], familyMembers: [], familyFilter: "all", familySearch: "", editingFamilyTask: null,
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
  if (state.view === "groceries") { showGroceryWorkspace(); return; }
  if (state.view === "family_tasks") { showFamilyWorkspace(); return; }
  $("#task-footer").classList.remove("hidden");
  ["#task-welcome", "#task-stats", "#task-panel"].forEach((selector) => $(selector).classList.remove("hidden"));
  $("#grocery-workspace").classList.add("hidden");
  $("#family-workspace").classList.add("hidden");
  $("#quick-add").classList.remove("hidden");
  $("#quick-add").innerHTML = '<span>＋</span> New task';
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

function showGroceryWorkspace() {
  ["#task-welcome", "#task-stats", "#task-panel"].forEach((selector) => $(selector).classList.add("hidden"));
  $("#grocery-workspace").classList.remove("hidden"); $("#family-workspace").classList.add("hidden"); $("#quick-add").classList.add("hidden"); $("#task-footer").classList.add("hidden");
  $("#view-crumb").textContent = "Groceries";
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === "groceries"));
}

function showFamilyWorkspace() {
  ["#task-welcome", "#task-stats", "#task-panel", "#grocery-workspace"].forEach((selector) => $(selector).classList.add("hidden"));
  $("#family-workspace").classList.remove("hidden"); $("#quick-add").classList.remove("hidden"); $("#task-footer").classList.add("hidden");
  $("#quick-add").innerHTML = '<span>＋</span> New family task';
  $("#view-crumb").textContent = "Family Tasks";
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === "family_tasks"));
}

async function loadFamilyWorkspace() {
  showFamilyWorkspace();
  state.households = await api("/groceries/households");
  if (!state.households.some((household) => household.id === state.householdId)) state.householdId = state.households[0]?.id ?? null;
  const select = $("#family-household-select"); select.replaceChildren();
  state.households.forEach((household) => { const option = document.createElement("option"); option.value = household.id; option.textContent = household.name; select.append(option); });
  if (!state.householdId) { select.classList.add("hidden"); $("#family-no-household").classList.remove("hidden"); $("#family-task-content").classList.add("hidden"); return; }
  select.classList.remove("hidden"); select.value = String(state.householdId);
  $("#family-no-household").classList.add("hidden"); $("#family-task-content").classList.remove("hidden");
  const [members, summary] = await Promise.all([
    api(`/groceries/households/${state.householdId}/members`),
    api(`/family-tasks/households/${state.householdId}/summary`),
  ]);
  state.familyMembers = members;
  const assignee = $("#family-assignee"); assignee.replaceChildren();
  const none = document.createElement("option"); none.value = ""; none.textContent = "Anyone in the family"; assignee.append(none);
  members.forEach((member) => { const option = document.createElement("option"); option.value = member.user_id; option.textContent = member.full_name; assignee.append(option); });
  $("#family-todo").textContent = summary.todo; $("#family-progress").textContent = summary.in_progress; $("#family-done").textContent = summary.done;
  await loadFamilyTasks();
}

async function loadFamilyTasks() {
  if (!state.householdId) return;
  const params = new URLSearchParams();
  if (state.familyFilter !== "all") params.set("status", state.familyFilter);
  if (state.familySearch.trim()) params.set("search", state.familySearch.trim());
  const query = params.toString();
  state.familyTasks = await api(`/family-tasks/households/${state.householdId}/tasks${query ? `?${query}` : ""}`);
  const list = $("#family-task-list"); list.replaceChildren();
  state.familyTasks.forEach((task) => list.append(renderFamilyTask(task)));
  $("#family-task-count").textContent = `${state.familyTasks.length} ${state.familyTasks.length === 1 ? "task" : "tasks"}`;
  $("#family-no-tasks").classList.toggle("hidden", state.familyTasks.length !== 0);
  document.querySelectorAll("[data-family-filter]").forEach((button) => button.classList.toggle("selected", button.dataset.familyFilter === state.familyFilter));
}

function renderFamilyTask(task) {
  const row = document.createElement("article"); row.className = `task-row family-task-row ${task.status === "done" ? "is-done" : ""}`;
  const check = document.createElement("button"); check.className = `task-check ${task.status === "done" ? "checked" : ""}`; check.textContent = task.status === "done" ? "✓" : "";
  check.setAttribute("aria-label", task.status === "done" ? "Reopen family task" : "Complete family task");
  check.addEventListener("click", () => updateFamilyTask(task, { status: task.status === "done" ? "todo" : "done" }));
  const content = document.createElement("div"); content.className = "task-main";
  const titleLine = document.createElement("div"); titleLine.className = "task-title-line";
  const title = document.createElement("button"); title.className = "task-title"; title.textContent = task.title; title.addEventListener("click", () => openFamilyTask(task)); titleLine.append(title);
  const priority = document.createElement("span"); priority.className = `priority priority-${task.priority}`; priority.textContent = task.priority; titleLine.append(priority); content.append(titleLine);
  if (task.description) { const description = document.createElement("p"); description.className = "task-description"; description.textContent = task.description; content.append(description); }
  const meta = document.createElement("div"); meta.className = "task-meta";
  const assignee = document.createElement("span"); assignee.className = "task-project"; assignee.textContent = task.assignee_name ? `Assigned to ${task.assignee_name}` : "Anyone in the family"; meta.append(assignee);
  const creator = document.createElement("span"); creator.textContent = `Added by ${task.created_by_name}`; meta.append(creator);
  if (task.due_date) { const date = new Date(`${task.due_date}T00:00:00`); const due = document.createElement("span"); due.className = `due-label ${task.status !== "done" && date < new Date(new Date().toDateString()) ? "overdue" : ""}`; due.textContent = task.status === "done" ? "Completed" : niceDue(task.due_date); meta.append(due); }
  content.append(meta);
  const actions = document.createElement("div"); actions.className = "task-actions";
  const status = document.createElement("select"); status.className = "status-select"; status.setAttribute("aria-label", "Family task status");
  [["todo", "To do"], ["in_progress", "In progress"], ["done", "Completed"]].forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; option.selected = task.status === value; status.append(option); });
  status.addEventListener("change", () => updateFamilyTask(task, { status: status.value }));
  const remove = document.createElement("button"); remove.className = "icon-button task-remove"; remove.textContent = "×"; remove.title = "Delete family task"; remove.addEventListener("click", () => deleteFamilyTask(task));
  actions.append(status, remove); row.append(check, content, actions); return row;
}

function openFamilyTask(task = null) {
  if (!state.householdId) { toast("Create or join a household first.", "error"); return; }
  state.editingFamilyTask = task; $("#family-task-form").reset();
  $("#family-task-heading").textContent = task ? "Edit family task" : "New family task";
  $("#family-status").value = "todo"; $("#family-assignee").value = "";
  if (task) { $("#family-title").value = task.title; $("#family-description").value = task.description; $("#family-assignee").value = task.assignee_id || ""; $("#family-priority").value = task.priority; $("#family-due").value = task.due_date || ""; $("#family-status").value = task.status; }
  $("#family-task-dialog").showModal(); setTimeout(() => $("#family-title").focus(), 50);
}

async function updateFamilyTask(task, changes) { try { await api(`/family-tasks/${task.id}`, { method: "PATCH", body: JSON.stringify(changes) }); await loadFamilyWorkspace(); } catch (error) { toast(error.message, "error"); } }
async function deleteFamilyTask(task) { if (!confirm(`Delete “${task.title}” from Family Tasks?`)) return; try { await api(`/family-tasks/${task.id}`, { method: "DELETE" }); toast("Family task deleted."); await loadFamilyWorkspace(); } catch (error) { toast(error.message, "error"); } }

async function loadGroceryWorkspace() {
  showGroceryWorkspace();
  state.households = await api("/groceries/households");
  const select = $("#household-select"); select.replaceChildren();
  state.households.forEach((household) => { const option = document.createElement("option"); option.value = household.id; option.textContent = household.name; select.append(option); });
  if (!state.households.some((household) => household.id === state.householdId)) state.householdId = state.households[0]?.id ?? null;
  if (!state.householdId) { $("#grocery-empty-household").classList.remove("hidden"); $("#grocery-empty-list").classList.add("hidden"); $("#grocery-content").classList.add("hidden"); select.classList.add("hidden"); $("#grocery-list-select").classList.add("hidden"); return; }
  select.classList.remove("hidden"); select.value = String(state.householdId);
  const household = state.households.find((entry) => entry.id === state.householdId);
  $("#household-share").classList.remove("hidden"); $("#invite-code-value").textContent = household.invite_code;
  $("#household-create-form").classList.add("hidden");
  state.groceryLists = await api(`/groceries/households/${state.householdId}/lists`);
  const listSelect = $("#grocery-list-select"); listSelect.replaceChildren();
  state.groceryLists.forEach((entry) => { const option = document.createElement("option"); option.value = entry.id; option.textContent = entry.name; listSelect.append(option); });
  if (!state.groceryLists.some((entry) => entry.id === state.groceryListId)) state.groceryListId = state.groceryLists[0]?.id ?? null;
  if (!state.groceryListId) { $("#grocery-empty-household").classList.add("hidden"); $("#grocery-empty-list").classList.remove("hidden"); $("#grocery-content").classList.add("hidden"); listSelect.classList.add("hidden"); return; }
  listSelect.classList.remove("hidden"); listSelect.value = String(state.groceryListId);
  $("#grocery-empty-household").classList.add("hidden"); $("#grocery-empty-list").classList.add("hidden"); $("#grocery-content").classList.remove("hidden");
  await loadGroceryItems();
}

async function loadGroceryItems() {
  if (!state.groceryListId) return;
  const params = new URLSearchParams({ purchased: state.groceryFilter });
  if (state.grocerySearch.trim()) params.set("search", state.grocerySearch.trim());
  const [items, summary] = await Promise.all([api(`/groceries/lists/${state.groceryListId}/items?${params}`), api(`/groceries/lists/${state.groceryListId}/summary`)]);
  state.groceryItems = items;
  $("#grocery-needed").textContent = summary.needed; $("#grocery-overdue").textContent = summary.overdue; $("#grocery-purchased").textContent = summary.purchased;
  const list = $("#grocery-items"); list.replaceChildren(); items.forEach((item) => list.append(renderGroceryItem(item)));
  $("#grocery-result-count").textContent = `${items.length} ${items.length === 1 ? "item" : "items"}`;
  $("#grocery-no-items").classList.toggle("hidden", items.length !== 0);
  document.querySelectorAll("[data-grocery-filter]").forEach((button) => button.classList.toggle("selected", button.dataset.groceryFilter === state.groceryFilter));
}

function renderGroceryItem(item) {
  const row = document.createElement("article"); row.className = `task-row grocery-row ${item.is_purchased ? "is-done" : ""}`;
  const check = document.createElement("button"); check.className = `task-check ${item.is_purchased ? "checked" : ""}`; check.textContent = item.is_purchased ? "✓" : "";
  check.setAttribute("aria-label", item.is_purchased ? "Move back to needed" : "Mark picked up");
  check.addEventListener("click", () => updateGroceryItem(item, { is_purchased: !item.is_purchased }));
  const content = document.createElement("div"); content.className = "task-main";
  const titleLine = document.createElement("div"); titleLine.className = "task-title-line";
  const title = document.createElement("button"); title.className = "task-title"; title.textContent = item.name; title.addEventListener("click", () => openGroceryItem(item)); titleLine.append(title);
  const priority = document.createElement("span"); priority.className = `priority priority-${item.priority === "normal" ? "medium" : item.priority}`; priority.textContent = item.priority; titleLine.append(priority); content.append(titleLine);
  if (item.notes) { const note = document.createElement("p"); note.className = "task-description"; note.textContent = item.notes; content.append(note); }
  const meta = document.createElement("div"); meta.className = "task-meta";
  if (item.quantity) { const quantity = document.createElement("span"); quantity.textContent = `× ${item.quantity}`; meta.append(quantity); }
  if (item.category) { const category = document.createElement("span"); category.className = "tag-label"; category.textContent = item.category; meta.append(category); }
  if (item.deadline) { const date = new Date(`${item.deadline}T00:00:00`); const due = document.createElement("span"); due.className = `due-label ${!item.is_purchased && date < new Date(new Date().toDateString()) ? "overdue" : ""}`; due.textContent = item.is_purchased ? "Picked up" : niceDue(item.deadline); meta.append(due); }
  content.append(meta);
  const actions = document.createElement("div"); actions.className = "task-actions";
  const prioritySelect = document.createElement("select"); prioritySelect.className = "status-select grocery-priority-select"; prioritySelect.setAttribute("aria-label", "Change item priority");
  [["urgent", "Urgent"], ["high", "High"], ["normal", "Normal"], ["low", "Low"]].forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; option.selected = item.priority === value; prioritySelect.append(option); });
  prioritySelect.addEventListener("change", () => updateGroceryItem(item, { priority: prioritySelect.value }));
  const remove = document.createElement("button"); remove.className = "icon-button task-remove"; remove.textContent = "×"; remove.title = "Remove item"; remove.addEventListener("click", () => deleteGroceryItem(item));
  actions.append(prioritySelect, remove); row.append(check, content, actions); return row;
}

async function updateGroceryItem(item, changes) { try { await api(`/groceries/items/${item.id}`, { method: "PATCH", body: JSON.stringify(changes) }); await loadGroceryItems(); } catch (error) { toast(error.message, "error"); } }
async function deleteGroceryItem(item) { if (!confirm(`Remove “${item.name}” from this list?`)) return; try { await api(`/groceries/items/${item.id}`, { method: "DELETE" }); toast("Item removed."); await loadGroceryItems(); } catch (error) { toast(error.message, "error"); } }
function openGroceryItem(item = null) {
  if (!state.groceryListId) { toast("Create a grocery list first.", "error"); return; }
  state.editingGroceryItem = item; $("#grocery-item-form").reset();
  $("#grocery-item-heading").textContent = item ? "Edit item" : "Add an item";
  if (item) { $("#grocery-name").value = item.name; $("#grocery-quantity").value = item.quantity; $("#grocery-category").value = item.category; $("#grocery-priority").value = item.priority; $("#grocery-deadline").value = item.deadline || ""; $("#grocery-notes").value = item.notes; }
  $("#grocery-item-dialog").showModal(); setTimeout(() => $("#grocery-name").focus(), 50);
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
$("#quick-add").addEventListener("click", () => state.view === "family_tasks" ? openFamilyTask() : openTaskDialog());
$("#empty-add").addEventListener("click", openTaskDialog);
$("#load-more").addEventListener("click", () => loadTasks(false).catch((error) => toast(error.message, "error")));
$("#sort-select").addEventListener("change", (event) => { state.sort = event.target.value; loadTasks(); });
$("#task-search").addEventListener("input", (event) => { clearTimeout(state.searchTimer); state.search = event.target.value; state.searchTimer = setTimeout(() => loadTasks(), 300); });
document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => { state.view = item.dataset.view; state.filter = "all"; setFilterChips(); if (state.view === "groceries") loadGroceryWorkspace().catch((error) => toast(error.message, "error")); else if (state.view === "family_tasks") loadFamilyWorkspace().catch((error) => toast(error.message, "error")); else loadTasks(); }));
document.querySelectorAll(".filter-chip").forEach((chip) => chip.addEventListener("click", () => { state.filter = chip.dataset.filter; setFilterChips(); loadTasks(); }));
$("#add-project-open").addEventListener("click", () => { if (state.view === "groceries") $("#grocery-list-dialog").showModal(); else $("#project-dialog").showModal(); });
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

$("#household-select").addEventListener("change", (event) => { state.householdId = Number(event.target.value); state.groceryListId = null; loadGroceryWorkspace().catch((error) => toast(error.message, "error")); });
$("#family-household-select").addEventListener("change", (event) => { state.householdId = Number(event.target.value); loadFamilyWorkspace().catch((error) => toast(error.message, "error")); });
$("#grocery-list-select").addEventListener("change", (event) => { state.groceryListId = Number(event.target.value); loadGroceryItems().catch((error) => toast(error.message, "error")); });
$("#grocery-search").addEventListener("input", (event) => { clearTimeout(state.grocerySearchTimer); state.grocerySearch = event.target.value; state.grocerySearchTimer = setTimeout(() => loadGroceryItems().catch((error) => toast(error.message, "error")), 250); });
document.querySelectorAll("[data-grocery-filter]").forEach((button) => button.addEventListener("click", () => { state.groceryFilter = button.dataset.groceryFilter; loadGroceryItems().catch((error) => toast(error.message, "error")); }));
$("#add-grocery").addEventListener("click", () => openGroceryItem()); $("#empty-add-grocery").addEventListener("click", () => openGroceryItem());
$("#first-household").addEventListener("click", () => { $("#household-create-form").classList.remove("hidden"); $("#household-share").classList.add("hidden"); $("#new-grocery-list").classList.add("hidden"); $("#household-dialog").showModal(); });
$("#manage-household").addEventListener("click", () => { $("#household-create-form").classList.toggle("hidden", state.households.length > 0); $("#household-share").classList.toggle("hidden", state.households.length === 0); $("#new-grocery-list").classList.toggle("hidden", state.households.length === 0); if (state.households.length) $("#invite-code-value").textContent = state.households.find((entry) => entry.id === state.householdId)?.invite_code || ""; $("#household-dialog").showModal(); });
$("#first-grocery-list").addEventListener("click", () => $("#grocery-list-dialog").showModal()); $("#new-grocery-list").addEventListener("click", () => { $("#household-dialog").close(); $("#grocery-list-dialog").showModal(); });
$("#household-create-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const household = await api("/groceries/households", { method: "POST", body: JSON.stringify({ name: $("#household-name").value.trim() }) }); state.householdId = household.id; state.groceryListId = null; $("#household-dialog").close(); toast("Household created. Share the invite code to plan together."); await loadGroceryWorkspace(); $("#household-dialog").showModal(); } catch (error) { toast(error.message, "error"); } });
$("#household-join-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const household = await api("/groceries/households/join", { method: "POST", body: JSON.stringify({ invite_code: $("#household-code").value.trim() }) }); state.householdId = household.id; state.groceryListId = null; $("#household-dialog").close(); toast(`You joined ${household.name}.`); await loadGroceryWorkspace(); } catch (error) { toast(error.message, "error"); } });
$("#copy-invite").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("#invite-code-value").textContent); toast("Invite code copied."); } catch { toast("Select and copy the invite code.", "error"); } });
$("#rotate-invite").addEventListener("click", async () => { const household = state.households.find((entry) => entry.id === state.householdId); if (!household || !confirm("Reset this code? Anyone with the old code will no longer be able to join.")) return; try { await api(`/groceries/households/${household.id}/rotate-code`, { method: "POST" }); await loadGroceryWorkspace(); toast("Invite code reset."); $("#household-dialog").showModal(); } catch (error) { toast(error.message, "error"); } });
$("#grocery-list-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const list = await api(`/groceries/households/${state.householdId}/lists`, { method: "POST", body: JSON.stringify({ name: $("#grocery-list-name").value.trim() }) }); state.groceryListId = list.id; $("#grocery-list-dialog").close(); toast("Grocery list created."); await loadGroceryWorkspace(); } catch (error) { toast(error.message, "error"); } });
$("#grocery-item-form").addEventListener("submit", async (event) => { event.preventDefault(); const body = { name: $("#grocery-name").value.trim(), quantity: $("#grocery-quantity").value.trim(), category: $("#grocery-category").value.trim(), priority: $("#grocery-priority").value, deadline: $("#grocery-deadline").value || null, notes: $("#grocery-notes").value.trim() }; try { if (state.editingGroceryItem) await api(`/groceries/items/${state.editingGroceryItem.id}`, { method: "PATCH", body: JSON.stringify(body) }); else await api(`/groceries/lists/${state.groceryListId}/items`, { method: "POST", body: JSON.stringify(body) }); $("#grocery-item-dialog").close(); toast(state.editingGroceryItem ? "Item updated." : "Item added."); await loadGroceryItems(); } catch (error) { toast(error.message, "error"); } });
$("#add-family-task").addEventListener("click", () => openFamilyTask()); $("#empty-add-family-task").addEventListener("click", () => openFamilyTask());
$("#family-go-groceries").addEventListener("click", () => { state.view = "groceries"; loadGroceryWorkspace().catch((error) => toast(error.message, "error")); });
$("#family-manage-household").addEventListener("click", async () => { state.view = "groceries"; try { await loadGroceryWorkspace(); $("#household-create-form").classList.toggle("hidden", state.households.length > 0); $("#household-share").classList.toggle("hidden", state.households.length === 0); $("#new-grocery-list").classList.toggle("hidden", state.households.length === 0); if (state.households.length) $("#invite-code-value").textContent = state.households.find((entry) => entry.id === state.householdId)?.invite_code || ""; $("#household-dialog").showModal(); } catch (error) { toast(error.message, "error"); } });
$("#family-task-search").addEventListener("input", (event) => { clearTimeout(state.familySearchTimer); state.familySearch = event.target.value; state.familySearchTimer = setTimeout(() => loadFamilyTasks().catch((error) => toast(error.message, "error")), 250); });
document.querySelectorAll("[data-family-filter]").forEach((button) => button.addEventListener("click", () => { state.familyFilter = button.dataset.familyFilter; loadFamilyTasks().catch((error) => toast(error.message, "error")); }));
$("#family-task-form").addEventListener("submit", async (event) => { event.preventDefault(); const body = { title: $("#family-title").value.trim(), description: $("#family-description").value.trim(), assignee_id: $("#family-assignee").value ? Number($("#family-assignee").value) : null, priority: $("#family-priority").value, due_date: $("#family-due").value || null, status: $("#family-status").value }; try { if (state.editingFamilyTask) await api(`/family-tasks/${state.editingFamilyTask.id}`, { method: "PATCH", body: JSON.stringify(body) }); else await api(`/family-tasks/households/${state.householdId}/tasks`, { method: "POST", body: JSON.stringify(body) }); $("#family-task-dialog").close(); toast(state.editingFamilyTask ? "Family task updated." : "Added to the family plan."); await loadFamilyWorkspace(); } catch (error) { toast(error.message, "error"); } });

setAuthMode(false);
if (state.token) reloadAll();
