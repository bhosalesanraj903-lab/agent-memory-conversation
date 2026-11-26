// Chat UI logic. Talks to the FastAPI backend on the same origin.

const userSelect = document.getElementById("user-select");
const sessionList = document.getElementById("session-list");
const messagesEl = document.getElementById("messages");
const chatTitle = document.getElementById("chat-title");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");

let userId = null;          // currently selected customer
let activeSessionId = null; // null means a brand new chat that has no session yet

// ---------- API helper ----------

// Call the backend and return parsed JSON; throws an Error with the server's message on failure.
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

// ---------- Rendering ----------

// Add one chat bubble to the message pane and scroll to the bottom. Returns the element.
function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text; // textContent (not innerHTML) so message text can never inject HTML
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

// Show the empty-state text for a chat that has no messages yet.
function showWelcome() {
  messagesEl.innerHTML = "";
  const div = document.createElement("div");
  div.className = "welcome";
  div.innerHTML = "<h2>How can I help?</h2><p>Ask about your recent orders, billing details, or where a package is.</p>";
  messagesEl.appendChild(div);
}

// Format a unix timestamp (seconds) as a short date/time for the sidebar.
function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// Redraw the sidebar from the server's list of this user's chats (newest first).
async function loadSessions() {
  const sessions = await api(`/users/${userId}/sessions`);
  sessionList.innerHTML = "";
  if (sessions.length === 0) {
    sessionList.innerHTML = '<li class="empty">No chats yet</li>';
    return;
  }
  for (const s of sessions) {
    const li = document.createElement("li");
    if (s.session_id === activeSessionId) li.classList.add("active");
    li.innerHTML = '<div class="s-title"></div><div class="s-meta"></div>';
    li.querySelector(".s-title").textContent = s.title;
    li.querySelector(".s-meta").textContent = `${formatTime(s.updated_at)} · ${s.message_count} msgs`;
    li.addEventListener("click", () => openSession(s.session_id, s.title));
    sessionList.appendChild(li);
  }
}

// ---------- Actions ----------

// Start a fresh chat. The session is created on the server lazily, when the first message is sent.
function newChat() {
  activeSessionId = null;
  localStorage.removeItem("activeSessionId");
  chatTitle.textContent = "New chat";
  showWelcome();
  loadSessions();
  input.focus();
}

// Open a past chat: load its stored messages from the server and show them.
async function openSession(sessionId, title) {
  activeSessionId = sessionId;
  localStorage.setItem("activeSessionId", sessionId);
  chatTitle.textContent = title;
  messagesEl.innerHTML = "";
  try {
    const messages = await api(`/sessions/${sessionId}/messages?user_id=${userId}`);
    messages.forEach((m) => addMessage(m.role === "user" ? "user" : "agent", m.content));
  } catch (err) {
    addMessage("error", err.message);
  }
  loadSessions();
  input.focus();
}

// Send the typed message to the agent and show its reply.
async function sendMessage(text) {
  if (messagesEl.querySelector(".welcome")) messagesEl.innerHTML = "";
  addMessage("user", text);
  const typing = addMessage("agent typing", "Thinking...");
  sendBtn.disabled = true;
  input.disabled = true;
  try {
    const data = await api("/chat", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, session_id: activeSessionId, message: text }),
    });
    activeSessionId = data.session_id;
    localStorage.setItem("activeSessionId", data.session_id);
    chatTitle.textContent = data.title;
    typing.remove();
    addMessage("agent", data.reply);
    loadSessions(); // refresh so the new title and ordering show up
  } catch (err) {
    typing.remove();
    addMessage("error", err.message);
  } finally {
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

// Switch to another customer: remember the choice and reset to a new chat.
async function switchUser(newUserId) {
  userId = newUserId;
  localStorage.setItem("userId", userId);
  localStorage.removeItem("activeSessionId");
  activeSessionId = null;
  newChat();
}

// ---------- Startup ----------

// Load customers, restore the last user/chat (so a page reload or server restart picks up where you left off).
async function init() {
  const users = await api("/users");
  for (const u of users) {
    const opt = document.createElement("option");
    opt.value = u.customer_id;
    opt.textContent = `${u.name} (${u.customer_id})`;
    userSelect.appendChild(opt);
  }
  userId = localStorage.getItem("userId") || users[0].customer_id;
  userSelect.value = userId;

  const savedSession = localStorage.getItem("activeSessionId");
  const sessions = await api(`/users/${userId}/sessions`);
  const saved = sessions.find((s) => s.session_id === savedSession);
  if (saved) openSession(saved.session_id, saved.title);
  else newChat();
}

userSelect.addEventListener("change", () => switchUser(userSelect.value));
document.getElementById("new-chat").addEventListener("click", newChat);
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendMessage(text);
});

init().catch((err) => addMessage("error", `Cannot reach the server: ${err.message}`));
