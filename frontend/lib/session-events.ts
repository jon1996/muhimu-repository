export type SessionExpiredReason = "idle" | "absolute" | "unknown";

export const SESSION_EXPIRED_EVENT = "muhimu:session-expired";

export function emitSessionExpired(reason: SessionExpiredReason) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(SESSION_EXPIRED_EVENT, { detail: { reason } }),
  );
}

export function parseSessionExpiredHeader(value: string | null): SessionExpiredReason {
  if (value === "idle" || value === "absolute") return value;
  return "unknown";
}

export function sessionExpiredLoginMessage(reason: SessionExpiredReason): string {
  if (reason === "idle") {
    return "Votre session a expiré après une période d'inactivité. Reconnectez-vous pour continuer.";
  }
  if (reason === "absolute") {
    return "Votre session a atteint la durée maximale autorisée. Reconnectez-vous pour continuer.";
  }
  return "Votre session n'est plus valide. Reconnectez-vous pour continuer.";
}
