// Clean closed-world base - synthetic, no reflection / dynamic dispatch.
// Used as an injection target by pipeline/inject_reflection.py.
// Ground truth (pre-injection): closed-world.
package clean

func add(a, b int) int {
	return a + b
}

func subtract(a, b int) int {
	return a - b
}

func multiply(a, b int) int {
	return a * b
}

func Run(x, y int) int {
	s := add(x, y)
	d := subtract(x, y)
	return multiply(s, d)
}
