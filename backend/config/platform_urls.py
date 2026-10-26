from django.contrib import admin
from django.urls import path

from config.platform_api import platform_api

admin.site.site_header = "Muhimu — administration"
admin.site.site_title = "Muhimu"
admin.site.index_title = "Console interne"

urlpatterns = [
    path("django/", admin.site.urls),
    path("api/", platform_api.urls),
]
