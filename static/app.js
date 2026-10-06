const conversation = document.getElementById("conversation");
const scrollArea = document.getElementById("chat-scroll");
const form = document.getElementById("question-form");
const input = document.getElementById("question-input");
const sendButton = document.getElementById("send-button");
const voiceButton = document.getElementById("voice-button");
const voiceStatus = document.getElementById("voice-status");
const stopAudioButton = document.getElementById("stop-audio");
const indexStatus = document.getElementById("index-status");

let socket = null;
let connectPromise = null;
let ready = false;
let turnActive = false;
let microphone = null;
let captureContext = null;
let captureNode = null;
let captureSource = null;
let captureSink = null;
let captureTimer = null;
let recordedFrames = 0;
let playbackContext = null;
let playbackTime = 0;
let playbackQueue = Promise.resolve();
let audioEpoch = 0;
let suppressAudio = false;
const playingSources = new Set();
let answerNode = null;
let answerText = null;
let answerSources = null;
let voiceMessageBubble = null;
let voiceTranscript = "";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setVoiceStatus(message) { voiceStatus.textContent = message; }
function scrollToBottom() { scrollArea.scrollTop = scrollArea.scrollHeight; }

function clearWelcome() {
  conversation.querySelector(".welcome")?.remove();
}

function addUserMessage(message) {
  clearWelcome();
  const row = element("div", "message-row user-row");
  const bubble = element("div", "message-bubble user-bubble", message);
  row.appendChild(bubble);
  conversation.appendChild(row);
  scrollToBottom();
  return bubble;
}

function startAnswer() {
  if (answerNode) return;
  const row = element("div", "message-row assistant-row");
  row.appendChild(element("div", "assistant-avatar", "✦"));
  const content = element("div", "assistant-content");
  content.appendChild(element("div", "assistant-name", "SmartHelper"));
  answerText = element("p", "answer-text", "");
  answerSources = element("div", "source-list");
  content.append(answerText, answerSources);
  row.appendChild(content);
  conversation.appendChild(row);
  answerNode = row;
  scrollToBottom();
}

function displaySources(citations) {
  startAnswer();
  answerSources.replaceChildren();
  if (!citations?.length) return;
  for (const [index, citation] of citations.entries()) {
    const link = element("a", "source-card");
    link.href = citation.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.appendChild(element("span", "source-number", String(index + 1)));
    const body = element("span", "source-body");
    body.appendChild(element("strong", "source-title", citation.title));
    body.appendChild(element("span", "source-section", citation.heading));
    link.append(body, element("span", "source-arrow", "↗"));
    answerSources.appendChild(link);
  }
  scrollToBottom();
}

function resetAnswer() {
  answerNode = null;
  answerText = null;
  answerSources = null;
}

