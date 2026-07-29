from pathlib import Path

from utils.downloads import (
    attribution_credit_line,
    dedupe_folder,
    delete_media_file,
    read_attribution,
    sha256_file,
    write_attribution,
)


def test_sha256_file_is_stable_and_content_sensitive(tmp_path: Path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"same content")
    b.write_bytes(b"same content")
    c = tmp_path / "c.bin"
    c.write_bytes(b"different content")

    assert sha256_file(a) == sha256_file(b)
    assert sha256_file(a) != sha256_file(c)


def test_write_and_read_attribution_roundtrip(tmp_path: Path):
    media = tmp_path / "track.mp3"
    media.write_bytes(b"fake audio")

    write_attribution(
        media,
        source="incompetech",
        license="CC BY 3.0",
        attribution_required=True,
        credit="Music by Kevin MacLeod",
        query="",
        url="https://incompetech.com/x.mp3",
    )

    data = read_attribution(media)
    assert data["source"] == "incompetech"
    assert data["attribution_required"] is True
    assert attribution_credit_line(media) == "Music by Kevin MacLeod"


def test_attribution_credit_line_none_when_not_required(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake video")

    write_attribution(media, source="pexels", license="Pexels License", attribution_required=False)

    assert read_attribution(media) is not None
    assert attribution_credit_line(media) is None


def test_attribution_credit_line_none_when_no_sidecar(tmp_path: Path):
    media = tmp_path / "untracked.mp4"
    media.write_bytes(b"fake video")
    assert attribution_credit_line(media) is None


def test_delete_media_file_removes_sidecar_too(tmp_path: Path):
    media = tmp_path / "track.mp3"
    media.write_bytes(b"fake audio")
    write_attribution(media, source="incompetech", license="CC BY 3.0", attribution_required=True)

    sidecar = tmp_path / "track.mp3.attribution.json"
    assert media.exists() and sidecar.exists()

    delete_media_file(media)

    assert not media.exists()
    assert not sidecar.exists()


def test_dedupe_folder_removes_byte_identical_duplicates_keeps_oldest(tmp_path: Path):
    original = tmp_path / "original.mp4"
    original.write_bytes(b"identical payload")

    duplicate = tmp_path / "duplicate.mp4"
    duplicate.write_bytes(b"identical payload")

    unique = tmp_path / "unique.mp4"
    unique.write_bytes(b"different payload")

    removed = dedupe_folder(tmp_path, {".mp4"})

    assert removed == 1
    remaining = {p.name for p in tmp_path.glob("*.mp4")}
    assert remaining == {"original.mp4", "unique.mp4"}


def test_dedupe_folder_no_duplicates_removes_nothing(tmp_path: Path):
    (tmp_path / "a.mp4").write_bytes(b"one")
    (tmp_path / "b.mp4").write_bytes(b"two")

    removed = dedupe_folder(tmp_path, {".mp4"})

    assert removed == 0
    assert len(list(tmp_path.glob("*.mp4"))) == 2
