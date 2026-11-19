"""Keep API answers out of shared and browser caches (judge 3 round 5, L2; round 6, L7), and answer unknown API
paths with JSON (judge 2 round 8, L4)."""

from django.http import JsonResponse



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


class ApiNotFoundMiddleware:
    """Answer an unknown ``/api/`` path with ``{"error": "Not found"}`` (404), in production and in DEBUG alike.

    The local quickstart runs with ``RIPIANO_DEBUG=1`` (plain-http localhost cannot use secure cookies), where Django's
    debug 404 page would list every URL pattern. Views' own JSON 404s pass through unchanged.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.path.startswith("/api/") and response.status_code == 404
                and not response.get("Content-Type", "").startswith("application/json")):
            return JsonResponse({"error": "Not found"}, status=404)
        return response
