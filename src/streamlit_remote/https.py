from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@dataclass(frozen=True)
class HttpsMaterial:
    cert_file: Path
    key_file: Path


class HttpsError(Exception):
    pass


def prepare_https_material(
    mode: str,
    host: str,
    cert_file: Path | None = None,
    key_file: Path | None = None,
    valid_days: int = 30,
    cache_dir: Path | None = None,
) -> HttpsMaterial | None:
    if mode == "off":
        return None

    if mode == "cert-files":
        return validate_cert_files(cert_file, key_file)

    if mode == "self-signed":
        return prepare_self_signed_material(host, valid_days, cache_dir)

    raise HttpsError(f"Unsupported HTTPS mode: {mode}")


def validate_cert_files(
    cert_file: Path | None,
    key_file: Path | None,
) -> HttpsMaterial:
    if cert_file is None or key_file is None:
        raise HttpsError(
            "`--https cert-files` requires both `--ssl-cert-file` and `--ssl-key-file`."
        )

    if not cert_file.is_file():
        raise HttpsError(f"SSL certificate file not found: {cert_file}")

    if not key_file.is_file():
        raise HttpsError(f"SSL key file not found: {key_file}")

    return HttpsMaterial(cert_file=cert_file, key_file=key_file)


def prepare_self_signed_material(
    host: str,
    valid_days: int = 30,
    cache_dir: Path | None = None,
) -> HttpsMaterial:
    if valid_days < 1:
        raise HttpsError("`--cert-valid-days` must be at least 1.")

    sans = subject_alt_names_for_host(host)
    cert_file, key_file, metadata_file = self_signed_paths(host, cache_dir)
    cert_dir = cert_file.parent
    cert_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    if is_reusable_certificate(cert_file, key_file, sans):
        return HttpsMaterial(cert_file=cert_file, key_file=key_file)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(certificate_name())
        .issuer_name(certificate_name())
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(key_file, 0o600)

    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    metadata_file.write_text(
        json.dumps(
            {
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=valid_days)).isoformat(),
                "sans": [str(san) for san in sans],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return HttpsMaterial(cert_file=cert_file, key_file=key_file)


def planned_self_signed_material(
    host: str,
    cache_dir: Path | None = None,
) -> HttpsMaterial:
    cert_file, key_file, _ = self_signed_paths(host, cache_dir)
    return HttpsMaterial(cert_file=cert_file, key_file=key_file)


def self_signed_paths(
    host: str,
    cache_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    sans = subject_alt_names_for_host(host)
    cert_dir = cache_dir if cache_dir is not None else default_cert_cache_dir()
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "schema": 1,
                "sans": [str(san) for san in sans],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]

    return (
        cert_dir / f"self-signed-{fingerprint}.crt",
        cert_dir / f"self-signed-{fingerprint}.key",
        cert_dir / f"self-signed-{fingerprint}.json",
    )


def default_cert_cache_dir() -> Path:
    return Path.home() / ".streamlit-remote" / "certs"


def subject_alt_names_for_host(host: str) -> list[x509.GeneralName]:
    names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]

    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        if host and host != "localhost":
            names.append(x509.DNSName(host))
    else:
        if host_ip not in {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}:
            names.append(x509.IPAddress(host_ip))

    return names


def is_reusable_certificate(
    cert_file: Path,
    key_file: Path,
    expected_sans: list[x509.GeneralName],
) -> bool:
    if not cert_file.is_file() or not key_file.is_file():
        return False

    try:
        cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
        sans = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
    except (OSError, ValueError, x509.ExtensionNotFound):
        return False

    if sorted(str(san) for san in sans) != sorted(str(san) for san in expected_sans):
        return False

    expires_at = certificate_not_valid_after(cert)
    return expires_at > datetime.now(timezone.utc) + timedelta(days=1)


def certificate_not_valid_after(cert: x509.Certificate) -> datetime:
    expires_at = getattr(cert, "not_valid_after_utc", None)
    if expires_at is not None:
        return expires_at
    return cert.not_valid_after.replace(tzinfo=timezone.utc)


def certificate_name() -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "streamlit-remote local development"),
        ]
    )
