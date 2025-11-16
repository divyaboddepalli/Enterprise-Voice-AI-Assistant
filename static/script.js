// script.js — voice recognition, UI controls, auth helpers

let recognition = null;
let listening = false;

function speak(text) {
  if (!text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1;
  window.speechSynthesis.speak(u);
}

function startRecognition() {
  if (listening) return;
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert("Speech recognition not supported in this browser. Use Chrome (desktop or mobile).");
    return;
  }
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new Rec();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    listening = true;
    const btn = document.getElementById("micBtn");
    if (btn) btn.textContent = "Listening... 🎧";
  };

  recognition.onresult = async (event) => {
    const text = event.results[0][0].transcript;
    document.getElementById("userText").value = text;

    // send to backend
    const email = document.getElementById("emailField") ? document.getElementById("emailField").value.trim() : "";
    const res = await fetch("/ask", {
      method: "POST",
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ message: text, email })
    });
    const out = await res.json();
    const reply = out.reply || "I didn't catch that. Try asking about leave balance, booking meeting rooms, or 'show policies'.";
    document.getElementById("botText").value = reply;
    speak(reply);
  };

  recognition.onerror = (e) => {
    console.error("Recognition error", e);
    listening = false;
    const btn = document.getElementById("micBtn");
    if (btn) btn.textContent = "Start Listening 🎤";
  };

  recognition.onend = () => {
    listening = false;
    const btn = document.getElementById("micBtn");
    if (btn) btn.textContent = "Start Listening 🎤";
  };

  recognition.start();
}

// Stop recognition and any TTS immediately
function stopAll() {
  if (recognition) {
    try { recognition.stop(); } catch(e){ console.warn(e); }
    recognition = null;
  }
  window.speechSynthesis.cancel();
  listening = false;
  const btn = document.getElementById("micBtn");
  if (btn) btn.textContent = "Start Listening 🎤";
}

// Reset UI (stop audio + clear boxes + server reset call)
async function resetUI() {
  stopAll();
  const u = document.getElementById("userText");
  const b = document.getElementById("botText");
  if (u) u.value = "";
  if (b) b.value = "";
  await fetch("/reset", { method: "POST" });
}

// Logout
async function logout() {
  await fetch("/logout");
  window.location.href = "/login";
}

// Attach event listeners on DOM load
document.addEventListener("DOMContentLoaded", () => {
  const micBtn = document.getElementById("micBtn");
  if (micBtn) micBtn.addEventListener("click", startRecognition);

  const stopBtn = document.getElementById("stopBtn");
  if (stopBtn) stopBtn.addEventListener("click", stopAll);

  const resetBtn = document.getElementById("resetBtn");
  if (resetBtn) resetBtn.addEventListener("click", resetUI);

  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
});
