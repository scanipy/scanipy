# Clean closed-world base - synthetic, no reflection / dynamic dispatch.
# Used as an injection target by pipeline/inject_reflection.py.
# Ground truth (pre-injection): closed-world.

class Calculator
  def add(a, b)
    a + b
  end

  def subtract(a, b)
    a - b
  end

  def multiply(a, b)
    a * b
  end

  def run(x, y)
    s = add(x, y)
    d = subtract(x, y)
    multiply(s, d)
  end
end
