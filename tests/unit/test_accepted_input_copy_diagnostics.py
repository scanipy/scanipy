"""Bounded inert fixture copies/diagnostics; never build or launch a verifier runtime."""

import os

import pytest

from tests.integration import test_accepted_input_verifier_process as copying

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_runtime_or_copy(monkeypatch):
    original_copy = copying._copy_regular

    def forbidden(*args, **kwargs):
        raise AssertionError("diagnostics must not copy or launch a runtime")

    monkeypatch.setattr(copying, "_copy_regular", forbidden)
    monkeypatch.setattr(copying.transport, "run_bounded_process", forbidden)
    assert copying._DIAGNOSTIC_RUNTIME is None
    return original_copy


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


@pytest.fixture
def static_archive_tree(tmp_path, monkeypatch, no_runtime_or_copy):
    source = tmp_path / "stdlib"
    config = source / "config-3.11-x86_64-linux-gnu"
    config.mkdir(parents=True)
    archive = config / "libpython3.11.a"
    archive.write_bytes(b"four")
    metadata = {"LIBPL": str(config), "LIBRARY": archive.name}
    queried = []

    def config_var(name):
        queried.append(name)
        return metadata[name]

    monkeypatch.setattr(copying.sysconfig, "get_config_var", config_var)
    # This fixture alone permits copying small inert bytes. Child launch remains poisoned.
    monkeypatch.setattr(copying, "_copy_regular", no_runtime_or_copy)
    return source, archive, metadata, queried


def test_static_archive_exact_regular_omission_preserves_neighbors_and_accounting(
    tmp_path, static_archive_tree, monkeypatch
):
    source, archive, _, queried = static_archive_tree
    neighbors = {"Makefile": b"mk", "neighbor.a": b"ar", "core.py": b"py"}
    for name, raw in neighbors.items():
        (archive.parent / name).write_bytes(raw)
    destination = tmp_path / "copy"
    budget = copying._CopyBudget(max_file_bytes=2, max_total_bytes=6, max_files=3)
    observed = []
    original_observe = budget.observe

    def observe(path, depth):
        observed.append((path, depth))
        return original_observe(path, depth)

    monkeypatch.setattr(budget, "observe", observe)
    copying._private_copy_tree(source, destination, budget, stdlib_root=True)
    assert queried == ["LIBPL", "LIBRARY"]
    assert (archive, 2) in observed
    assert budget.entries == len(observed) == len(source.parents) + 6
    assert (budget.files, budget.total_bytes) == (3, 6)
    copied_config = destination / archive.parent.name
    assert sorted(path.name for path in copied_config.iterdir()) == sorted(neighbors)
    for name, raw in neighbors.items():
        assert (copied_config / name).read_bytes() == raw
    assert not (copied_config / archive.name).exists()


def test_static_archive_observed_ci_size_is_not_read_or_copied(
    tmp_path, static_archive_tree, monkeypatch
):
    source, archive, _, _ = static_archive_tree
    # Sparse inert fixture: repeat the observed CI length without allocating or
    # reading that payload. This does not reproduce the hosted Python distribution.
    os.truncate(archive, 48_157_564)

    def forbidden(*args, **kwargs):
        raise AssertionError("the exact static archive must not be opened/copied")

    monkeypatch.setattr(copying, "_copy_regular", forbidden)
    budget = copying._CopyBudget(max_files=0, max_total_bytes=0)
    copying._private_copy_tree(source, tmp_path / "copy", budget, stdlib_root=True)
    assert (budget.files, budget.total_bytes) == (0, 0)
    assert list((tmp_path / "copy" / archive.parent.name).iterdir()) == []


