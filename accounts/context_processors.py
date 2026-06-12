from django.conf import settings


def google_login(request):
    return {"google_login_enabled": bool(settings.GOOGLE_CLIENT_ID)}
