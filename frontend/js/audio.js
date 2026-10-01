/**
 * EchoLife Audio Engine
 * Client-side 16-bit PCM WAV Recorder and WebAudio Player.
 */

class WavRecorder {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 22050;
    this.audioContext = null;
    this.mediaStream = null;
    this.processor = null;
    this.source = null;
    this.analyser = null;
    this.isRecording = false;
    this.recordedBuffers = [];
    this.onVolume = options.onVolume || (() => {});
    this._meterInterval = null;
  }

  async start() {
    this.recordedBuffers = [];
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: this.sampleRate
    });

    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    this.source = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;

    // Buffer size 4096, 1 input channel, 1 output channel
    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.source.connect(this.analyser);
    this.analyser.connect(this.processor);
    this.processor.connect(this.audioContext.destination);

    this.processor.onaudioprocess = (e) => {
      if (!this.isRecording) return;
      const inputData = e.inputBuffer.getChannelData(0);
      this.recordedBuffers.push(new Float32Array(inputData));
    };

    // Live volume meter loop
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this._meterInterval = setInterval(() => {
      if (!this.isRecording) return;
      this.analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;
      const normalized = Math.min(1.0, average / 100);
      this.onVolume(normalized);
    }, 50);

    this.isRecording = true;
  }

  async stop() {
    this.isRecording = false;
    clearInterval(this._meterInterval);
    this.onVolume(0);

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }

    const merged = this._mergeBuffers(this.recordedBuffers);
    const wavBlob = this._encodeWAV(merged, this.audioContext.sampleRate);

    if (this.audioContext && this.audioContext.state !== "closed") {
      await this.audioContext.close();
    }

    return wavBlob;
  }

  _mergeBuffers(buffers) {
    let totalLength = 0;
    for (let b of buffers) totalLength += b.length;
    const result = new Float32Array(totalLength);
    let offset = 0;
    for (let b of buffers) {
      result.set(b, offset);
      offset += b.length;
    }
    return result;
  }

  _encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // RIFF identifier
    this._writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    this._writeString(view, 8, "WAVE");

    // fmt subchunk
    this._writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);          // SubChunk1Size (16 for PCM)
    view.setUint16(20, 1, true);           // AudioFormat (1 = PCM)
    view.setUint16(22, 1, true);           // NumChannels (1 = Mono)
    view.setUint32(24, sampleRate, true);  // SampleRate
    view.setUint32(28, sampleRate * 2, true); // ByteRate (SampleRate * 1 * 2)
    view.setUint16(32, 2, true);           // BlockAlign (1 * 2)
    view.setUint16(34, 16, true);          // BitsPerSample (16-bit)

    // data subchunk
    this._writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    // Write PCM samples (convert float32 to signed 16-bit int)
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: "audio/wav" });
  }

  _writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
}

class AudioPlayer {
  constructor() {
    this.currentAudio = null;
  }

  playBlob(blob, onStart, onEnd) {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    this.currentAudio = audio;

    audio.onplay = () => {
      if (onStart) onStart();
    };

    audio.onended = () => {
      URL.revokeObjectURL(url);
      this.currentAudio = null;
      if (onEnd) onEnd();
    };

    audio.onerror = () => {
      URL.revokeObjectURL(url);
      this.currentAudio = null;
      if (onEnd) onEnd();
    };

    audio.play().catch(e => {
      console.warn("Autoplay error:", e);
      if (onEnd) onEnd();
    });
  }

  stop() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
  }
}

window.WavRecorder = WavRecorder;
window.AudioPlayer = AudioPlayer;