def test_static_archive_candidate_selection_is_lexical_only(static_archive_tree, monkeypatch):
    source, archive, _, _ = static_archive_tree

    def forbidden(*args, **kwargs):
        raise AssertionError("candidate selection must not resolve/read/stat metadata paths")

    with monkeypatch.context() as patch:
        patch.setattr(copying.Path, "resolve", forbidden)
        patch.setattr(copying.Path, "stat", forbidden)
        patch.setattr(copying.Path, "read_bytes", forbidden)
        patch.setattr(copying.os, "open", forbidden)
        candidate = copying._stdlib_static_archive(source, copying._CopyBudget())
    assert candidate == archive.relative_to(source)


@pytest.mark.parametrize("kind", ["same-basename", "unrelated-large-file"])
def test_static_archive_omission_does_not_exempt_other_large_files(
    tmp_path, static_archive_tree, kind
):
    source, archive, _, _ = static_archive_tree
    other = source / archive.name if kind == "same-basename" else archive.parent / "unrelated.a"
    other.write_bytes(b"other")
    destination = tmp_path / "copy"
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_tree(
            source, destination, copying._CopyBudget(max_file_bytes=3), stdlib_root=True
        )
    assert f"relative={str(other.relative_to(source))!a}" in str(caught.value)
    assert "exceeded_file_bytes=true" in str(caught.value)
    assert not destination.exists()


@pytest.mark.parametrize("phase", ["tree", "application", "dependency"])
def test_static_archive_omission_never_applies_to_other_copy_phases(
    tmp_path, static_archive_tree, phase
):
    source, archive, _, queried = static_archive_tree
    destination = tmp_path / "copy"
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_tree(
            source, destination, copying._CopyBudget(max_file_bytes=3), copy_phase=phase
        )
    assert queried == []
    assert f"phase={phase} relative={str(archive.relative_to(source))!a}" in str(caught.value)
    assert not destination.exists()


def test_static_archive_direct_file_copy_has_no_exemption(tmp_path, static_archive_tree):
    _, archive, _, queried = static_archive_tree
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit "):
        copying._private_copy_file(
            archive, tmp_path / "copy", copying._CopyBudget(max_file_bytes=3)
        )
    assert queried == []
    assert not (tmp_path / "copy").exists()


@pytest.mark.parametrize("limits", [{"max_files": 0}, {"max_total_bytes": 1}])
def test_static_archive_omission_preserves_copied_file_and_total_limits(
    tmp_path, static_archive_tree, limits
):
    source, archive, _, _ = static_archive_tree
    (archive.parent / "Makefile").write_bytes(b"mk")
    budget = copying._CopyBudget(max_file_bytes=2, **limits)
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit ") as caught:
        copying._private_copy_tree(source, tmp_path / "copy", budget, stdlib_root=True)
    assert "Makefile'" in str(caught.value)
    assert (budget.files, budget.total_bytes) == (1, 2)
    assert not (tmp_path / "copy").exists()


@pytest.mark.parametrize("kind", ["symlink", "directory", "fifo", "ancestor"])
def test_static_archive_candidate_and_ancestors_must_remain_non_symlink_regular_leaf(
    tmp_path, static_archive_tree, kind
):
    source, archive, metadata, _ = static_archive_tree
    archive.unlink()
    if kind == "symlink":
        target = tmp_path / "outside"
        target.write_bytes(b"outside")
        archive.symlink_to(target)
    elif kind == "directory":
        archive.mkdir()
    elif kind == "fifo":
        os.mkfifo(archive)
    else:
        actual = source / "actual-config"
        archive.parent.rename(actual)
        (actual / archive.name).write_bytes(b"four")
        archive.parent.symlink_to(actual, target_is_directory=True)
        assert metadata["LIBPL"] == str(archive.parent)
    with pytest.raises(ValueError, match="diagnostic-copy-nonregular"):
        copying._private_copy_tree(
            source, tmp_path / "copy", copying._CopyBudget(), stdlib_root=True
        )
    assert not (tmp_path / "copy").exists()


