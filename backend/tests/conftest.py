# Shared: CSRF guard requires X-Requested-With on every unsafe /api call -> add it to every requests Session by default.
import requests

_orig_init = requests.Session.__init__


def _init_with_xrw(self, *a, **kw):
    _orig_init(self, *a, **kw)
    self.headers["X-Requested-With"] = "XMLHttpRequest"


requests.Session.__init__ = _init_with_xrw
