import hashlib
import os
import re
import traceback
import uuid
from django.http import HttpResponseServerError
from django.core.exceptions import PermissionDenied
from django.http import Http404
from .models import RuntimeError


def sanitize(text):
    return re.sub(r"(?i)(bearer|password|cookie|api[_-]?key|secret)[=: ]+[^\s,;]+",
                  r"\1=[REDACTED]", str(text)[:6000])


class ErrorCaptureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.correlation_id = uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Correlation-ID"] = request.correlation_id
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, (PermissionDenied, Http404)):
            return None
        stack = sanitize("".join(traceback.format_exception(type(exception), exception, exception.__traceback__))[-6000:])
        path = request.path[:250]
        correlation = request.correlation_id
        RuntimeError.objects.create(
            fingerprint=hashlib.sha256((path + type(exception).__name__ + str(exception)).encode()).hexdigest(),
            correlation_id=correlation, source="server", route=path,
            case_reference="", deployed_commit=os.getenv("FINCORP_COMMIT", "local-unversioned"),
            environment=os.getenv("FINCORP_ENVIRONMENT", "runtime"), message=sanitize(exception)[:400],
            stack=stack, log_excerpt=f"{correlation} server exception {type(exception).__name__} on {path}",
        )
        return HttpResponseServerError("An error occurred. Reference: " + correlation)
