from pathlib import Path

import pytest
from cryptography import x509

from streamlit_remote.https import (
    HttpsError,
    prepare_https_material,
    prepare_self_signed_material,
    subject_alt_names_for_host,
    validate_cert_files,
)


def test_validate_cert_files_requires_both_files(tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_text("cert", encoding="utf-8")

    with pytest.raises(HttpsError, match="requires both"):
        validate_cert_files(cert_file, None)


def test_validate_cert_files_returns_existing_paths(tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("cert", encoding="utf-8")
    key_file.write_text("key", encoding="utf-8")

    material = validate_cert_files(cert_file, key_file)

    assert material.cert_file == cert_file
    assert material.key_file == key_file


def test_prepare_https_material_off_returns_none() -> None:
    assert prepare_https_material("off", "127.0.0.1") is None


def test_prepare_self_signed_material_generates_and_reuses_cert(tmp_path: Path) -> None:
    first = prepare_self_signed_material(
        "127.0.0.1",
        valid_days=30,
        cache_dir=tmp_path,
    )
    second = prepare_self_signed_material(
        "127.0.0.1",
        valid_days=30,
        cache_dir=tmp_path,
    )

    assert first == second
    assert first.cert_file.is_file()
    assert first.key_file.is_file()


def test_prepare_self_signed_material_includes_expected_sans(tmp_path: Path) -> None:
    material = prepare_self_signed_material(
        "example.test",
        valid_days=30,
        cache_dir=tmp_path,
    )

    cert = x509.load_pem_x509_certificate(material.cert_file.read_bytes())
    sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value

    assert sorted(str(san) for san in sans) == sorted(
        str(san) for san in subject_alt_names_for_host("example.test")
    )


def test_prepare_self_signed_material_rejects_invalid_validity(
    tmp_path: Path,
) -> None:
    with pytest.raises(HttpsError, match="at least 1"):
        prepare_self_signed_material("127.0.0.1", valid_days=0, cache_dir=tmp_path)
