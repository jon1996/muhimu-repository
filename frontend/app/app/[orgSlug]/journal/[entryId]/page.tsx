"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useRef } from "react";

import { EntryForm } from "@/components/entry-form";
import { useTenant } from "@/components/tenant-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { JournalEntry, SourceDocument } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function EntryDetailPage() {
  const { entryId } = useParams<{ entryId: string }>();
  const { orgSlug, companyId } = useTenant();
  const router = useRouter();
  const queryClient = useQueryClient();
  const entry = useQuery({
    queryKey: ["entry", orgSlug, companyId, entryId],
    queryFn: () => api<JournalEntry>(`/api/ledger/entries/${entryId}`, { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId && entryId),
  });

  const reverse = useMutation({
    mutationFn: () =>
      api<JournalEntry>(`/api/ledger/entries/${entryId}/reverse`, {
        method: "POST",
        body: JSON.stringify({ description: "" }),
        orgSlug,
        companyId,
      }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["entries"] });
      router.replace(`/app/${orgSlug}/journal/${created.id}`);
    },
  });

  if (entry.isLoading) {
    return <p className="text-muted-foreground">Chargement de la pièce…</p>;
  }
  if (!entry.data) {
    return <p className="text-destructive">Pièce introuvable.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl">{entry.data.number_display || "Brouillon"}</h1>
          <p className="mt-1 text-muted-foreground">
            {entry.data.status === "posted"
              ? "Validée — montants immuables (art. 20). L’échéance reste saisissable (notes 7 et 17)."
              : "Brouillon modifiable."}
          </p>
        </div>
        {entry.data.status === "posted" && !entry.data.reversed_entry_id && (
          <Button variant="outline" onClick={() => reverse.mutate()} disabled={reverse.isPending}>
            Contrepasser
          </Button>
        )}
      </div>
      <EntryForm initial={entry.data} />
      <EntryDocuments entryId={entry.data.id} />
    </div>
  );
}

function EntryDocuments({ entryId }: { entryId: string }) {
  const { orgSlug, companyId, membership } = useTenant();
  const canWrite = ["owner", "admin", "accountant"].includes(membership?.role ?? "");
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const documents = useQuery({
    queryKey: ["documents", orgSlug, companyId, entryId],
    queryFn: () =>
      api<SourceDocument[]>(`/api/ledger/documents?entry_id=${entryId}`, { orgSlug, companyId }),
    enabled: Boolean(orgSlug && companyId && entryId),
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api<SourceDocument>(`/api/ledger/documents?entry_id=${entryId}`, {
        method: "POST",
        body,
        orgSlug,
        companyId,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", orgSlug, companyId, entryId] }),
  });

  const download = async (doc: SourceDocument) => {
    const res = await fetch(`${API_URL}/api/ledger/documents/${doc.id}/file`, {
      credentials: "include",
      headers: {
        "X-Organization-Slug": orgSlug,
        "X-Company-Id": companyId,
      },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = doc.original_name;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pièces justificatives</CardTitle>
        <CardDescription>Datées, classées, conservées 10 ans (art. 17-3, 24).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {upload.isError && (
          <p className="text-sm text-destructive">
            {upload.error instanceof ApiError ? upload.error.message : "Téléversement impossible."}
          </p>
        )}
        <ul className="space-y-2 text-sm">
          {(documents.data ?? []).map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-3">
              <button type="button" className="text-left hover:underline" onClick={() => download(doc)}>
                {doc.original_name}
                <span className="ml-2 text-muted-foreground">
                  jusqu’au {doc.keep_until} · {doc.sha256.slice(0, 8)}
                </span>
              </button>
            </li>
          ))}
          {documents.data?.length === 0 && (
            <li className="text-muted-foreground">Aucune pièce jointe.</li>
          )}
        </ul>
        {canWrite && (
          <>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
            <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
              {upload.isPending ? "Envoi…" : "Joindre une pièce"}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
