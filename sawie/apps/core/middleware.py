"""Small request-scoped middleware."""
from datetime import timedelta

from django.utils import timezone


class LastSeenMiddleware:
    """Record user activity at most once every five minutes."""

    THROTTLE = timedelta(minutes=5)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            if user.last_seen is None or now - user.last_seen > self.THROTTLE:
                user.touch()
        return self.get_response(request)
