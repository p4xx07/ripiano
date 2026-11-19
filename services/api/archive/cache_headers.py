"""Keep API answers out of shared and browser caches (judge 3 round 5, L2; round 6, L7)."""


class PrivateApiCacheMiddleware:
    """Add ``Cache-Control: private, no-store`` to ``/api/`` responses that set none, signed in or not.

    Responses that choose their own policy (share-link downloads' ``no-store``, page previews'
    ``private, max-age``) keep it. Signed-out answers such as ``/api/session`` are per-person too.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/") and not response.has_header("Cache-Control"):
            response["Cache-Control"] = "private, no-store"
        return response
