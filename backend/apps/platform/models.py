import uuid

from django.conf import settings
from django.db import models


class DemoGrant(models.Model):
    """Accès sandbox (PME et/ou cabinet de démo), géré uniquement depuis la console SaaS."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="demo_grant",
    )
    access_pme = models.BooleanField(default=True)
    access_cabinet = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demo_grants_given",
    )
    notes = models.CharField(max_length=255, blank=True)
    last_emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "accès démo"
        verbose_name_plural = "accès démo"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"démo → {self.user}"
