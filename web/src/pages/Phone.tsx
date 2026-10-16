import { useState } from "react";
import { Leaf, Mic, MicOff, PhoneCall, PhoneOff } from "lucide-react";
import "@/styles/phone.css";
import { PhoneInput } from "@/components/ui/phone-input";
import { clock, outcome, turnLines } from "@/lib/callEvents";
import { useVoiceCall } from "@/lib/useVoiceCall";

// Public demo phone (no sign-in): the farmer's phone line in a browser. The number is the only
// identity, like caller ID on a real call (voice/app/browser_routes.py); it is remembered on
// this device. Admins use /call for the full desk view.
const STORAGE_KEY = "residue.phone";

function savedNumber(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function remember(number: string) {
  try {
    localStorage.setItem(STORAGE_KEY, number);
  } catch {
    // private window or blocked storage: the number just is not remembered
  }
}

const STATUS_TEXT = {
  idle: "Ready to call",
  connecting: "Connecting…",
  live: "On the call",
  ended: "Call ended",
} as const;

export default function Phone() {
  const [number, setNumber] = useState(savedNumber);
  const [draft, setDraft] = useState("");
  const [changing, setChanging] = useState(false);
  const { status, error, muted, view, seconds, start, hangUp, toggleMute } = useVoiceCall();
  const busy = status === "connecting" || status === "live";
  const last = view.turns[view.turns.length - 1];
  const caption = last ? turnLines(last).main : "";
  const done = outcome(view);

  if (!number || changing) {
    return (
      <main className="phone-page">
        <div className="phone-screen setup">
          <div className="phone-emblem">
            <Leaf aria-hidden="true" />
          </div>
          <h1>Residue line</h1>
          <p className="phone-sub">Enter your mobile number. The agent will know it is you.</p>
          <PhoneInput label="Your mobile number" value={draft} onChange={(e164) => setDraft(e164)} />
          <button
            className="phone-btn call"
            disabled={!draft}
            onClick={() => {
              remember(draft);
              setNumber(draft);
              setChanging(false);
            }}
          >
            Save number
          </button>
          {changing && (
            <button className="phone-link" onClick={() => setChanging(false)}>
              Cancel
            </button>
          )}
          <p className="phone-note">Demo line · synthetic data only</p>
        </div>
      </main>
    );
  }

  return (
    <main className="phone-page">
      <div className="phone-screen">
        <div className="phone-top">
          <span className={`phone-badge${status === "live" ? " live" : ""}`}>
            <span className="dot" />
            {STATUS_TEXT[status]}
          </span>
        </div>

        <div className={`phone-avatar${status === "live" ? " live" : ""}`}>
          <Leaf aria-hidden="true" />
        </div>
        <h1>Residue agent</h1>
        <p className="phone-sub">Urdu · Punjabi · Pashto · Sindhi · Saraiki</p>
        <div className="phone-timer" role="timer" aria-label="Call duration">
          {clock(seconds)}
        </div>

        <p className="phone-caption" role="status" dir="auto">
          {caption || (busy ? "Say salaam to begin." : "Tap the green button and speak.")}
        </p>
        {done && <p className="phone-result">{done}</p>}
        {error && (
          <p className="phone-error" role="alert">
            {error}
          </p>
        )}

        <div className="phone-controls">
          <button
            className="phone-round"
            aria-pressed={muted}
            aria-label={muted ? "Unmute microphone" : "Mute microphone"}
            disabled={status !== "live"}
            onClick={toggleMute}
          >
            {muted ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}
          </button>
          {busy ? (
            <button className="phone-btn end" aria-label="End call" onClick={hangUp}>
              <PhoneOff aria-hidden="true" />
            </button>
          ) : (
            <button className="phone-btn call" aria-label={status === "ended" ? "Call again" : "Start call"} onClick={() => void start(number)}>
              <PhoneCall aria-hidden="true" />
            </button>
          )}
          <span className="phone-round spacer" aria-hidden="true" />
        </div>

        <p className="phone-note">
          {number}
          {!busy && (
            <>
              {" · "}
              <button
                className="phone-link"
                onClick={() => {
                  setDraft("");
                  setChanging(true);
                }}
              >
                Change number
              </button>
            </>
          )}
        </p>
        <p className="phone-note">Use headphones · Demo line, synthetic data only</p>
      </div>
    </main>
  );
}
