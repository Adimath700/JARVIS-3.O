const {
  Room,
  RoomEvent,
  Track,
} = window.LivekitClient || {};

const body = document.body;
const talkButton = document.getElementById("talk-button");
const talkLabel = document.getElementById("talk-label");
const connectionLabel = document.getElementById("connection-label");
const statusTitle = document.getElementById("status-title");
const statusMessage = document.getElementById("status-message");
const voiceStatus = document.getElementById("voice-status");
const securityStatus = document.getElementById("security-status");
const securityMessage = document.getElementById("security-message");
const userTranscript = document.getElementById("user-transcript");
const jarvisTranscript = document.getElementById("jarvis-transcript");
const approvalPanel = document.getElementById("approval-panel");
const approvalAction = document.getElementById("approval-action");
const approvalDetails = document.getElementById("approval-details");
const approveButton = document.getElementById("approve-button");
const denyButton = document.getElementById("deny-button");
const clock = document.getElementById("clock");
const canvas = document.getElementById("particle-field");
const context = canvas.getContext("2d");

let room = null;
let connected = false;
let holding = false;
let connecting = false;
let activeApproval = null;
let analyser = null;
let audioContext = null;
let particles = [];
let startingTurn = null;
let committingTurn = false;
let manualTurnControl = true;
let connectedAt = 0;

const stateLabels = {
  offline: "OFFLINE",
  initializing: "INITIALIZING",
  idle: "READY",
  listening: "LISTENING",
  thinking: "THINKING",
  speaking: "SPEAKING",
  tool: "EXECUTING",
  approval: "AWAITING APPROVAL",
  error: "SYSTEM ALERT",
};

function setVisualState(state, message) {
  body.dataset.state = state;
  statusTitle.textContent = stateLabels[state] || state.toUpperCase();
  voiceStatus.textContent = stateLabels[state] || state.toUpperCase();
  if (message) {
    statusMessage.textContent = message;
  }
}

async function connectJarvis() {
  if (connected || connecting) {
    return;
  }
  if (!Room) {
    setVisualState("error", "LiveKit client failed to load.");
    return;
  }
  connecting = true;
  setVisualState("initializing", "Establishing encrypted LiveKit connection");
  talkLabel.textContent = "CONNECTING";

  try {
    const response = await fetch("/api/token");
    const credentials = await response.json();
    if (!response.ok) {
      throw new Error(credentials.error || "Could not create a LiveKit token.");
    }

    room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });
    room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
    room.on(RoomEvent.Disconnected, handleDisconnected);
    room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);
    await room.connect(
      credentials.server_url,
      credentials.participant_token,
    );
    connected = true;
    connectedAt = Date.now();
    body.dataset.connected = "true";
    connectionLabel.textContent = "LIVEKIT CONNECTED";
    talkLabel.textContent = "HOLD TO TALK";
    await room.localParticipant.setMicrophoneEnabled(false);
    setVisualState("idle", "Neural link established");
  } catch (error) {
    setVisualState("error", error.message);
    talkLabel.textContent = "RETRY CONNECTION";
  } finally {
    connecting = false;
  }
}

function handleTrackSubscribed(track) {
  if (track.kind !== Track.Kind.Audio) {
    return;
  }
  const element = track.attach();
  element.autoplay = true;
  element.dataset.jarvisAudio = "true";
  document.body.appendChild(element);
  attachAnalyser(track.mediaStreamTrack);
}

function attachAnalyser(mediaStreamTrack) {
  audioContext = audioContext || new AudioContext();
  const stream = new MediaStream([mediaStreamTrack]);
  const source = audioContext.createMediaStreamSource(stream);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.72;
  source.connect(analyser);
}

function handleActiveSpeakers(speakers) {
  const jarvisSpeaking = speakers.some(
    (participant) => participant.identity !== room?.localParticipant.identity,
  );
  if (jarvisSpeaking) {
    setVisualState("speaking", "JARVIS is speaking");
  }
}

function handleDisconnected() {
  connected = false;
  connectedAt = 0;
  holding = false;
  body.dataset.connected = "false";
  connectionLabel.textContent = "OFFLINE";
  talkLabel.textContent = "CONNECT JARVIS";
  talkButton.classList.remove("active");
  startingTurn = null;
  committingTurn = false;
  setVisualState("offline", "Voice link disconnected");
}

function findAgentIdentity() {
  const participants = Array.from(room?.remoteParticipants.values() || []);
  const agent = participants.find((participant) => participant.isAgent);
  return (agent || participants[0])?.identity || "";
}

async function signalAgent(method) {
  const destinationIdentity = findAgentIdentity();
  if (!destinationIdentity) {
    throw new Error("JARVIS is still joining the room. Try again in a moment.");
  }
  return room.localParticipant.performRpc({
    destinationIdentity,
    method,
    payload: "push-to-talk",
  });
}

async function startTalking(event) {
  event.preventDefault();
  if (!connected) {
    await connectJarvis();
    return;
  }
  if (holding) {
    return;
  }
  holding = true;
  committingTurn = false;
  talkButton.classList.add("active");
  if (Number.isInteger(event.pointerId)) {
    talkButton.setPointerCapture(event.pointerId);
  }
  const prepareTurn = async () => {
    if (manualTurnControl) {
      await signalAgent("start_turn");
    }
    if (!holding) {
      return;
    }
    await room.localParticipant.setMicrophoneEnabled(true);
  };
  const pendingTurn = prepareTurn();
  startingTurn = pendingTurn;
  try {
    await pendingTurn;
    if (!holding) {
      return;
    }
    setVisualState("listening", "Listening to you");
  } catch (error) {
    holding = false;
    talkButton.classList.remove("active");
    setVisualState("error", error.message);
  } finally {
    if (startingTurn === pendingTurn) {
      startingTurn = null;
    }
  }
}

