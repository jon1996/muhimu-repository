"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useUnsavedWork } from "@/components/unsaved-work-context";
import { Button } from "@/components/ui/button";
import { clearCsrf } from "@/lib/api";
import {
  emitSessionExpired,
  parseSessionExpiredHeader,
  SESSION_EXPIRED_EVENT,
  sessionExpiredLoginMessage,
  type SessionExpiredReason,
} from "@/lib/session-events";

type SessionStatus = {
  authenticated: boolean;
  idle_timeout_seconds: number;
  absolute_timeout_seconds: number;
  warn_before_seconds: number;
  idle_expires_at: number | null;
  absolute_expires_at: number | null;
};

function redirectToLogin(router: ReturnType<typeof useRouter>, reason: SessionExpiredReason) {
  const message = sessionExpiredLoginMessage(reason);
  router.replace(`/login?reason=${encodeURIComponent(reason)}&message=${encodeURIComponent(message)}`);
}

export function SessionGuard() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { hasUnsavedWork } = useUnsavedWork();
  const [idleWarning, setIdleWarning] = useState(false);
  const pendingRedirect = useRef<SessionExpiredReason | null>(null);

  const finalizeExpiry = (reason: SessionExpiredReason, force = false) => {
    if (hasUnsavedWork && !force) {
      pendingRedirect.current = reason;
      return;
    }
    clearCsrf();
    queryClient.clear();
    redirectToLogin(router, reason);
  };

  useEffect(() => {
    const onExpired = (event: Event) => {
      const detail = (event as CustomEvent<{ reason: SessionExpiredReason }>).detail;
      finalizeExpiry(detail?.reason ?? "unknown");
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  });

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/auth/session`,
          {
            credentials: "include",
            cache: "no-store",
            headers: {
              Accept: "application/json",
              "X-Muhimu-Session-Activity": "background",
            },
          },
        );
        if (cancelled) return;
        if (res.status === 401) {
          const reason = parseSessionExpiredHeader(res.headers.get("X-Muhimu-Session-Expired"));
          emitSessionExpired(reason);
          return;
        }
        if (!res.ok) return;
        const status = (await res.json()) as SessionStatus;
        if (!status.authenticated || !status.idle_expires_at) {
          setIdleWarning(false);
          return;
        }
        const nowSec = Date.now() / 1000;
        const idleLeft = status.idle_expires_at - nowSec;
        const absLeft =
          status.absolute_expires_at != null
            ? status.absolute_expires_at - nowSec
            : Number.POSITIVE_INFINITY;
        if (idleLeft <= 0 || absLeft <= 0) {
          emitSessionExpired(idleLeft <= 0 ? "idle" : "absolute");
          return;
        }
        setIdleWarning(idleLeft <= status.warn_before_seconds);
      } catch {
        /* réseau : ne pas déconnecter agressivement */
      }
    };

    void poll();
    const id = window.setInterval(poll, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [router, queryClient]);

  return (
    <>
      {idleWarning && !pendingRedirect.current && (
        <div
          role="status"
          className="fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border border-border bg-card p-4 text-sm shadow-lg"
        >
          <p className="font-medium text-foreground">Session bientôt expirée</p>
          <p className="mt-1 text-muted-foreground">
            En l&apos;absence d&apos;activité, vous serez déconnecté pour protéger vos données.
            Enregistrez votre travail ou naviguez dans l&apos;application.
          </p>
        </div>
      )}
      {pendingRedirect.current && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-background/80 p-4">
          <div className="max-w-md rounded-lg border border-border bg-card p-6 shadow-lg">
            <p className="font-medium">Modifications non enregistrées</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Votre session a expiré. Enregistrez ce que vous pouvez encore, puis reconnectez-vous.
              Les données comptables ne sont pas copiées dans le navigateur.
            </p>
            <Button
              className="mt-4 w-full"
              onClick={() => {
                const reason = pendingRedirect.current ?? "unknown";
                pendingRedirect.current = null;
                finalizeExpiry(reason, true);
              }}
            >
              Aller à la connexion
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
