# SYNTHESIZED Juliet-shaped CWE-22 case (Public Domain, authored for CMP-CORP-VULN-01).
# Ground truth: tainted source (request arg) reaches the open() sink.
import os


def action(request):
    name = request.get("file")  # BadSource: untrusted request parameter
    if name is not None:
        path = os.path.join("/var/data", name)
        with open(path, "rb") as fh:  # SINK (CWE-22): unsanitized path
            return fh.read()
    return None