function stopPlayback() {
  audioEpoch++;
  for (const source of playingSources) {
    try { source.stop(); } catch { /* Already finished. */ }
  }
  playingSources.clear();
  playbackTime = 0;
  stopAudioButton.hidden = true;
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function playPcm(encoded) {
  if (!playbackContext) playbackContext = new AudioContext();
  if (playbackContext.state === "suspended") await playbackContext.resume();
  const bytes = base64ToBytes(encoded);
  if (bytes.length < 2 || bytes.length % 2) return;
  const samples = bytes.length / 2;
  const audioBuffer = playbackContext.createBuffer(1, samples, 24000);
  const channel = audioBuffer.getChannelData(0);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
  const source = playbackContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(playbackContext.destination);
  source.onended = () => {
    playingSources.delete(source);
    if (!playingSources.size) stopAudioButton.hidden = true;
  };
  playbackTime = Math.max(playbackTime, playbackContext.currentTime + 0.04);
  source.start(playbackTime);
  playbackTime += audioBuffer.duration;
  playingSources.add(source);
  stopAudioButton.hidden = false;
}

function onServerEvent(event) {
  switch (event.type) {
    case "ready":
      ready = true;
      setVoiceStatus("Tap the microphone to speak. Tap again to finish.");
      break;
    case "sources":
      displaySources(event.citations);
      setVoiceStatus("Answering from public documentation…");
      break;
    case "user_transcript":
      if (typeof event.text === "string" && event.text.trim()) {
        voiceTranscript = event.text.trim();
        if (voiceMessageBubble) voiceMessageBubble.textContent = voiceTranscript;
        scrollToBottom();
      }
      break;
    case "answer_delta":
      startAnswer();
      answerText.textContent += event.text || "";
      scrollToBottom();
      break;
    case "audio":
      if (!suppressAudio) {
        const epoch = audioEpoch;
        playbackQueue = playbackQueue.then(() => epoch === audioEpoch ? playPcm(event.audio) : null)
          .catch(() => setVoiceStatus("Audio playback failed; the answer is shown as text."));
      }
      break;
    case "turn_done":
      if (voiceMessageBubble && !voiceTranscript) voiceMessageBubble.textContent = "Audio question (transcript unavailable)";
      voiceMessageBubble = null;
      if (event.answer && answerText && !answerText.textContent) answerText.textContent = event.answer;
      turnActive = false;
      sendButton.disabled = false;
      resetAnswer();
      setVoiceStatus("Tap the microphone to ask another question.");
      break;
    case "error":
      if (voiceMessageBubble && !voiceTranscript) voiceMessageBubble.textContent = "Audio question (transcript unavailable)";
      voiceMessageBubble = null;
      turnActive = false;
      sendButton.disabled = false;
      if (answerText && !answerText.textContent) answerText.textContent = event.message;
      resetAnswer();
      setVoiceStatus(event.message || "Voice session error.");
      break;
  }
}

function ensureSocket() {
  if (socket?.readyState === WebSocket.OPEN && ready) return Promise.resolve();
  if (connectPromise) return connectPromise;
  setVoiceStatus("Connecting to Qwen Realtime…");
  connectPromise = new Promise((resolve, reject) => {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${scheme}//${location.host}/api/realtime`);
    socket.onmessage = message => {
      let event;
      try { event = JSON.parse(message.data); } catch { return; }
      onServerEvent(event);
      if (event.type === "ready") resolve();
      if (event.type === "error" && !ready) reject(new Error(event.message));
    };
    socket.onerror = () => reject(new Error("Could not open the voice connection."));
    socket.onclose = () => {
      ready = false;
      socket = null;
      connectPromise = null;
      turnActive = false;
      sendButton.disabled = false;
    };
  });
  return connectPromise;
}

function sendEvent(event) {
  if (!socket || socket.readyState !== WebSocket.OPEN || !ready) throw new Error("Voice session is disconnected.");
  socket.send(JSON.stringify(event));
}

function bytesToBase64(bytes) {
  let text = "";
  for (let i = 0; i < bytes.length; i++) text += String.fromCharCode(bytes[i]);
  return btoa(text);
}

function pcm16FromFloat(input, sourceRate) {
  const size = Math.floor(input.length * 16000 / sourceRate);
  const bytes = new Uint8Array(size * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < size; i++) {
    const position = i * sourceRate / 16000;
    const left = Math.floor(position);
    const fraction = position - left;
    const sample = input[left] * (1 - fraction) + input[Math.min(left + 1, input.length - 1)] * fraction;
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(i * 2, clamped < 0 ? clamped * 32768 : clamped * 32767, true);
  }
  return bytes;
}

async function stopMicrophone(commit = true) {
  if (!microphone) return;
  clearTimeout(captureTimer);
  captureNode?.disconnect();
  captureSource?.disconnect();
  captureSink?.disconnect();
  microphone.getTracks().forEach(track => track.stop());
  microphone = null;
  captureNode = null;
  captureSource = null;
  captureSink = null;
  if (captureContext) await captureContext.close();
  captureContext = null;
  voiceButton.classList.remove("recording");
  voiceButton.setAttribute("aria-label", "Start voice question");
  if (commit && recordedFrames) {
    voiceMessageBubble = addUserMessage(voiceTranscript || "Transcribing…");
    resetAnswer();
    sendEvent({ type: "commit" });
    setVoiceStatus("Checking the documentation…");
  } else if (commit) {
    turnActive = false;
    sendButton.disabled = false;
    setVoiceStatus("No audio was captured. Please try again.");
  }
}

async function toggleMicrophone() {
  if (microphone) { await stopMicrophone(); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
    setVoiceStatus("Microphone access is unavailable here. You can type your question.");
    return;
  }
  voiceButton.disabled = true;
  try {
    await ensureSocket();
    if (turnActive) {
      sendEvent({ type: "cancel" });
      stopPlayback();
      resetAnswer();
    }
    suppressAudio = false;
    microphone = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    captureContext = new AudioContext();
    await captureContext.resume();
    captureSource = captureContext.createMediaStreamSource(microphone);
    captureNode = captureContext.createScriptProcessor(4096, 1, 1);
    captureSink = captureContext.createGain();
    captureSink.gain.value = 0;
    captureSource.connect(captureNode);
    captureNode.connect(captureSink);
    captureSink.connect(captureContext.destination);
    recordedFrames = 0;
    voiceTranscript = "";
    voiceMessageBubble = null;
    captureNode.onaudioprocess = event => {
      if (!microphone || !ready || socket.bufferedAmount > 500_000) return;
      const pcm = pcm16FromFloat(event.inputBuffer.getChannelData(0), captureContext.sampleRate);
      recordedFrames++;
      sendEvent({ type: "audio", audio: bytesToBase64(pcm) });
    };
    turnActive = true;
    sendButton.disabled = true;
    voiceButton.classList.add("recording");
    voiceButton.setAttribute("aria-label", "Finish voice question");
    setVoiceStatus("Listening… tap the microphone to finish (30 seconds max).");
    captureTimer = setTimeout(() => stopMicrophone().catch(() => {}), 30000);
  } catch (error) {
    await stopMicrophone(false);
    turnActive = false;
    sendButton.disabled = false;
    setVoiceStatus(`${error.message} You can type your question.`);
  } finally {
    voiceButton.disabled = false;
  }
}

async function askText(question) {
  question = question.trim();
  if (!question || turnActive) return;
  turnActive = true;
  sendButton.disabled = true;
  try {
    await ensureSocket();
    stopPlayback();
    suppressAudio = false;
    addUserMessage(question);
    resetAnswer();
    input.value = "";
    sendEvent({ type: "text", text: question });
    setVoiceStatus("Checking the documentation…");
  } catch (error) {
    turnActive = false;
    sendButton.disabled = false;
    setVoiceStatus(error.message);
  }
}

voiceButton.addEventListener("click", () => toggleMicrophone());
stopAudioButton.addEventListener("click", () => { suppressAudio = true; stopPlayback(); setVoiceStatus("Audio stopped."); });
form.addEventListener("submit", event => { event.preventDefault(); askText(input.value); });
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); askText(input.value); }
});
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
});
document.querySelectorAll(".prompt-chip").forEach(button => {
  button.addEventListener("click", () => askText(button.dataset.question));
});

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error();
    const data = await response.json();
    indexStatus.textContent = `${data.documents} public documents · ${data.sections} sections`;
    if (!data.qwen_realtime_configured && !turnActive) setVoiceStatus("Add a QwenCloud API key in .env, then restart the app.");
  } catch {
    indexStatus.textContent = "Could not load document status";
    if (!turnActive) setVoiceStatus("Connection unavailable. Please refresh the page.");
  }
}

document.getElementById("refresh-button").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  indexStatus.textContent = "Refreshing…";
  try {
    const response = await fetch("/api/reindex", { method: "POST" });
    if (!response.ok) throw new Error();
    await loadStatus();
  } catch {
    indexStatus.textContent = "Refresh failed";
  } finally {
    button.disabled = false;
  }
});

loadStatus();
window.addEventListener("focus", loadStatus);
document.addEventListener("visibilitychange", () => { if (!document.hidden) loadStatus(); });
setInterval(loadStatus, 15000);
