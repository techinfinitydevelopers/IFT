"""Site-wide middleware helpers."""

import re

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

# Write methods a read-only account must never perform.
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# TCE (limited read-only) may only open these admin areas. Everything else under
# /super-admin/ is blocked and redirected to the dashboard.
_TCE_ALLOWED_PREFIXES = (
    "/super-admin/user-management/students",
    "/super-admin/user-management/schools",
    "/super-admin/submissions",
    "/super-admin/submission/",
    "/super-admin/reports",
)

_BODY_CLOSE_RE = re.compile(r"</body>", re.IGNORECASE)

# Injected on TCE admin pages: hide any sidebar nav link that isn't allowed
# (Dashboard + Schools/Students lists + Submissions + Reports/Zonal).
_TCE_NAV_HIDE = """<script>
(function(){
  var ok = ['/super-admin/user-management/students','/super-admin/user-management/schools',
            '/super-admin/submissions','/super-admin/submission/','/super-admin/reports'];
  document.querySelectorAll('a.nav-item, a.nav-dropdown-item').forEach(function(a){
    var h = a.getAttribute('href') || '';
    if (h.indexOf('/super-admin/') === -1) return;             // leave non-admin links
    if (h === '/super-admin/' || h === '/super-admin') return; // keep Dashboard
    var allowed = ok.some(function(p){ return h.indexOf(p) === 0; });
    if (!allowed) a.style.display = 'none';
  });
  document.querySelectorAll('.nav-dropdown').forEach(function(d){
    var vis = 0;
    d.querySelectorAll('a.nav-dropdown-item').forEach(function(x){ if (x.style.display !== 'none') vis++; });
    if (vis === 0) d.style.display = 'none';
  });
  // Page-level write-action buttons on the Students/Schools list pages
  // (Onboard, Delete Test Data, Import/Sample CSV). Export CSV stays — it is
  // read-only and part of what TCE is allowed to do.
  ['a[href*="/user-management/onboard-"]',
   'a[href*="/user-management/schools/sample-csv"]',
   '[onclick*="deleteTestData"]',
   '[onclick*="importModal"]'].forEach(function(sel){
    document.querySelectorAll(sel).forEach(function(el){ el.style.display = 'none'; });
  });
})();
</script>"""


class ReadOnlyViewerMiddleware:
    """Read-only enforcement for 'viewer' and 'tce' roles.

    - viewer & tce: any state-changing request (POST/PUT/PATCH/DELETE) is 403'd.
    - tce (limited): may only open a whitelist of admin pages; any other
      /super-admin/ page is redirected to the dashboard, and non-allowed
      sidebar links are hidden via an injected script.
    Auth POSTs (login/logout) are unaffected — the user is still anonymous then.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        method = request.method
        role = None
        # Only pay for the profile lookup when it can matter.
        if method in _UNSAFE_METHODS or path.startswith("/super-admin/"):
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                profile = getattr(user, "profile", None)
                role = getattr(profile, "role", None) if profile is not None else None

        if role in ("viewer", "tce") and method in _UNSAFE_METHODS:
            return HttpResponseForbidden(
                "This is a read-only account. Changes are not allowed."
            )

        if role == "tce" and path.startswith("/super-admin/") and path != "/super-admin/":
            if not any(path.startswith(p) for p in _TCE_ALLOWED_PREFIXES):
                return redirect("/super-admin/")

        request._is_tce = (role == "tce")
        response = self.get_response(request)

        if getattr(request, "_is_tce", False):
            try:
                if (not getattr(response, "streaming", False)
                        and "text/html" in response.get("Content-Type", "")
                        and hasattr(response, "content")):
                    charset = response.charset or "utf-8"
                    content = response.content.decode(charset, errors="ignore")
                    m = _BODY_CLOSE_RE.search(content)
                    if m:
                        content = content[:m.start()] + _TCE_NAV_HIDE + content[m.start():]
                        response.content = content.encode(charset)
                        if response.has_header("Content-Length"):
                            response["Content-Length"] = str(len(response.content))
            except Exception:
                pass
        return response

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
