"""CMP-FND-03 — software-backed :class:`KMSAsymmetricSigner` stand-in.

**NEVER for production customer traffic.** CLAR-DEPLOY-16 (RESOLVED
2026-05-23) ratified one real AWS KMS asymmetric CMK per tenant, but no such
CMK exists yet: verified live (2026-07-17, account 508703380027, us-east-1)
via ``aws kms list-aliases`` — zero ``scanipy``-tagged keys/aliases, and no
Terraform module under ``infra/`` provisions one. Filed as **CLAR-DEPLOY-24**
(``WBS.md §17``), which also records a second, independent gap: the
``KMSAsymmetricSigner.get_public_key`` contract takes a separate ``KeyVersion``
per call to model key-material rotation, but AWS KMS **does not support
automatic rotation for asymmetric CMKs** — there is no native rotation
concept to bind ``KeyVersion`` to. A real ``boto3``-backed implementation
needs a design resolution for that mismatch before it can be built correctly;
guessing at one here would be inventing scope (RULE-4).

Until both land, this module is the explicitly-flagged shortcut-path stand-in
(mirrors the already-established ``CLAR-CP-01-02`` test-auth-bypass pattern
in ``scripts/seed_test_org.py``: real crypto operations — RSASSA-PSS via the
``cryptography`` library, not a no-op — but refuses at construction time
whenever ``ENV``/``SCANIPY_ENV`` is ``"prod"`` — see :func:`refuse_if_prod`).
The class itself was relocated (not duplicated) from
``tests/fnd03_fakes.py::SoftwareKMSSigner``, which now imports it from here,
so the hermetic test suite and this production-namespaced default share one
implementation.
"""

from __future__ import annotations

from collections.abc import Mapping

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

__all__ = ["SoftwareKMSSigner", "SoftwareKmsSignerProdRefusalError", "refuse_if_prod"]


class SoftwareKmsSignerProdRefusalError(RuntimeError):
    """Raised by :func:`refuse_if_prod` — the fail-closed ENV/SCANIPY_ENV gate."""


def refuse_if_prod(env: Mapping[str, str] | None = None) -> None:
    """Fail closed: refuse to construct a software signer when ENV/SCANIPY_ENV is "prod".

    Identical contract to ``scripts/seed_test_org.py::refuse_if_prod``
    (CLAR-CP-01-02): checked against both env var names in use across this
    repo (``ENV`` — shell apply scripts; ``SCANIPY_ENV`` — application code,
    ``tools/observability/init.py``), case-insensitive and whitespace-trimmed.
    An unset value does NOT refuse — only an explicit "prod" trips the gate.
    """
    import os

    source = env if env is not None else os.environ
    for var_name in ("ENV", "SCANIPY_ENV"):
        value = source.get(var_name)
        if value is not None and value.strip().casefold() == "prod":
            raise SoftwareKmsSignerProdRefusalError(
                f"refusing to construct SoftwareKMSSigner: {var_name}={value!r} — "
                "this is a TEST/DEV-ONLY software stand-in for the not-yet-"
                "provisioned real KMS CMK (CLAR-DEPLOY-24) and must never run "
                "against a production environment"
            )


class SoftwareKMSSigner:
    """Offline RSASSA-PSS signer modelling KMS sign / get_public_key.

    A single 2048-bit RSA key stands in for one per-tenant CMK. ``sign`` returns
    the boto3-shaped ``{"Signature", "KeyId"}`` dict; ``get_public_key`` returns
    the DER ``SubjectPublicKeyInfo`` bytes under ``"PublicKey"`` for the pinned
    ``(KeyId, KeyVersion)``. An unknown key version yields no ``PublicKey`` so
    the verifier returns ``KEY_NOT_FOUND``.

    ``env`` is threaded through to :func:`refuse_if_prod` for hermetic tests;
    production callers omit it (defaults to ``os.environ``).
    """

    def __init__(self, *, version: str = "v1", env: Mapping[str, str] | None = None) -> None:
        refuse_if_prod(env)
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._version = version

    def sign(
        self,
        *,
        KeyId: str,  # noqa: N803 — boto3 wire parameter names are PascalCase.
        Message: bytes,  # noqa: N803
        SigningAlgorithm: str,  # noqa: N803
    ) -> dict[str, object]:
        digest = hashes.SHA384() if SigningAlgorithm == "RSASSA_PSS_SHA_384" else hashes.SHA256()
        signature = self._private.sign(
            Message,
            padding.PSS(mgf=padding.MGF1(digest), salt_length=padding.PSS.DIGEST_LENGTH),
            digest,
        )
        # boto3 returns the version-qualified key id under "KeyId".
        return {"Signature": signature, "KeyId": f"{KeyId}:{self._version}"}

    def get_public_key(
        self,
        *,
        KeyId: str,  # noqa: N803
        KeyVersion: str,  # noqa: N803
    ) -> dict[str, object]:
        if KeyVersion != self._version:
            # Unknown version -> KMS would not resolve a public key.
            return {}
        der = self._private.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        return {"PublicKey": der}
