"""Copy-failure diagnostics only; never construct or launch the verifier runtime."""

import os

import pytest

from tests.integration import test_accepted_input_verifier_process as copying

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_runtime_or_copy(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("diagnostics must not copy or launch a runtime")

    monkeypatch.setattr(copying, "_copy_regular", forbidden)
    monkeypatch.setattr(copying.transport, "run_bounded_process", forbidden)
    assert copying._DIAGNOSTIC_RUNTIME is None


@pytest.mark.parametrize(
    ("limits", "flags"),
    [
        ({"max_files": 0}, (True, False, False)),
        ({"max_file_bytes": 3}, (False, True, False)),
        ({"max_total_bytes": 3}, (False, False, True)),
        ({"max_files": 0, "max_file_bytes": 3, "max_total_bytes": 3}, (True, True, True)),
    ],
)
def test_copy_diagnostic_identifies_each_cap_without_allocating(tmp_path, limits, flags):
    source = tmp_path / "stdlib"
    child = source / "config"
    child.mkdir(parents=True)
    (child / "candidate.a").write_bytes(b"four")
    destination = tmp_path / "destination"
    budget = copying._CopyBudget(**limits)
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_tree(source, destination, budget, stdlib_root=True)
    detail = str(caught.value)
    assert "phase=stdlib relative='config/candidate.a' relative_truncated=false" in detail
    assert "file_bytes=4 files=1 cumulative_bytes=4" in detail
    for key, value in zip(
        ("exceeded_files", "exceeded_file_bytes", "exceeded_total_bytes"), flags, strict=True
    ):
        assert f"{key}={str(value).lower()}" in detail
    assert str(tmp_path) not in detail and "four" not in detail
    assert (budget.files, budget.total_bytes) == (1, 4)
    assert not destination.exists()


def test_copy_diagnostic_keeps_shared_cumulative_accounting(tmp_path):
    source = tmp_path / "file"
    source.write_bytes(b"four")
    budget = copying._CopyBudget(max_total_bytes=7, files=2, total_bytes=4)
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_file(source, tmp_path / "destination", budget)
    assert "file_bytes=4 files=3 cumulative_bytes=8" in str(caught.value)
    assert (budget.files, budget.total_bytes) == (3, 8)
    assert not (tmp_path / "destination").exists()


@pytest.mark.parametrize("phase", ["file", "tree", "executable", "dependency", "application"])
def test_copy_diagnostic_reports_only_fixed_logical_phase(tmp_path, phase):
    source = tmp_path / "file"
    source.write_bytes(b"four")
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_file(
            source,
            tmp_path / "destination",
            copying._CopyBudget(max_files=0),
            executable=phase == "executable",
            copy_phase=phase,
        )
    assert f"phase={phase} relative='file' " in str(caught.value)
    assert not (tmp_path / "destination").exists()


@pytest.mark.parametrize(
    "relative",
    [
        "file\nnext\r\t\x00\x1b[31m",
        "' quoted \\ path",
        "\u202e\u0085\udcff",
        "\U0001f600" * 256,
        "\U0001f600" * 257,
        "x" * 100_000,
    ],
    ids=["controls", "quotes", "unicode-surrogate", "max-preview", "truncated", "long"],
)
def test_copy_diagnostic_escapes_only_bounded_relative_preview(relative):
    observed = os.stat_result((0, 0, 0, 0, 0, 0, 4, 0, 0, 0))
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._CopyBudget(max_files=0).reserve(observed, phase="stdlib", relative=relative)
    detail = str(caught.value)
    assert detail.isascii() and len(detail) < 3000
    assert all(32 <= ord(char) <= 126 for char in detail)
    assert f"relative={relative[:256]!a} " in detail
    assert f"relative_truncated={str(len(relative) > 256).lower()} " in detail


@pytest.mark.parametrize("name", ["line\n\x1b[31mfile", "\u202e\u00e9-file"])
def test_copy_diagnostic_escapes_actual_unusual_filename(tmp_path, name):
    source = tmp_path / name
    source.write_bytes(b"private contents")
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_file(
            source, tmp_path / "destination", copying._CopyBudget(max_files=0)
        )
    detail = str(caught.value)
    assert f"relative={name!a} " in detail
    assert all(32 <= ord(char) <= 126 for char in detail)
    assert str(tmp_path) not in detail and "private contents" not in detail
    assert not (tmp_path / "destination").exists()


def test_copy_diagnostic_does_not_format_unknown_context_or_huge_counters():
    class Poison:
        def __str__(self):
            raise AssertionError("do not format arbitrary diagnostic context")

        __repr__ = __str__

    detail = copying._copy_limit_details(
        Poison(), Poison(), 2**20_000, -1, 2**20_000, (True, False, True)
    )
    assert "phase=unknown relative='<unavailable>'" in detail
    assert "file_bytes=unavailable files=unavailable cumulative_bytes=unavailable" in detail
    assert detail.isascii() and len(detail) < 3000


def test_copy_diagnostic_preserves_exact_admission_and_default_caps(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("accepted reservation must not format diagnostics")

    monkeypatch.setattr(copying, "_copy_limit_details", forbidden)
    budget = copying._CopyBudget(max_files=1, max_file_bytes=4, max_total_bytes=4)
    budget.reserve(os.stat_result((0, 0, 0, 0, 0, 0, 4, 0, 0, 0)))
    assert (budget.files, budget.total_bytes) == (1, 4)
    defaults = copying._CopyBudget()
    assert (
        defaults.max_files,
        defaults.max_entries,
        defaults.max_depth,
        defaults.max_path_bytes,
        defaults.max_file_bytes,
        defaults.max_total_bytes,
        defaults.wall_seconds,
    ) == (10_000, 20_000, 64, 4096, 32 * 1024 * 1024, 128 * 1024 * 1024, 30.0)
