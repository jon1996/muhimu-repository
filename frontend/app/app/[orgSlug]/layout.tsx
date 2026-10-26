import { AppShell } from "@/components/app-shell";
import { SessionGuard } from "@/components/session-guard";
import { UnsavedWorkProvider } from "@/components/unsaved-work-context";

export default function OrgLayout({ children }: { children: React.ReactNode }) {
  return (
    <UnsavedWorkProvider>
      <SessionGuard />
      <AppShell>{children}</AppShell>
    </UnsavedWorkProvider>
  );
}