def test_static_archive_missing_leaf_does_not_hide_neighbors(tmp_path, static_archive_tree):
    source, archive, _, _ = static_archive_tree
    archive.unlink()
    (archive.parent / "Makefile").write_bytes(b"mk")
    copying._private_copy_tree(
        source, tmp_path / "copy", copying._CopyBudget(max_total_bytes=2), stdlib_root=True
    )
    assert (tmp_path / "copy" / archive.parent.name / "Makefile").read_bytes() == b"mk"


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("LIBPL", None),
        ("LIBPL", 3),
        ("LIBPL", "relative/config"),
        ("LIBPL", "/outside/config"),
        ("LIBPL", "/stdlib/../config"),
        ("LIBPL", "/" + "x" * 4096),
        ("LIBPL", "/bad\x00config"),
        ("LIBPL", "/bad\udcffconfig"),
        ("LIBRARY", None),
        ("LIBRARY", 3),
        ("LIBRARY", ""),
        ("LIBRARY", ".."),
        ("LIBRARY", "../libpython3.11.a"),
        ("LIBRARY", "/libpython3.11.a"),
        ("LIBRARY", "libpython3.11.so"),
        ("LIBRARY", "x" * 4096 + ".a"),
        ("LIBRARY", "bad\x00.a"),
        ("LIBRARY", "bad\\name.a"),
        ("LIBRARY", "bad\udcff.a"),
    ],
    ids=[
        "directory-none",
        "directory-number",
        "directory-relative",
        "directory-outside",
        "directory-traversal",
        "directory-long",
        "directory-nul",
        "directory-surrogate",
        "library-none",
        "library-number",
        "library-empty",
        "library-parent",
        "library-traversal",
        "library-absolute",
        "library-shared",
        "library-long",
        "library-nul",
        "library-backslash",
        "library-surrogate",
    ],
)
def test_static_archive_invalid_metadata_grants_no_exemption(
    tmp_path, static_archive_tree, field, bad_value
):
    source, _, metadata, _ = static_archive_tree
    metadata[field] = bad_value
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit "):
        copying._private_copy_tree(
            source, tmp_path / "copy", copying._CopyBudget(max_file_bytes=3), stdlib_root=True
        )
    assert not (tmp_path / "copy").exists()


@pytest.mark.parametrize("spelling", ["dot", "parent", "double-slash", "trailing-slash"])
def test_static_archive_non_normalized_metadata_does_not_alias_exact_leaf(
    tmp_path, static_archive_tree, spelling
):
    source, archive, metadata, _ = static_archive_tree
    metadata["LIBPL"] = {
        "dot": str(source) + "/./" + archive.parent.name,
        "parent": str(archive.parent) + "/../" + archive.parent.name,
        "double-slash": str(source) + "//" + archive.parent.name,
        "trailing-slash": str(archive.parent) + "/",
    }[spelling]
    with pytest.raises(ValueError, match=r"^diagnostic-copy-limit "):
        copying._private_copy_tree(
            source, tmp_path / "copy", copying._CopyBudget(max_file_bytes=3), stdlib_root=True
        )
    assert not (tmp_path / "copy").exists()


@pytest.mark.parametrize("limit", ["entries", "depth", "path", "deadline"])
def test_static_archive_still_observed_before_omission(
    tmp_path, static_archive_tree, monkeypatch, limit
):
    source, archive, _, _ = static_archive_tree
    budget = copying._CopyBudget()
    if limit == "entries":
        budget.max_entries = len(source.parents) + 2
    elif limit == "depth":
        budget.max_depth = 1
    elif limit == "path":
        budget.max_path_bytes = len(str(archive)) - 1
    else:
        original_observe = budget.observe

        def observe(path, depth):
            if path == archive:
                budget.started -= budget.wall_seconds
            return original_observe(path, depth)

        monkeypatch.setattr(budget, "observe", observe)
    with pytest.raises(ValueError, match=r"^diagnostic-copy-(limit|deadline)"):
        copying._private_copy_tree(source, tmp_path / "copy", budget, stdlib_root=True)
    assert not (tmp_path / "copy").exists()
