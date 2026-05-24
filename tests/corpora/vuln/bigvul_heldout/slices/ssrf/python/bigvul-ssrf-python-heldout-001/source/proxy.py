# SYNTHESIZED BigVul-shaped CWE-918 (SSRF) held-out function authored for
# CMP-CORP-VULN-01. Represents the held-out row src/net/proxy.py::forward
# (row_id bigvul:100d0b9ffa07ebda3a9e0ed2894e1823) selected by the deterministic
# split (sha256(row_id) % 10 == 9). Ground truth by construction: the user-controlled
# target URL flows unchecked into an outbound request (SSRF sink).
import urllib.request


def forward(request):
    target = request.get("url")  # tainted: user-controlled destination
    resp = urllib.request.urlopen(target)  # SINK (CWE-918): no allow-list / no scheme check
    return resp.read()
