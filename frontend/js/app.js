const apiUrl = "http://localhost:8000/api";
const chatEl = document.getElementById("chat");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const suggestionBox = document.getElementById("suggestionBox");
const micBtn = document.getElementById("micBtn");
const showStatsBtn = document.getElementById("showStats");
let userId = null;

const emotionIcons = {
  anger: "😡", sadness: "😢", fear: "😨",
  joy: "😊", stress: "😫", calm: "😌",
  severe_distress: "⚠️", neutral: "🙂"
};

function appendMessage(text, cls, meta, typing=false) {
  const d = document.createElement("div");
  d.className = `msg ${cls}`;

  if (typing) {
    let i = 0;
    const interval = setInterval(() => {
      d.innerHTML = `<div>${escapeHtml(text.slice(0, i))}▌</div>`;
      i++;
      if (i > text.length) {
        clearInterval(interval);
        d.innerHTML = `<div>${escapeHtml(text)}</div>`;
      }
    }, 30);
  } else {
    d.innerHTML = `<div>${escapeHtml(text)}</div>`;
  }

  if (meta) {
    const m = document.createElement("div");
    m.className = "msg meta";
    m.textContent = meta;
    d.appendChild(m);
  }

  chatEl.appendChild(d);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  appendMessage(text, "user");
  input.value = "";

  try {
    const res = await fetch(`${apiUrl}/chat`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ user_id: userId, text })
    });

    const data = await res.json();
    userId = data.user_id;

    const emoIcon = emotionIcons[data.emotion] || "";
    const meta = `${emoIcon} ${data.emotion} (${Math.round(data.confidence*100)}%) ${data.escalate ? "⚠️" : ""}`;
    appendMessage(data.text, "bot", meta, true);

    suggestionBox.innerHTML = data.suggestion ? `<p>💡 ${data.suggestion}</p>` : "";

    // Voice output 🔊
    const utter = new SpeechSynthesisUtterance(data.text);
    speechSynthesis.speak(utter);

  } catch (err) {
    appendMessage("⚠️ Network error: " + err.message, "bot");
  }
});

// 🎤 Voice input
if ("webkitSpeechRecognition" in window) {
  const rec = new webkitSpeechRecognition();
  rec.lang = "en-US";
  rec.continuous = false;
  rec.interimResults = false;

  micBtn.addEventListener("click", () => rec.start());
  rec.onresult = (e) => {
    input.value = e.results[0][0].transcript;
    form.dispatchEvent(new Event("submit"));
  };
}

// 📊 Dashboard
showStatsBtn.addEventListener("click", async () => {
  const res = await fetch(`${apiUrl}/stats/${userId}`);
  const stats = await res.json();

  document.getElementById("dashboard").style.display = "block";
  const ctx = document.getElementById("moodChart").getContext("2d");

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: Object.keys(stats),
      datasets: [{ data: Object.values(stats), backgroundColor: ["#f87171","#60a5fa","#facc15","#4ade80","#c084fc","#a3e635"] }]
    }
  });
});
