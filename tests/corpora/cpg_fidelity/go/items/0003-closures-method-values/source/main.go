// Package closures exercises first-class functions: closures over local state,
// function-valued parameters, and bound method values. These are higher-order
// call sites where a front-end must connect an indirect call (via a func value)
// to the function literals / methods that can flow to it.
package closures

// Counter holds a running total.
type Counter struct{ n int }

// Inc adds delta to the counter and returns the new total. Used as a bound
// method value below.
func (c *Counter) Inc(delta int) int {
	c.n += delta
	return c.n
}

// apply invokes the supplied function value with x. The call site f(x) is an
// indirect call; ground truth records the set of functions that can flow to f.
func apply(f func(int) int, x int) int {
	return f(x)
}

// makeAdder returns a closure capturing base.
func makeAdder(base int) func(int) int {
	return func(x int) int {
		return base + x
	}
}

// Run wires a closure and a bound method value through apply.
func Run() int {
	adder := makeAdder(10)
	a := apply(adder, 5)

	c := &Counter{}
	bound := c.Inc // bound method value
	b := apply(bound, a)
	return b
}