async function stopTalking(event) {
  event?.preventDefault();
  if (!holding || !room) {
    return;
  }
  holding = false;
  committingTurn = true;
  talkButton.classList.remove("active");
  setVisualState("thinking", "Processing your request");
  try {
    if (startingTurn) {
      await startingTurn;
    }
    await room.localParticipant.setMicrophoneEnabled(false);
    if (manualTurnControl) {
      await signalAgent("end_turn");
    }
  } catch (error) {
    committingTurn = false;
    setVisualState("error", error.message);
  }
}

async function resolveApproval(approved) {
  if (!activeApproval) {
    return;
  }
  const requestId = activeApproval.id;
  activeApproval = null;
  approvalPanel.hidden = true;
  await fetch(`/api/approvals/${requestId}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({approved}),
  });
}

async function pollState() {
  try {
    const response = await fetch("/api/state", {cache: "no-store"});
    if (!response.ok) {
      return;
    }
    const state = await response.json();
    manualTurnControl = state.manual_turn_control !== false;
    const startupExpired = (
      connected
      && connectedAt
      && Date.now() - connectedAt > 25000
      && ["offline", "initializing"].includes(state.status)
    );
    if (startupExpired) {
      setVisualState(
        "error",
        "Voice agent did not become ready. Check the terminal startup error.",
      );
    } else if (
      committingTurn
      && ["offline", "initializing", "idle", "listening"].includes(state.status)
    ) {
      setVisualState("thinking", "Processing your request");
    } else if (state.status === "offline" && connected) {
      setVisualState("initializing", "Waiting for JARVIS to join the room");
    } else {
      if (["thinking", "speaking", "tool", "error"].includes(state.status)) {
        committingTurn = false;
      }
      setVisualState(state.status, state.message);
    }
    if (state.user_transcript) {
      userTranscript.textContent = `YOU // ${state.user_transcript}`;
    }
    if (state.assistant_transcript) {
      jarvisTranscript.textContent = `JARVIS // ${state.assistant_transcript}`;
    }
    securityStatus.textContent = state.trusted_mode ? "OWNER" : "ACTIVE";
    securityMessage.textContent = state.trusted_mode
      ? "Owner mode executes requested actions without confirmation."
      : "Controlled actions wait for your approval.";
    const pending = state.approvals[0];
    if (pending && pending.id !== activeApproval?.id) {
      activeApproval = pending;
      approvalAction.textContent = pending.action.toUpperCase();
      approvalDetails.textContent = pending.details;
      approvalPanel.hidden = false;
    } else if (!pending && activeApproval) {
      activeApproval = null;
      approvalPanel.hidden = true;
    }
  } catch {
    if (!connected) {
      setVisualState("offline", "Waiting for the local UI server");
    }
  }
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = window.innerWidth * ratio;
  canvas.height = window.innerHeight * ratio;
  canvas.style.width = `${window.innerWidth}px`;
  canvas.style.height = `${window.innerHeight}px`;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  particles = Array.from({length: Math.min(220, window.innerWidth / 5)}, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 120 + Math.random() * Math.min(window.innerWidth, window.innerHeight) * 0.34,
    speed: 0.0004 + Math.random() * 0.0016,
    size: 0.4 + Math.random() * 1.8,
    alpha: 0.1 + Math.random() * 0.65,
    offset: (Math.random() - 0.5) * 120,
  }));
}

function animate(time) {
  context.clearRect(0, 0, window.innerWidth, window.innerHeight);
  const centerX = window.innerWidth / 2;
  const centerY = window.innerHeight * 0.48;
  let voiceLevel = 0;
  if (analyser) {
    const values = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(values);
    voiceLevel = values.reduce((sum, value) => sum + value, 0)
      / values.length
      / 150;
  } else if (body.dataset.state === "speaking") {
    voiceLevel = 0.22 + Math.sin(time / 130) * 0.08;
  }
  voiceLevel = Math.max(0, Math.min(1, voiceLevel));
  body.style.setProperty("--voice-level", voiceLevel.toFixed(3));

  particles.forEach((particle, index) => {
    const angle = particle.angle + time * particle.speed;
    const pulse = Math.sin(time / 900 + index) * 9 * (1 + voiceLevel);
    const x = centerX + Math.cos(angle) * (particle.radius + pulse);
    const y = centerY
      + Math.sin(angle) * (particle.radius * 0.5 + pulse)
      + particle.offset;
    context.beginPath();
    context.fillStyle = `rgba(255, 153, 53, ${particle.alpha})`;
    context.shadowBlur = 8 + voiceLevel * 14;
    context.shadowColor = "#ff8e2b";
    context.arc(x, y, particle.size * (1 + voiceLevel), 0, Math.PI * 2);
    context.fill();
  });
  context.shadowBlur = 0;
  requestAnimationFrame(animate);
}

talkButton.addEventListener("pointerdown", startTalking);
talkButton.addEventListener("pointerup", stopTalking);
talkButton.addEventListener("pointercancel", stopTalking);
talkButton.addEventListener("contextmenu", (event) => event.preventDefault());
approveButton.addEventListener("click", () => resolveApproval(true));
denyButton.addEventListener("click", () => resolveApproval(false));

window.addEventListener("keydown", async (event) => {
  if (event.code === "Space" && !event.repeat) {
    await startTalking(event);
  }
});
window.addEventListener("keyup", async (event) => {
  if (event.code === "Space") {
    await stopTalking(event);
  }
});
window.addEventListener("resize", resizeCanvas);

setInterval(() => {
  clock.textContent = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}, 1000);
setInterval(pollState, 300);

resizeCanvas();
requestAnimationFrame(animate);
pollState();
