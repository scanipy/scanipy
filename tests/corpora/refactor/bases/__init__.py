"""Seeded-vulnerability base programs for CMP-CORP-REFAC-01.

Each base is a small, self-contained, *closed-world* program that contains
exactly one seeded finding of a Stage-A core class (injection, path-traversal,
ssrf, deserialization) in one Stage-A language (java, python). The base is the
``before/`` tree of every (seed, refactor) pair; the refactor transforms in
``pipeline/refactor_transforms.py`` produce the ``after/`` tree.

A base is a pure function of a ``seed`` integer so the build is deterministic
and reproducible (no wall-clock, no RNG state leakage). The ``seed`` only
varies *names and constant values* — never the taint topology — so that the
seeded finding (source -> sink dataflow) is identical across instantiations of
the same template. This keeps the ground-truth label well-defined: a refactor
that does not change the source->sink slice MUST keep the fingerprint stable.

Synthesis note: every base in this module is SYNTHESIZED (authored for this
corpus, Apache-2.0). They are not lifted from any external repository, so they
carry no third-party provenance. See README.md "SOURCED vs SYNTHESIZED".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Base:
    """A rendered seeded-vulnerability base program.

    Attributes:
        cls:       Stage-A core class of the seeded finding.
        language:  "java" | "python".
        filename:  the single source file name in ``source/``.
        source:    full source text (the ``before/`` tree).
        sink_line: 1-based line of the taint sink (the seeded finding site).
        source_desc: short human description of the source->sink dataflow.
    """

    cls: str
    language: str
    filename: str
    source: str
    sink_line: int
    source_desc: str


# Each template is keyed by (class, language). render(seed) returns a Base.
# The seed perturbs identifiers/constants deterministically; the source->sink
# dataflow (the seeded finding) is invariant across seeds.


def _ident(stem: str, seed: int) -> str:
    """Deterministic, valid identifier suffix from a seed (no RNG)."""
    return f"{stem}{seed:03d}"


# ---------------------------------------------------------------------------
# Java templates
# ---------------------------------------------------------------------------


def _java_injection(seed: int) -> Base:
    p = _ident("p", seed)
    q = _ident("query", seed)
    src = f"""package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {{
    private final Connection conn;

    public OrderService(Connection conn) {{
        this.conn = conn;
    }}

    public void lookup(String {p}) throws Exception {{
        String {q} = "SELECT * FROM orders WHERE id = '" + {p} + "'";
        Statement st = conn.createStatement();
        st.executeQuery({q});
    }}
}}
"""
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "executeQuery" in ln)
    return Base(
        "injection",
        "java",
        "OrderService.java",
        src,
        sink_line,
        f"tainted param `{p}` concatenated into SQL `{q}` and executed",
    )


def _java_path_traversal(seed: int) -> Base:
    p = _ident("name", seed)
    src = f"""package com.scanipy.corpus.refac;

import java.io.File;
import java.io.FileInputStream;

public class FileService {{
    private final String root = "/var/data";

    public byte[] read(String {p}) throws Exception {{
        File target = new File(root + "/" + {p});
        FileInputStream in = new FileInputStream(target);
        return in.readAllBytes();
    }}
}}
"""
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "FileInputStream(" in ln)
    return Base(
        "path-traversal",
        "java",
        "FileService.java",
        src,
        sink_line,
        f"tainted param `{p}` flows into File path opened by FileInputStream",
    )


def _java_ssrf(seed: int) -> Base:
    p = _ident("host", seed)
    src = f"""package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {{
    public int fetch(String {p}) throws Exception {{
        URL url = new URL("http://" + {p} + "/status");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        return c.getResponseCode();
    }}
}}
"""
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "openConnection" in ln)
    return Base(
        "ssrf",
        "java",
        "FetchService.java",
        src,
        sink_line,
        f"tainted param `{p}` flows into URL opened via openConnection",
    )


def _java_deserialization(seed: int) -> Base:
    p = _ident("bytes", seed)
    src = f"""package com.scanipy.corpus.refac;

import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;

public class SessionService {{
    public Object restore(byte[] {p}) throws Exception {{
        ByteArrayInputStream bin = new ByteArrayInputStream({p});
        ObjectInputStream ois = new ObjectInputStream(bin);
        return ois.readObject();
    }}
}}
"""
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "readObject" in ln)
    return Base(
        "deserialization",
        "java",
        "SessionService.java",
        src,
        sink_line,
        f"tainted bytes `{p}` deserialized via ObjectInputStream.readObject",
    )


# ---------------------------------------------------------------------------
# Python templates
# ---------------------------------------------------------------------------


def _py_injection(seed: int) -> Base:
    p = _ident("user_id", seed)
    q = _ident("sql", seed)
    src = f'''"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, {p}):
        {q} = "SELECT * FROM orders WHERE id = '" + {p} + "'"
        self.cursor.execute({q})
        return self.cursor.fetchall()
'''
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if ".execute(" in ln)
    return Base(
        "injection",
        "python",
        "order_service.py",
        src,
        sink_line,
        f"tainted arg `{p}` concatenated into `{q}` passed to cursor.execute",
    )


def _py_path_traversal(seed: int) -> Base:
    p = _ident("name", seed)
    src = f'''"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, {p}):
        target = os.path.join(self.root, {p})
        with open(target, "rb") as fh:
            return fh.read()
'''
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "open(target" in ln)
    return Base(
        "path-traversal",
        "python",
        "file_service.py",
        src,
        sink_line,
        f"tainted arg `{p}` joined into path opened by open()",
    )


def _py_ssrf(seed: int) -> Base:
    p = _ident("host", seed)
    src = f'''"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, {p}):
        url = "http://" + {p} + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status
'''
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "urlopen(" in ln)
    return Base(
        "ssrf",
        "python",
        "fetch_service.py",
        src,
        sink_line,
        f"tainted arg `{p}` built into url passed to urllib.request.urlopen",
    )


def _py_deserialization(seed: int) -> Base:
    p = _ident("blob", seed)
    src = f'''"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, {p}):
        data = pickle.loads({p})
        return data
'''
    lines = src.splitlines()
    sink_line = next(i for i, ln in enumerate(lines, 1) if "pickle.loads(" in ln)
    return Base(
        "deserialization",
        "python",
        "session_service.py",
        src,
        sink_line,
        f"tainted arg `{p}` deserialized via pickle.loads",
    )


# Ordered template registry: index -> renderer. The build cycles through this
# list to instantiate the requested number of seeds, balanced across classes
# and languages by construction (8 templates, round-robin).
TEMPLATES = [
    _java_injection,
    _py_injection,
    _java_path_traversal,
    _py_path_traversal,
    _java_ssrf,
    _py_ssrf,
    _java_deserialization,
    _py_deserialization,
]


def render(seed: int) -> Base:
    """Render the seeded-vuln base for a global seed index (round-robin template)."""
    return TEMPLATES[seed % len(TEMPLATES)](seed)
