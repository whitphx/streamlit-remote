from pathlib import Path

import pytest
from cryptography import x509

from streamlit_remote.https import (
    HttpsError,
    mkcert_hosts_for_host,
    mkcert_paths,
    prepare_https_material,
    prepare_mkcert_material,
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


def test_mkcert_hosts_include_local_defaults_and_host() -> None:
    assert mkcert_hosts_for_host("localhost") == ["localhost", "127.0.0.1", "::1"]
    assert mkcert_hosts_for_host("example.test") == [
        "localhost",
        "127.0.0.1",
        "::1",
        "example.test",
    ]


def test_prepare_mkcert_material_generates_cert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr("streamlit_remote.https.shutil.which", lambda name: "/usr/bin/mkcert")

    def fake_run_mkcert(command: list[str]) -> None:
        commands.append(command)
        if "-cert-file" in command:
            cert_file = Path(command[command.index("-cert-file") + 1])
            key_file = Path(command[command.index("-key-file") + 1])
            cert_file.write_text("cert", encoding="utf-8")
            key_file.write_text("key", encoding="utf-8")

    monkeypatch.setattr("streamlit_remote.https.run_mkcert", fake_run_mkcert)

    material = prepare_mkcert_material("example.test", cache_dir=tmp_path)

    assert material.cert_file.is_file()
    assert material.key_file.is_file()
    assert commands[0] == ["mkcert", "-install"]
    assert commands[1][:5] == [
        "mkcert",
        "-cert-file",
        str(material.cert_file),
        "-key-file",
        str(material.key_file),
    ]
    assert commands[1][5:] == ["localhost", "127.0.0.1", "::1", "example.test"]


def test_prepare_mkcert_material_uses_custom_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []
    mkcert_binary = tmp_path / "mkcert-custom"

    monkeypatch.setattr(
        "streamlit_remote.https.shutil.which",
        lambda name: str(mkcert_binary) if name == str(mkcert_binary) else None,
    )

    def fake_run_mkcert(command: list[str]) -> None:
        commands.append(command)
        if "-cert-file" in command:
            cert_file = Path(command[command.index("-cert-file") + 1])
            key_file = Path(command[command.index("-key-file") + 1])
            cert_file.write_text("cert", encoding="utf-8")
            key_file.write_text("key", encoding="utf-8")

    monkeypatch.setattr("streamlit_remote.https.run_mkcert", fake_run_mkcert)

    prepare_mkcert_material("localhost", cache_dir=tmp_path, mkcert_binary=mkcert_binary)

    assert commands[0] == [str(mkcert_binary), "-install"]
    assert commands[1][0] == str(mkcert_binary)


def test_prepare_mkcert_material_reuses_existing_cert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("streamlit_remote.https.shutil.which", lambda name: "/usr/bin/mkcert")
    monkeypatch.setattr(
        "streamlit_remote.https.run_mkcert",
        lambda command: pytest.fail("unexpected mkcert call"),
    )

    cert_file, key_file, _ = mkcert_paths("localhost", cache_dir=tmp_path)
    cert_file.parent.mkdir(parents=True, exist_ok=True)
    cert_file.write_text("cert", encoding="utf-8")
    key_file.write_text("key", encoding="utf-8")
    second = prepare_mkcert_material("localhost", cache_dir=tmp_path)

    assert second.cert_file == cert_file
    assert second.key_file == key_file


def test_prepare_mkcert_material_reports_missing_mkcert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("streamlit_remote.https.shutil.which", lambda name: None)

    with pytest.raises(HttpsError, match="mkcert was not found"):
        prepare_mkcert_material("localhost", cache_dir=tmp_path)


def test_prepare_mkcert_material_reports_missing_custom_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("streamlit_remote.https.shutil.which", lambda name: None)

    with pytest.raises(HttpsError, match="configured path"):
        prepare_mkcert_material(
            "localhost",
            cache_dir=tmp_path,
            mkcert_binary=tmp_path / "missing-mkcert",
        )
