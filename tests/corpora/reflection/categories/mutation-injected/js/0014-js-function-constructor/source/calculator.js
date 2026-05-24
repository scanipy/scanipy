// Clean closed-world base - synthetic, no reflection / dynamic dispatch.
// Used as an injection target by pipeline/inject_reflection.py.
// Ground truth (pre-injection): closed-world.

function add(a, b) {
  return a + b;
}

function subtract(a, b) {
  return a - b;
}

function multiply(a, b) {
  return a * b;
}

function run(x, y) {
  const s = add(x, y);
  const f = new Function("a", "b", "return a + b;");
  f(x, y);
  const d = subtract(x, y);
  return multiply(s, d);
}

module.exports = { add, subtract, multiply, run };
