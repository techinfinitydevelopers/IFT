"""Campaign attribution — capture ?utm_source/utm_medium/utm_campaign from the
registration page's URL and carry them through to account creation.

UTM params only ever appear on the initial GET (the ad link lands here); the
form POST that actually creates the account doesn't carry them. So: stash in
the session on GET, read (and clear) it on POST.
"""

_SESSION_KEY = 'utm_attribution'
_FIELDS = ('utm_source', 'utm_medium', 'utm_campaign')


def capture(request):
    """Call on a sign-up page's GET. Stores utm_* params in the session if
    any are present on this request (last-touch — a later visit with new UTM
    params overwrites an earlier one)."""
    data = {f: request.GET.get(f, '').strip() for f in _FIELDS}
    if any(data.values()):
        request.session[_SESSION_KEY] = data
        request.session.modified = True


def pop(request):
    """Call when creating the account (form POST). Returns the stashed
    utm_* dict (empty strings if none was ever captured) and clears it."""
    data = request.session.pop(_SESSION_KEY, None) or {}
    request.session.modified = True
    return {f: data.get(f, '') for f in _FIELDS}
