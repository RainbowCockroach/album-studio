"""Trust certifi's root certificates as well as the operating system's.

A fresh Windows does not ship every root certificate: it fetches them on
demand, but only when its own networking code asks. Python's SSL reads the
Windows store without triggering that fetch, so on a clean PC every HTTPS call
the app makes (the "Find similar" model download, the update check, Pull from
Server) failed with CERTIFICATE_VERIFY_FAILED.

Setting SSL_CERT_FILE *adds* certifi's bundle: on Windows,
SSLContext.load_default_certs() loads the system store and then
set_default_verify_paths(), which reads this variable. Company or antivirus
root certificates installed in Windows therefore keep working.
"""

import os
from typing import Optional


def use_bundled_ca_certs() -> Optional[str]:
    """Point SSL_CERT_FILE at certifi's bundle. Returns the path, or None.

    A value the user already set is left alone.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return None
    try:
        import certifi
    except ImportError:
        return None
    path = certifi.where()
    if not os.path.exists(path):
        return None
    os.environ["SSL_CERT_FILE"] = path
    return path
