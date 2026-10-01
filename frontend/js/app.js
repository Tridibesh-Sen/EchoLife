/**
 * EchoLife Main Application Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let activeProfile = "default_user";
  let activeCategory = "all";
  let allCategories = [];
  let recorder = null;
  let player = new AudioPlayer();
  let recordedBlob = null;
  let isSpeaking = false;

  // DOM Elements
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const engineBadge = document.getElementById("engineBadge");
  const activeProfileName = document.getElementById("activeProfileName");
  const categoryTabs = document.getElementById("categoryTabs");
  const aacGrid = document.getElementById("aacGrid");
  const typingInput = document.getElementById("typingInput");
  const btnSpeak = document.getElementById("btnSpeak");
  const speakingBanner = document.getElementById("speakingBanner");
  const speakingText = document.getElementById("speakingText");

  // Modal Elements
  const enrollmentModal = document.getElementById("enrollmentModal");
  const btnOpenEnrollment = document.getElementById("btnOpenEnrollment");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const profileNameInput = document.getElementById("profileNameInput");
  const btnRecord = document.getElementById("btnRecord");
  const btnPreviewRecord = document.getElementById("btnPreviewRecord");
  const btnSaveVoice = document.getElementById("btnSaveVoice");
  const recordStatus = document.getElementById("recordStatus");
  const micMeterFill = document.getElementById("micMeterFill");

  // 1. Check Backend Status
  async function checkServerStatus() {
    const status = await ApiClient.getStatus();
    if (status.status === "ready") {
      statusDot.classList.add("active");
      statusText.textContent = "Offline Ready";
      
      const engineName = status.active_engine === "xtts_v2" ? "XTTS-v2 (GPU)" : 
                         status.active_engine === "openvoice_v2" ? "OpenVoice v2" : "Standby Mode";
      engineBadge.textContent = engineName;
      engineBadge.style.display = "inline-block";

      if (status.installed_profiles && status.installed_profiles.length > 0) {
        activeProfile = status.installed_profiles[0];
        activeProfileName.textContent = activeProfile;
      }
    } else {
      statusDot.classList.remove("active");
      statusText.textContent = "Backend Offline";
      engineBadge.textContent = "Connecting...";
    }
  }

  // 2. Load AAC Phrases
  async function loadPhrases() {
    try {
      const data = await ApiClient.getPhrases();
      allCategories = data.categories || [];
      renderCategoryTabs();
      renderPhraseGrid();
    } catch (e) {
      console.warn("Using fallback phrase list:", e);
      aacGrid.innerHTML = `
        <button class="phrase-card emergency" data-text="I need help right now.">
          <span class="phrase-text">I need help right now.</span>
          <span class="phrase-meta">Emergency • 0ms</span>
        </button>
        <button class="phrase-card" data-text="I need a glass of water.">
          <span class="phrase-text">I need a glass of water.</span>
          <span class="phrase-meta">Daily Needs</span>
        </button>
        <button class="phrase-card" data-text="I love you so much.">
          <span class="phrase-text">I love you so much.</span>
          <span class="phrase-meta">Family</span>
        </button>
      `;
      bindPhraseClicks();
    }
  }

  function renderCategoryTabs() {
    categoryTabs.innerHTML = `
      <button class="tab-btn ${activeCategory === 'all' ? 'active' : ''}" data-cat="all">All Phrases</button>
    `;
    allCategories.forEach(cat => {
      const btn = document.createElement("button");
      btn.className = `tab-btn ${activeCategory === cat.id ? 'active' : ''}`;
      btn.dataset.cat = cat.id;
      btn.textContent = cat.name;
      categoryTabs.appendChild(btn);
    });

    categoryTabs.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        categoryTabs.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        activeCategory = btn.dataset.cat;
        renderPhraseGrid();
      });
    });
  }

  function renderPhraseGrid() {
    aacGrid.innerHTML = "";
    allCategories.forEach(cat => {
      if (activeCategory !== "all" && activeCategory !== cat.id) return;

      cat.phrases.forEach(phrase => {
        const card = document.createElement("button");
        card.className = `phrase-card ${cat.id === 'emergency' ? 'emergency' : ''}`;
        card.dataset.text = phrase;
        card.innerHTML = `
          <span class="phrase-text">${phrase}</span>
          <span class="phrase-meta">${cat.name} ${cat.id === 'emergency' ? '• Fast' : ''}</span>
        `;
        aacGrid.appendChild(card);
      });
    });

    bindPhraseClicks();
  }

  function bindPhraseClicks() {
    aacGrid.querySelectorAll(".phrase-card").forEach(card => {
      card.addEventListener("click", () => {
        const text = card.dataset.text;
        speakText(text);
      });
    });
  }

  // 3. Speech Synthesis
  async function speakText(text) {
    if (!text || isSpeaking) return;
    isSpeaking = true;
    showSpeakingBanner(text);

    try {
      const wavBlob = await ApiClient.synthesizeSpeech(text, activeProfile);
      player.playBlob(
        wavBlob,
        () => { /* playback started */ },
        () => {
          hideSpeakingBanner();
          isSpeaking = false;
        }
      );
    } catch (e) {
      alert(`Synthesis Error: ${e.message}`);
      hideSpeakingBanner();
      isSpeaking = false;
    }
  }

  function showSpeakingBanner(text) {
    speakingText.textContent = `Speaking: "${text}"`;
    speakingBanner.classList.add("active");
  }

  function hideSpeakingBanner() {
    speakingBanner.classList.remove("active");
  }

  // 4. Free-Text Input
  btnSpeak.addEventListener("click", () => {
    const text = typingInput.value.trim();
    if (text) {
      speakText(text);
      typingInput.value = "";
    }
  });

  typingInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const text = typingInput.value.trim();
      if (text) {
        speakText(text);
        typingInput.value = "";
      }
    }
  });

  // 5. Voice Enrollment Modal Flow
  btnOpenEnrollment.addEventListener("click", () => {
    enrollmentModal.classList.add("active");
    recordStatus.textContent = "Ready to record 15-second sample";
    btnSaveVoice.disabled = true;
    btnPreviewRecord.style.display = "none";
  });

  btnCloseModal.addEventListener("click", () => {
    if (recorder && recorder.isRecording) {
      recorder.stop();
    }
    enrollmentModal.classList.remove("active");
  });

  // Start / Stop Recording
  btnRecord.addEventListener("click", async () => {
    if (!recorder || !recorder.isRecording) {
      // Start Recording
      recorder = new WavRecorder({
        onVolume: (val) => {
          micMeterFill.style.width = `${Math.round(val * 100)}%`;
        }
      });

      await recorder.start();
      btnRecord.textContent = "⏹ Stop Recording";
      btnRecord.classList.add("btn-secondary");
      recordStatus.textContent = "🎙 Recording in progress... Please read the script aloud.";
    } else {
      // Stop Recording
      recordStatus.textContent = "Processing audio...";
      recordedBlob = await recorder.stop();
      btnRecord.textContent = "🎙 Record Again";
      btnRecord.classList.remove("btn-secondary");

      recordStatus.textContent = "✅ Voice recorded successfully!";
      btnPreviewRecord.style.display = "inline-flex";
      btnSaveVoice.disabled = false;
    }
  });

  // Preview Recording
  btnPreviewRecord.addEventListener("click", () => {
    if (recordedBlob) {
      player.playBlob(recordedBlob);
    }
  });

  // Save & Encrypt Voice into Vault
  btnSaveVoice.addEventListener("click", async () => {
    if (!recordedBlob) return;
    const name = profileNameInput.value.trim() || "my_voice";
    btnSaveVoice.textContent = "Encrypting into Vault...";
    btnSaveVoice.disabled = true;

    try {
      const res = await ApiClient.enrollVoice(recordedBlob, name);
      activeProfile = name;
      activeProfileName.textContent = name;
      alert(`Success! Voice profile "${name}" encrypted and stored in local hardware vault.`);
      enrollmentModal.classList.remove("active");
    } catch (e) {
      alert(`Enrollment Error: ${e.message}`);
    } finally {
      btnSaveVoice.textContent = "Lock into Vault & Activate";
      btnSaveVoice.disabled = false;
    }
  });

  // Initial load
  checkServerStatus();
  loadPhrases();
  // Periodic status poll
  setInterval(checkServerStatus, 5000);
});
