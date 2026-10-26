"use client";

import { EntryForm } from "@/components/entry-form";

export default function NewEntryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl">Nouvelle pièce</h1>
        <p className="mt-1 text-muted-foreground">
          Partie double : au moins deux lignes, totaux débit = crédit.
        </p>
      </div>
      <EntryForm />
    </div>
  );
}
