// Package directcalls exercises the simplest call-graph case: static,
// monomorphic, intra-package function calls. This is the baseline against
// which a front-end's call-edge precision/recall must be near-perfect; any
// miss here is a structural front-end defect, not an undecidability cost.
package directcalls

// add returns the sum of two integers.
func add(a, b int) int {
	return a + b
}

// double returns twice its argument by calling add.
func double(x int) int {
	return add(x, x)
}

// quadruple returns four times its argument by calling double twice.
func quadruple(x int) int {
	return double(double(x))
}

// Run is the package entry point; it chains the arithmetic helpers.
func Run(seed int) int {
	a := add(seed, 1)
	b := double(a)
	c := quadruple(b)
	return c
}
