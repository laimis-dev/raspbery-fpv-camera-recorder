"use strict";

const element = (id) => document.getElementById(id);
const livePreview = element("live-preview");
const playbackVideo = element("playback-video");
let playbackSelection = 0;
let selectedFilename = null;
let liveAvailable = false;
let librarySignature = null;

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {cache: "no-store", ...options});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || "Request failed. Please try again.");
  return result;
}

function showViewerMessage(message) {
  element("viewer-message").textContent = message;
  element("viewer-message").hidden = !message;
}

function returnToLive() {
  playbackSelection += 1;
  selectedFilename = null;
  playbackVideo.pause();
  playbackVideo.removeAttribute("src");
  playbackVideo.load();
  playbackVideo.hidden = true;
  livePreview.hidden = false;
  livePreview.src = `/live.mjpg?reconnect=${Date.now()}`;
  element("live-button").hidden = true;
  element("live-badge").hidden = false;
  element("viewer-heading").textContent = "Live view";
  element("viewer-caption").textContent = "Live preview has no sound. Saved recordings include microphone audio.";
  showViewerMessage(liveAvailable ? "" : "Waiting for camera…");
}

async function selectRecording(filename) {
  const selection = ++playbackSelection;
  selectedFilename = filename;
  playbackVideo.pause();
  playbackVideo.hidden = true;
  livePreview.hidden = true;
  livePreview.removeAttribute("src");
  element("live-button").hidden = false;
  element("live-badge").hidden = true;
  element("viewer-heading").textContent = "Replay";
  element("viewer-caption").textContent = filename;
  showViewerMessage("Preparing recording for replay…");
  element("viewer-heading").scrollIntoView({behavior: "smooth", block: "start"});
  const recordingURL = `/api/recordings/${encodeURIComponent(filename)}`;
  let firstRequest = true;
  try {
    while (selection === playbackSelection) {
      const result = await requestJSON(`${recordingURL}/prepare${firstRequest ? "?retry=1" : ""}`, {method: "POST"});
      firstRequest = false;
      if (selection !== playbackSelection) return;
      if (result.status === "error") throw new Error(result.message);
      if (result.status === "ready") {
        playbackVideo.src = `${recordingURL}/play`;
        playbackVideo.hidden = false;
        showViewerMessage("");
        playbackVideo.play().catch(() => {});
        return;
      }
      showViewerMessage(result.status === "queued" ? "Waiting to prepare this recording…" : "Preparing recording for replay…");
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
  } catch (error) {
    if (selection === playbackSelection) showViewerMessage(error.message);
  }
}

async function refreshStatus() {
  try {
    const status = await requestJSON("/api/status");
    liveAvailable = status.live_available;
    element("connection-status").textContent = status.recording_filename ? "Recording" : "Waiting for camera";
    element("connection-status").classList.toggle("recording", Boolean(status.recording_filename));
    element("capture-message").textContent = status.recording_error ? "Camera or microphone unavailable. Recording will resume when it reconnects." : "";
    if (selectedFilename === null) showViewerMessage(liveAvailable ? "" : "Waiting for camera…");
  } catch (_) {
    liveAvailable = false;
    element("connection-status").textContent = "Recorder disconnected";
    element("connection-status").classList.remove("recording");
    if (selectedFilename === null) showViewerMessage("Connection lost. Reconnect to the recorder’s Wi-Fi.");
  }
}

async function refreshRecordings() {
  try {
    const recordings = await requestJSON("/api/recordings");
    element("recording-count").textContent = recordings.length;
    element("library-message").textContent = recordings.length ? "" : "No saved recordings yet.";
    const nextSignature = JSON.stringify(recordings);
    if (nextSignature === librarySignature) return;
    librarySignature = nextSignature;
    element("recordings-list").replaceChildren();
    for (const recording of recordings) {
      const row = document.createElement("li");
      row.className = "recording-row";
      const description = document.createElement("div");
      const title = document.createElement("p");
      title.className = "recording-title";
      title.textContent = new Date(recording.modified_timestamp * 1000).toLocaleString();
      const detail = document.createElement("p");
      detail.className = "recording-detail";
      detail.textContent = `${(recording.size_bytes / 1048576).toFixed(1)} MB · ${recording.filename}`;
      description.append(title, detail);
      const actions = document.createElement("div");
      actions.className = "recording-actions";
      const playButton = document.createElement("button");
      playButton.textContent = "Replay";
      playButton.addEventListener("click", () => selectRecording(recording.filename));
      const downloadLink = document.createElement("a");
      downloadLink.className = "download-link";
      downloadLink.textContent = "Download original";
      downloadLink.href = `/api/recordings/${encodeURIComponent(recording.filename)}/download`;
      actions.append(playButton, downloadLink);
      row.append(description, actions);
      element("recordings-list").append(row);
    }
  } catch (_) {
    element("library-message").textContent = "Could not load recordings. Check your connection and refresh.";
  }
}

element("live-button").addEventListener("click", returnToLive);
element("refresh-button").addEventListener("click", refreshRecordings);
playbackVideo.addEventListener("error", () => {
  if (selectedFilename !== null) showViewerMessage("Your browser could not play this recording. Try downloading the original.");
});
livePreview.addEventListener("error", () => {
  if (selectedFilename === null) setTimeout(() => {
    if (selectedFilename === null) livePreview.src = `/live.mjpg?reconnect=${Date.now()}`;
  }, 3000);
});
refreshStatus();
refreshRecordings();
setInterval(refreshStatus, 2000);
setInterval(refreshRecordings, 10000);
