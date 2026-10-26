"""ACC-02 — protection applicative des écritures comptabilisées (POSTED).

Couvre ``save``, ``QuerySet.update``, ``bulk_update``, ``bulk_create`` et ``delete``
sur ``Entry`` / ``EntryLine``. N'empêche pas le SQL direct (voir rapport ACC-02).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

# Annotations légitimes sur lignes validées (lettrage, pointage, échéance, tiers).
ENTRY_LINE_ANNOTATION_FIELDS = frozenset(
    {
        "due_on",
        "lettering",
        "bank_pointage",
        "third_party",
        "third_party_id",
    }
)

IMMUTABLE_POSTED_MSG = "Écriture validée immuable (art. 20 AUDCIF)."
IMMUTABLE_LINE_MSG = "Ligne d'une écriture validée immuable."
POST_VIA_SERVICE_MSG = "Comptabilisation uniquement via post_entry (ACC-02)."


def _normalize_field_names(fields) -> set[str]:
    names: set[str] = set()
    for field in fields:
        name = getattr(field, "name", None) or str(field)
        names.add(name)
        if name.endswith("_id"):
            names.add(name[:-3])
        else:
            names.add(f"{name}_id")
    return names


class EntryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        allow_posted_write = kwargs.pop("allow_posted_write", False)
        if allow_posted_write:
            return super().update(**kwargs)

        from apps.ledger.models import EntryStatus

        if self.filter(status=EntryStatus.POSTED).exists():
            raise ValidationError(IMMUTABLE_POSTED_MSG)
        if kwargs.get("status") == EntryStatus.POSTED:
            raise ValidationError(POST_VIA_SERVICE_MSG)
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        from apps.ledger.models import EntryStatus

        posted = [obj for obj in objs if getattr(obj, "status", None) == EntryStatus.POSTED]
        if posted:
            raise ValidationError(IMMUTABLE_POSTED_MSG)
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def delete(self):
        from apps.ledger.models import EntryStatus

        if self.filter(status=EntryStatus.POSTED).exists():
            raise ValidationError(IMMUTABLE_POSTED_MSG)
        return super().delete()


class EntryManager(models.Manager.from_queryset(EntryQuerySet)):
    pass


class EntryLineQuerySet(models.QuerySet):
    def update(self, **kwargs):
        allow_posted_write = kwargs.pop("allow_posted_write", False)
        if allow_posted_write:
            return super().update(**kwargs)

        from apps.ledger.models import EntryStatus

        fields = set(kwargs.keys())
        if self.filter(entry__status=EntryStatus.POSTED).exists():
            if not fields.issubset(ENTRY_LINE_ANNOTATION_FIELDS):
                raise ValidationError(IMMUTABLE_LINE_MSG)
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        from apps.ledger.models import Entry, EntryStatus

        field_names = _normalize_field_names(fields)
        annotation_only = field_names.issubset(
            _normalize_field_names(ENTRY_LINE_ANNOTATION_FIELDS)
        )
        entry_ids = {obj.entry_id for obj in objs if getattr(obj, "entry_id", None)}
        if entry_ids and Entry.objects.filter(pk__in=entry_ids, status=EntryStatus.POSTED).exists():
            if not annotation_only:
                raise ValidationError(IMMUTABLE_LINE_MSG)
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        allow_posted_write = False
        # bulk_create n'accepte pas de kw arbitrary — flag via attribut sur le QS
        # Utiliser EntryLine.objects.allow_posted().bulk_create(...) ou paramètre
        # stocké temporairement.
        if getattr(self, "_allow_posted_write", False):
            allow_posted_write = True
        if not allow_posted_write:
            from apps.ledger.models import Entry, EntryStatus

            entry_ids = {obj.entry_id for obj in objs if getattr(obj, "entry_id", None)}
            if entry_ids and Entry.objects.filter(
                pk__in=entry_ids, status=EntryStatus.POSTED
            ).exists():
                raise ValidationError(IMMUTABLE_LINE_MSG)
        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

    def allow_posted_write(self):
        """Chaînage pour chemins exceptionnels (non utilisé par post_entry aujourd'hui)."""
        clone = self._chain()
        clone._allow_posted_write = True
        return clone

    def delete(self):
        from apps.ledger.models import EntryStatus

        if self.filter(entry__status=EntryStatus.POSTED).exists():
            raise ValidationError(IMMUTABLE_LINE_MSG)
        return super().delete()


class EntryLineManager(models.Manager.from_queryset(EntryLineQuerySet)):
    pass
