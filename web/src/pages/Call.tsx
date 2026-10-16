import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  Check,
  Clock,
  Globe,
  Headphones,
  Leaf,
  MessageSquareText,
  Mic,
  MicOff,
  Phone,
  PhoneCall,
  PhoneOff,
  ShieldCheck,
} from "lucide-react";
import "@/styles/call.css";
import { useVoiceCall, type CallStatus } from "@/lib/useVoiceCall";
import {
  clock,
  LANGUAGE_NAMES,
  scriptLang,
  rupees,
  turnLines,
  type CallView,
  type Lot,
} from "@/lib/callEvents";

const STATUS_LABEL: Record<CallStatus, string> = {
  idle: "Idle",
  connecting: "Connecting",
  live: "Live",
  ended: "Ended",
};

export default function Call() {
  const [phone, setPhone] = useState("+923001234567");
  const { status, error, muted, view, seconds, start, hangUp, toggleMute } = useVoiceCall();
  const [showUrdu, setShowUrdu] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const conversation = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true); // auto-scroll only when the reader is already at the end

  useEffect(() => {
    const box = conversation.current;
    if (autoScroll && nearBottom.current && box) box.scrollTop = box.scrollHeight;
  }, [view.turns, autoScroll]);

  const busy = status === "connecting" || status === "live";
  const statusText =
    status === "live"
      ? muted
        ? "Microphone muted. Listening to the agent."
        : "On the call. Speak now."
      : status === "connecting"
        ? "Connecting to the agent…"
        : status === "ended"
          ? "Call ended."
          : "Ready when you are.";

  return (
    <div className="call-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Voice agent</div>
          <h1>Live call</h1>
          <p>
            A browser fallback for the farmers’ phone line. Speak Urdu, Punjabi, Pashto, Sindhi or
            Saraiki with the same agent.
          </p>
        </div>
        <span className="session-tag">
          <Globe aria-hidden="true" />
          Browser call
        </span>
      </div>

      <div className="call-layout">
        <div className="left-column">
          <section className={`card call-card${status === "live" ? "" : " paused"}`} aria-labelledby="call-heading">
            <div className="card-top">
              <h2 id="call-heading">Your call</h2>
              <span className={`badge${status === "live" ? " live" : ""}`}>
                <span className="live-dot" />
                <span>{STATUS_LABEL[status]}</span>
              </span>
            </div>
            <div className="call-body">
              <div className="agent-visual" aria-hidden="true">
                <span className="orbit" />
                <span className="orbit-dot" />
                <div className="agent-emblem">
                  <Leaf />
                </div>
              </div>
              <h3 className="agent-title">
                A little conversation.
                <br />A new beginning.
              </h3>
              <p className="agent-sub">Residue’s farmer support agent</p>
              <div className="language-label">
                <Globe aria-hidden="true" />
                Urdu · Punjabi · Pashto · Sindhi · Saraiki
              </div>
              <div className="call-meter">
                <div className="timer" role="timer" aria-label="Call duration">
                  {clock(seconds)}
                </div>
                <div className="wave" aria-hidden="true">
                  {Array.from({ length: 23 }, (_, i) => (
                    <i key={i} />
                  ))}
                </div>
                <p className="status-text" role="status">
                  {statusText}
                </p>
              </div>
              <label className="field-label" htmlFor="phone">
                Caller phone number<span>Pakistan · +92</span>
              </label>
              <div className="phone-wrap">
                <Phone aria-hidden="true" />
                <input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={busy}
                  autoComplete="tel"
                  spellCheck={false}
                />
              </div>
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <div className="call-controls">
                {busy ? (
                  <button className="main-button end" onClick={hangUp}>
                    <PhoneOff aria-hidden="true" />
                    <span>End call</span>
                  </button>
                ) : (
                  <button className="main-button" onClick={() => void start(phone)}>
                    <PhoneCall aria-hidden="true" />
                    <span>{status === "ended" ? "Call again" : "Start call"}</span>
                  </button>
                )}
                <button
                  className="mute-button"
                  aria-pressed={muted}
                  aria-label={muted ? "Unmute microphone" : "Mute microphone"}
                  title={muted ? "Unmute microphone" : "Mute microphone"}
                  onClick={toggleMute}
                  disabled={status !== "live"}
                >
                  {muted ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}
                </button>
              </div>
              <p className="headphones">
                <Headphones aria-hidden="true" />
                <span>Use headphones so the agent doesn’t hear itself.</span>
              </p>
            </div>
            <div className="call-foot">
              <span>
                <span className="live-dot" />
                <span>{status === "live" ? "Connected in browser" : "Not connected"}</span>
              </span>
              <span>
                <ShieldCheck aria-hidden="true" />
                Synthetic demo data
              </span>
            </div>
          </section>
          <p className="demo-note">
            <strong>A familiar voice, in your language.</strong>
            <br />
            Tell the agent what’s left after your harvest. It will help arrange the next step.
          </p>
        </div>

        <section className={`card transcript${showUrdu ? "" : " hide-urdu"}`} aria-labelledby="transcript-heading">
          <div className="card-top">
            <div className="transcript-title">
              <MessageSquareText aria-hidden="true" />
              <h2 id="transcript-heading">Live transcript</h2>
            </div>
            <div className="transcript-tools">
              <label className="switch-label">
                <input type="checkbox" checked={showUrdu} onChange={(e) => setShowUrdu(e.target.checked)} />
                Show original script
              </label>
              <button
                className="autoscroll"
                aria-pressed={autoScroll}
                title="Toggle automatic scrolling"
                onClick={() => {
                  const on = !autoScroll;
                  setAutoScroll(on);
                  const box = conversation.current;
                  if (on && box) {
                    nearBottom.current = true; // jump back to the newest line
                    box.scrollTop = box.scrollHeight;
                  }
                }}
              >
                <ArrowDown aria-hidden="true" />
                <span>Auto-scroll</span>
              </button>
            </div>
          </div>
          <div
            className="conversation"
            ref={conversation}
            role="log"
            aria-label="Call conversation"
            tabIndex={0}
            onScroll={(e) => {
              const box = e.currentTarget;
              nearBottom.current = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
            }}
          >
            {view.turns.length === 0 ? (
              <div className="empty-state">
                <MessageSquareText aria-hidden="true" />
                <h3>Every harvest has a story.</h3>
                <p>
                  {busy ? "Say salaam: the conversation appears here as you speak." : "Start a call to see your conversation here."}
                  <br />
                  Speak naturally in Urdu, Punjabi, Pashto, Sindhi or Saraiki.
                </p>
              </div>
            ) : (
              <div>
                <div className="conversation-start">Today · Browser call</div>
                {view.turns.map((turn) => {
                  const { main, rtl, script } = turnLines(turn);
                  const speaking = turn.who === "agent" && !turn.final && status === "live";
                  return (
                    <article
                      key={turn.id}
                      className={`turn ${turn.who}${speaking ? " partial" : ""}`}
                      aria-busy={speaking || undefined}
                    >
                      <div className="turn-meta">
                        {turn.who === "agent" ? (
                          <>
                            <span className="tiny-avatar">
                              <Leaf aria-hidden="true" />
                            </span>
                            Agent<time>{clock(turn.at)}</time>
                            {turn.lang && turn.lang !== "other" && (
                              <span className="lang-tag">{LANGUAGE_NAMES[turn.lang]}</span>
                            )}
                            {speaking && (
                              <span className="speaking">
                                <i />
                                <i />
                                <i />
                                <span>Speaking</span>
                              </span>
                            )}
                          </>
                        ) : (
                          <>
                            {turn.lang && turn.lang !== "other" && (
                              <span className="lang-tag">{LANGUAGE_NAMES[turn.lang]}</span>
                            )}
                            Caller<time>{clock(turn.at)}</time>
                            <span className="tiny-avatar">You</span>
                          </>
                        )}
                      </div>
                      <div className="bubble">
                        <p
                          className={rtl ? "urdu-main" : undefined}
                          dir={rtl ? "rtl" : undefined}
                          lang={rtl ? scriptLang(turn.lang) : undefined}
                        >
                          {main}
                          {speaking && <span className="cursor" aria-hidden="true" />}
                        </p>
                        {script && (
                          <p className="urdu" lang={scriptLang(turn.lang)} dir="rtl">
                            {script}
                          </p>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
          <div className="transcript-footer">
            <ShieldCheck aria-hidden="true" />
            <span>Live transcription · romanised by Gemini · wording may vary slightly from speech</span>
          </div>
        </section>

        <aside className="right-rail" aria-label="Call details">
          <Captured view={view} busy={busy} />
        </aside>
      </div>
    </div>
  );
}

const FIELDS: { label: string; value: (lot: Lot) => string | undefined }[] = [
  { label: "Residue type", value: (lot) => lot.residue_label },
  { label: "Quantity", value: (lot) => (lot.quantity_tonnes === undefined ? undefined : `${lot.quantity_tonnes} tonnes`) },
  { label: "Pickup", value: (lot) => lot.pickup_text },
  { label: "Village", value: (lot) => lot.village },
  { label: "District", value: (lot) => lot.district },
];

function Captured({ view, busy }: { view: CallView; busy: boolean }) {
  const { lot, quote } = view;
  return (
    <>
      <section className="card capture">
        <div className="capture-heading">
          <div className="heading-line">
            <h2>Captured so far</h2>
            <Leaf aria-hidden="true" />
          </div>
          <p>The details that turn a call into a pickup. They fill in when the agent saves your lot.</p>
        </div>
        <dl className="capture-fields">
          {FIELDS.map(({ label, value }) => {
            const shown = lot ? value(lot) : undefined;
            return (
              <div key={label} className={`capture-field${shown ? "" : " pending"}`}>
                <dt>{label}</dt>
                <dd>{shown ?? (busy ? "Listening…" : "Not yet")}</dd>
                {shown ? (
                  <Check className="check" role="img" aria-label="Confirmed" />
                ) : (
                  <Clock className="check" role="img" aria-label="Pending" />
                )}
              </div>
            );
          })}
        </dl>
        {lot?.lot_id && (
          <div className="saved">
            <div className="saved-heading">
              <Check aria-hidden="true" />
              Lot saved
            </div>
            <div className="lot-ref">LOT-{lot.lot_id.slice(0, 8).toUpperCase()}</div>
            {quote && (
              <p className="quote">
                <strong>{rupees(quote.price_per_tonne_rupees)}</strong> per tonne
                <br />
                Your share <strong>{quote.farmer_share_percent}%</strong>
                {quote.est_farmer_amount_rupees !== undefined && <> · about {rupees(quote.est_farmer_amount_rupees)}</>}
                {quote.payment_timing && <small>{quote.payment_timing}</small>}
              </p>
            )}
          </div>
        )}
        <div className="capture-foot">
          <ShieldCheck aria-hidden="true" />
          {lot?.lot_id ? "Confirmed with the farmer" : "Read back to the farmer before saving"}
        </div>
      </section>
      {view.escalated && (
        <div className="variant" role="status">
          <div className="variant-title">
            <Headphones aria-hidden="true" />
            Escalated to a person
          </div>
          <p>Our team will follow up on the caller’s number.</p>
        </div>
      )}
      {view.confirmation?.state && (
        <div className="variant" role="status">
          <div className="variant-title">
            <Check aria-hidden="true" />
            {view.confirmation.state === "settled" ? "Payment confirmed" : "Payment disputed"}
          </div>
          <p>
            {view.confirmation.state === "settled"
              ? `Payout released${view.confirmation.farmer_amount_rupees !== undefined ? `: ${rupees(view.confirmation.farmer_amount_rupees)}` : ""}.`
              : "The payout is on hold and an admin has been alerted."}
          </p>
        </div>
      )}
    </>
  );
}
