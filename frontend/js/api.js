/**
 * EchoLife API Client
 * Connects frontend to local FastAPI server on localhost:8000.
 */

const API_BASE = "http://127.0.0.1:8000/api";

const ApiClient = {
  async getStatus() {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (e) {
      console.warn("[EchoLife API] Status fetch failed:", e.message);
      return { status: "disconnected", error: e.message };
    }
  },

  async getPhrases() {
    const res = await fetch(`${API_BASE}/phrases`);
    if (!res.ok) throw new Error("Failed to load AAC phrases");
    return await res.json();
  },

  async getProfiles() {
    const res = await fetch(`${API_BASE}/profiles`);
    if (!res.ok) throw new Error("Failed to load voice profiles");
    return await res.json();
  },

  async enrollVoice(wavBlob, profileName = "default_user") {
    const formData = new FormData();
    formData.append("audio_file", wavBlob, `${profileName}.wav`);
    formData.append("profile_name", profileName);

    const res = await fetch(`${API_BASE}/enroll`, {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Enrollment failed");
    }
    return data;
  },

  async synthesizeSpeech(text, profileName = "default_user", language = "en") {
    const res = await fetch(`${API_BASE}/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text,
        profile_name: profileName,
        language: language
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Synthesis failed" }));
      throw new Error(err.detail || "Synthesis failed");
    }

    // Returns audio/wav Blob
    return await res.blob();
  }
};

window.ApiClient = ApiClient;
