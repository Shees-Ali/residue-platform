import { useEffect, useRef, useState } from "react";
import { applyEvent, emptyView, type CallEvent, type CallView } from "@/lib/callEvents";

// Browser mic fallback for the phone line (voice/app/browser_routes.py has the protocol):
// send {"phone"} then 16 kHz PCM16 mic frames; play the 24 kHz PCM16 replies; on
// {"type":"interrupt"} stop whatever agent audio is still queued. Live events (transcript,
// Roman Urdu, saved lot, quote) are folded into `view` by lib/callEvents.
// Shared by the admin /call desk and the public /phone page.
// Default: this page's own origin, which Vite proxies to the voice service (so one HTTPS tunnel
// serves a phone); set VITE_VOICE_WS_URL when the voice service lives elsewhere (deployed).
const voiceWsUrl = () =>
  import.meta.env.VITE_VOICE_WS_URL ??
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/browser`;
const PLAYBACK_LEAD_S = 0.08; // absorbs network jitter between reply chunks

// Runs at the device rate (any browser), averages down to 16 kHz (a box filter against
// aliasing) and posts 40 ms frames of 16-bit PCM.
const MIC_WORKLET = `
class Mic extends AudioWorkletProcessor {
  step = sampleRate / 16000; t = 0; sum = 0; count = 0;
  buf = new Int16Array(640); n = 0;
  process([input]) {
    for (const s of input[0] ?? []) {
      this.sum += s; this.count++; this.t++;
      if (this.t < this.step) continue;
      this.t -= this.step;
      const v = this.sum / this.count;
      this.sum = 0; this.count = 0;
      this.buf[this.n++] = Math.max(-1, Math.min(1, v)) * 0x7fff;
      if (this.n === this.buf.length) { this.port.postMessage(this.buf.slice().buffer); this.n = 0; }
    }
    return true;
  }
}
registerProcessor("mic", Mic);`;

export type CallStatus = "idle" | "connecting" | "live" | "ended";

export function useVoiceCall() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [error, setError] = useState("");
  const [muted, setMuted] = useState(false);
  const [view, setView] = useState<CallView>(emptyView);
  const [seconds, setSeconds] = useState(0);
  const hangUp = useRef<() => void>(() => {});
  const mutedRef = useRef(false);
  const startedAt = useRef(0);

  useEffect(() => () => hangUp.current(), []);

  useEffect(() => {
    if (status !== "live") return;
    const timer = setInterval(() => setSeconds((Date.now() - startedAt.current) / 1000), 500);
    return () => clearInterval(timer);
  }, [status]);

  function toggleMute() {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
  }

  async function start(phone: string) {
    setError("");
    setStatus("connecting");
    setView(emptyView);
    setSeconds(0);
    mutedRef.current = false;
    setMuted(false);
    // Everything this call owns; stop() is idempotent and only ever touches this call.
    let stopped = false;
    let mic: MediaStream | undefined;
    let micCtx: AudioContext | undefined;
    let outCtx: AudioContext | undefined;
    let ws: WebSocket | undefined;
    const stop = (message?: string) => {
      if (stopped) return;
      stopped = true;
      ws?.close();
      mic?.getTracks().forEach((t) => t.stop());
      void micCtx?.close().catch(() => {});
      void outCtx?.close().catch(() => {});
      if (message) setError(message);
      setStatus("ended");
    };
    hangUp.current = () => stop();

    try {
      micCtx = new AudioContext();
      outCtx = new AudioContext({ sampleRate: 24000 });
      mic = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      if (stopped) return void mic.getTracks().forEach((t) => t.stop());
      const url = URL.createObjectURL(new Blob([MIC_WORKLET], { type: "text/javascript" }));
      try {
        await micCtx.audioWorklet.addModule(url);
      } finally {
        URL.revokeObjectURL(url);
      }
      if (stopped) return;
      if (micCtx.sampleRate < 16000) throw new Error("audio device rate below 16 kHz");
      const node = new AudioWorkletNode(micCtx, "mic", { numberOfInputs: 1, numberOfOutputs: 0 });
      micCtx.createMediaStreamSource(mic).connect(node);

      const out = outCtx;
      const playing = new Set<AudioBufferSourceNode>();
      let playAt = 0;
      let helloSent = false;
      const socket = (ws = new WebSocket(voiceWsUrl()));
      socket.binaryType = "arraybuffer";
      socket.onopen = () => {
        socket.send(JSON.stringify({ phone }));
        helloSent = true;
        startedAt.current = Date.now();
        setStatus("live");
      };
      socket.onerror = () => stop("Could not reach the voice service.");
      socket.onclose = () => stop();
      socket.onmessage = (e: MessageEvent<ArrayBuffer | string>) => {
        if (typeof e.data === "string") {
          let msg: { type?: string; message?: string };
          try {
            msg = JSON.parse(e.data);
          } catch {
            return;
          }
          if (msg.type === "interrupt") {
            playing.forEach((s) => s.stop());
            playing.clear();
            playAt = 0;
          } else if (msg.type === "error") {
            setError(msg.message ?? "The call failed.");
          } else {
            const at = (Date.now() - startedAt.current) / 1000;
            setView((v) => applyEvent(v, msg as CallEvent, at));
          }
          return;
        }
        const pcm = new Int16Array(e.data);
        const buffer = out.createBuffer(1, pcm.length, 24000);
        buffer.getChannelData(0).set(Float32Array.from(pcm, (s) => s / 0x8000));
        const src = out.createBufferSource();
        src.buffer = buffer;
        src.connect(out.destination);
        if (playAt < out.currentTime) playAt = out.currentTime + PLAYBACK_LEAD_S;
        src.start(playAt);
        playAt += buffer.duration;
        playing.add(src);
        src.onended = () => playing.delete(src);
      };
      node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        if (helloSent && socket.readyState === WebSocket.OPEN) {
          // Muted sends silence, like a muted phone: Gemini needs it to hear the turn end.
          socket.send(mutedRef.current ? new ArrayBuffer(e.data.byteLength) : e.data);
        }
      };
    } catch {
      stop("Microphone or audio is not available. Allow mic access and try again.");
    }
  }

  return { status, error, muted, view, seconds, start, hangUp: () => hangUp.current(), toggleMute };
}
