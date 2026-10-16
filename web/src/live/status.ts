import { createContext, useContext } from "react";

/** off: no live updates (the API does not mirror, or nobody is signed in). connecting: waiting for
 * the first answer. live: the inbox listener is healthy. paused: it is not (offline, blocked). */
export type LiveStatus = "off" | "connecting" | "live" | "paused";

export const LiveContext = createContext<LiveStatus>("off");
export const useLiveStatus = () => useContext(LiveContext);
