"""
Root URL configuration.

Routes:
  /admin/      Django admin
  /accounts/   auth (login, logout, register, profile) + allauth (Google OAuth)
  /api/        DRF endpoints (finance app)
  /            HTML dashboard / transactions / budgets / reports (finance app)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),  # Google OAuth flow
    path("api/", include("finance.api_urls")),
    path("", include("finance.urls")),
]

# Serve user-uploaded media in development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
