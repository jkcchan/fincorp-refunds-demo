import os
from django.conf import settings
from . import brand


def brand_context(request):
    return {
        "brand": brand,
        "app_role": settings.ROLE,
        "csrf_cookie_name": settings.CSRF_COOKIE_NAME,
        "mode": os.getenv("FINCORP_MODE", "manual"),
        "runtime_url": os.getenv("FINCORP_RUNTIME_URL", "http://127.0.0.1:8001"),
        "control_url": os.getenv("FINCORP_CONTROL_URL", "http://127.0.0.1:8000"),
        "deployed_commit": os.getenv("FINCORP_COMMIT", "local-unversioned"),
    }
