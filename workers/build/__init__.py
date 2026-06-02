"""Worker-image build tooling (CMP-DEPLOY-02).

Contains `verify_pins` — the publish-time gate that refuses to build if any
pinned base-image / tool digest in `workers/pins.json` is unspecified
(AC-DEPLOY-02c). This is the upstream INV-2 producer defence: `env_digest`
must never derive from an unpinned input.
"""
