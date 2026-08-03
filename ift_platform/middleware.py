"""Site-wide middleware helpers."""

import re

from django.http import HttpResponseForbidden

# Write methods a read-only viewer must never perform.
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ReadOnlyViewerMiddleware:
    """Enforce read-only access for users with the 'viewer' role.

    A viewer can open any page (GET), but any state-changing request
    (POST/PUT/PATCH/DELETE) is rejected with 403 — look-but-don't-touch.
    Authentication POSTs (login/logout) are unaffected because the user is
    still anonymous at that point.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in _UNSAFE_METHODS:
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                profile = getattr(user, "profile", None)
                if profile is not None and profile.role == "viewer":
                    return HttpResponseForbidden(
                        "This is a read-only (viewer) account. Changes are not allowed."
                    )
        return self.get_response(request)

GA_MEASUREMENT_ID = "G-VK29QNQ94H"
GTM_CONTAINER_ID = "GTM-PF4TLHG6"

_GA_SNIPPET = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{id}');
</script>
""".format(id=GA_MEASUREMENT_ID)


class GoogleAnalyticsMiddleware:
    """Injects the GA4 gtag snippet right after <head> on every HTML page.

    Site templates don't share a single base, so this guarantees coverage
    across landing, dashboards, admin and error pages in one place. Non-HTML,
    streaming, and already-tagged responses are left untouched.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if getattr(response, "streaming", False):
                return response
            if "text/html" not in response.get("Content-Type", ""):
                return response
            if not hasattr(response, "content"):
                return response

            charset = response.charset or "utf-8"
            content = response.content.decode(charset, errors="ignore")
            if GA_MEASUREMENT_ID in content:
                return response

            idx = content.lower().find("<head>")
            if idx == -1:
                return response

            insert_at = idx + len("<head>")
            content = content[:insert_at] + "\n" + _GA_SNIPPET + content[insert_at:]
            response.content = content.encode(charset)
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        except Exception:
            # Analytics must never break a page render.
            pass
        return response


_GTM_HEAD_SNIPPET = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{id}');</script>
<!-- End Google Tag Manager -->
""".format(id=GTM_CONTAINER_ID)

_GTM_BODY_SNIPPET = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={id}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
""".format(id=GTM_CONTAINER_ID)

_BODY_TAG_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)


class GoogleTagManagerMiddleware:
    """Injects the GTM head script right after <head>, and the GTM noscript
    iframe right after the opening <body> tag, on every HTML page.

    Mirrors GoogleAnalyticsMiddleware — same single-place-covers-everything
    rationale, since site templates don't share one base template.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if getattr(response, "streaming", False):
                return response
            if "text/html" not in response.get("Content-Type", ""):
                return response
            if not hasattr(response, "content"):
                return response

            charset = response.charset or "utf-8"
            content = response.content.decode(charset, errors="ignore")
            if GTM_CONTAINER_ID in content:
                return response

            head_idx = content.lower().find("<head>")
            if head_idx != -1:
                insert_at = head_idx + len("<head>")
                content = content[:insert_at] + "\n" + _GTM_HEAD_SNIPPET + content[insert_at:]

            body_match = _BODY_TAG_RE.search(content)
            if body_match:
                insert_at = body_match.end()
                content = content[:insert_at] + "\n" + _GTM_BODY_SNIPPET + content[insert_at:]

            response.content = content.encode(charset)
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        except Exception:
            # Analytics must never break a page render.
            pass
        return response
