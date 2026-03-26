from django.contrib.auth import logout

SESSION_COOKIE_NAME = '__session_dashboard'


class CrossDomainSessionMiddleware:
    """Log out the user if the cross-domain session cookie disappears.

    When a user signs out on another *.repebble.com site, the
    __session_dashboard cookie is cleared. This middleware detects
    the missing cookie and invalidates the Django session to match.

    Uses a session flag (_had_sso_cookie) to avoid logging out users
    who signed in directly on CloudPebble without SSO (e.g., non-developers).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            had_cookie = request.session.get('_had_sso_cookie', False)
            has_cookie = SESSION_COOKIE_NAME in request.COOKIES
            if had_cookie and not has_cookie:
                logout(request)
            elif has_cookie and not had_cookie:
                request.session['_had_sso_cookie'] = True
        return self.get_response(request)
