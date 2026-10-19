"""HTTPS must not depend on which root certificates Windows has fetched.

A clean Windows Sandbox failed the "Find similar" model download with
CERTIFICATE_VERIFY_FAILED: Windows fetches roots on demand, and Python never
asks. The update check and Pull from Server use the same urllib defaults.
"""

import ssl

import certifi

from src.utils import ssl_certs


def test_certifi_roots_are_added(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    before = ssl.create_default_context().cert_store_stats()["x509_ca"]
    assert ssl_certs.use_bundled_ca_certs() == certifi.where()
    after = ssl.create_default_context().cert_store_stats()["x509_ca"]
    assert after > before, "certifi's bundle did not reach the default context"


def test_system_store_is_kept_not_replaced(monkeypatch):
    # Company/antivirus roots live in the OS store; they must keep working.
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    system_only = ssl.create_default_context().cert_store_stats()["x509_ca"]
    ssl_certs.use_bundled_ca_certs()
    with open(certifi.where(), encoding="ascii") as f:
        certifi_count = f.read().count("BEGIN CERTIFICATE")
    combined = ssl.create_default_context().cert_store_stats()["x509_ca"]
    assert combined >= max(system_only, certifi_count)


def test_a_users_own_setting_wins(monkeypatch):
    monkeypatch.setenv("SSL_CERT_FILE", r"C:\corp\roots.pem")
    assert ssl_certs.use_bundled_ca_certs() is None
    assert ssl_certs.os.environ["SSL_CERT_FILE"] == r"C:\corp\roots.pem"
