"""Keep signed-in API answers out of shared and browser caches (judge 3 round 5, L2)."""


class PrivateApiCacheMiddleware:
    """Add ``Cache-Control: private, no-store`` to authenticated ``/api/`` responses that set none.

    Responses that choose their own policy (share-link downloads' ``no-store``, page previews'
    ``private, max-age``) keep it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if request.path.startswith("/api/") and user is not None and user.is_authenticated and not response.has_header("Cache-Control"):
            response["Cache-Control"] = "private, no-store"
        return response
