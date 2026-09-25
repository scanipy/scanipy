# September 25 — owner-confirmed presentation machine

The owner answered **“This machine”** when asked whether the local Docker demo
would use the current development machine. This settles machine identity, not
stage readiness. The presentation is expected on December 2 or 3, 2026; its exact
date remains unconfirmed.

The [structured observation](observation.json) records read-only checks bracketed
by **2026-09-25 13:21:07–13:21:09 UTC**. It is an authored selection of command
observations, not a full raw host/daemon dump or a hardware attestation. The
exact reply time and per-command UTC timestamps were not retained. No source
analysis, image build, container change or benchmark was performed.

The checkout remained at the main revision recorded in the
[foundation checkpoint](../2026-09-25-foundation-merges/README.md). That code
revision is context only; these are host-capacity observations, not code tests.

| Field | Observed value | Interpretation |
|---|---|---|
| OS / architecture | Ubuntu 22.04.5 LTS; Linux x86_64 | Current guest and Docker daemon agree |
| CPU | 32 exposed CPUs; Intel Xeon E5-2660 v4 @ 2.00 GHz | VMware guest topology, not proof of 32 physical cores or dedicated CPU capacity |
| RAM total | 67,379,802,112 bytes, about 62.75 GiB | Not an allocation available entirely to Scanipy |
| RAM available | 7,913,250,816 bytes, about 7.37 GiB | Transient; an earlier 13:14 observation was about 6.44 GiB |
| Swap | 2,146,119,680 of 2,147,479,552 bytes used | Nearly full; account for host memory pressure before heavy work |
| Disk available | 109,423,550,464 bytes, about 101.91 GiB | Workspace, `/tmp` and Docker root share `/dev/sda3`; do not add these figures |
| Docker | Server 29.1.3; Linux x86_64; 32 CPUs; same total RAM | Daemon root `/var/lib/docker`; no worker isolation or offline guarantee follows |

## Required actions before G3_STAGE

- [ ] Recheck available RAM, swap and shared free disk before every image build
  or native campaign. Establish a safe workload window with the owner if current
  workloads leave insufficient headroom; never stop unrelated processes or the
  existing app/database to obtain it.
- [ ] After the relevant safety, packaging and integration changes pass review,
  measure the accepted artifact's actual image size, peak memory, CPU use,
  disk/scratch growth, startup time and end-to-end latency on this machine.
  Separate fresh and warm runs, retain failures and set measured budgets.
- [ ] Verify actual Docker resource limits, source-mount protections, process
  cleanup and network isolation. A profile declaration or host capacity is not
  evidence that these controls were enforced.
- [ ] Rehearse the complete accepted demo twice with the required images,
  source/spec/model inputs, signing identities and verification material already
  available locally. Demonstrate operation without external network access.
- [ ] Exercise restart/recovery and fallback using the same accepted artifact;
  retain exact revisions, input hashes, limits, durations and results.
- [ ] Confirm the exact December presentation date when scheduled and recheck
  the machine/profile if its VM allocation, OS, Docker or storage changes.

No R15 milestone, C01–C18 claim or G0/G1/G2/G3 gate passes because these checks
identified the machine. Earlier reference-only frontend/resource observations
remain historical diagnostics; they are not retroactively stage acceptance.
