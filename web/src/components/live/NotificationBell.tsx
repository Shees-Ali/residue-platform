import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { api } from "@/api/client";
import { NOTIFICATIONS_KEY, useNotificationPages, useUnreadCount } from "@/api/hooks";
import { apiErrorFrom } from "@/api/query";
import type { components } from "@/api/schema";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/spinner";
import type { Role } from "@/lib/auth";
import { routeFor, timeAgo } from "@/lib/notifications";
import { useLiveStatus } from "@/live/status";

type Item = components["schemas"]["NotificationOut"];

/** The bell: an unread count, and a list of what happened, newest first (EV4). */
export function NotificationBell() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const unread = useUnreadCount();
  const pages = useNotificationPages(open);
  const count = unread.data?.unread ?? 0;

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const changed = () => void qc.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
  const readOne = useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.POST("/api/notifications/{notification_id}/read", {
        params: { path: { notification_id: id } },
      });
      if (!response.ok) throw apiErrorFrom(error, response.status);
    },
    onSettled: changed,
  });
  const readAll = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/api/notifications/read-all");
      if (!response.ok) throw apiErrorFrom(error, response.status);
    },
    onSettled: changed,
  });

  function openItem(n: Item) {
    if (!n.read) readOne.mutate(n.id);
    setOpen(false);
    navigate(routeFor(n.type, (user?.role ?? "buyer") as Role));
  }

  const items = pages.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="bell" ref={box}>
      <button
        type="button"
        className="bell-button"
        aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell size={18} />
        {count > 0 && <span className="bell-badge">{count > 99 ? "99+" : count}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <div className="bell-head">
            <strong>Notifications</strong>
            <Button
              size="sm"
              variant="ghost"
              loading={readAll.isPending}
              disabled={count === 0}
              onClick={() => readAll.mutate()}
            >
              Mark all read
            </Button>
          </div>
          {pages.isPending ? (
            <div aria-busy="true" className="bell-body">
              <Skeleton className="h-14" />
              <Skeleton className="h-14" />
            </div>
          ) : pages.isError ? (
            <div className="bell-body bell-empty">
              <p>Could not load your notifications.</p>
              <Button size="sm" variant="outline" loading={pages.isFetching} onClick={() => void pages.refetch()}>
                Try again
              </Button>
            </div>
          ) : items.length === 0 ? (
            <div className="bell-body bell-empty">No notifications yet</div>
          ) : (
            <ul className="bell-body">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={`bell-item ${n.read ? "" : "bell-unread"} ${n.level === "warning" ? "bell-warning" : ""}`}
                    onClick={() => openItem(n)}
                  >
                    <span className="bell-title">
                      {!n.read && <span className="bell-dot" aria-label="Unread" />}
                      {n.title}
                    </span>
                    <span className="bell-text">{n.body}</span>
                    <span className="bell-time">{timeAgo(n.created_at)}</span>
                  </button>
                </li>
              ))}
              {pages.hasNextPage && (
                <li className="bell-more">
                  <Button
                    size="sm"
                    variant="outline"
                    loading={pages.isFetchingNextPage}
                    onClick={() => void pages.fetchNextPage()}
                  >
                    Load older
                  </Button>
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** Shown when the live listener is down: the page still refreshes, just more slowly. */
export function LiveChip() {
  const status = useLiveStatus();
  if (status !== "paused") return null;
  return (
    <span className="live-chip" role="status">
      Live updates paused · refreshing every 30 s
    </span>
  );
}
