"""Static analysis fixture. Never import or execute this target source."""

import os


def assemble(left, value, right):
    joined = left + value
    return joined + right


def run(input_value):
    if type(input_value) is not str:
        raise TypeError("exact str required")
    prefix = "printf '%s\\n' "
    suffix = " >/dev/null"
    command = assemble(prefix, input_value, suffix)
    os.system(command)
