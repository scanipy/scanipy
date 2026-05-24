# Clean closed-world base - synthetic, no reflection / dynamic dispatch.
# Used as an injection target by pipeline/inject_reflection.py.
# Ground truth (pre-injection): closed-world.


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def run(x, y):
    s = add(x, y)
    d = subtract(x, y)
    return multiply(s, d)
