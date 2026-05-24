// Package generics exercises Go 1.18+ type parameters. Generic functions are
// instantiated per type argument; a front-end's call graph must connect call
// sites of a generic function to its (possibly multiple) instantiations. This
// is a documented stress point for Go front-ends and a Stage-C fidelity risk.
package generics

// Number constrains to the numeric types used below.
type Number interface {
	~int | ~float64
}

// Sum reduces a slice using the generic accumulator add.
func Sum[T Number](xs []T) T {
	var total T
	for _, x := range xs {
		total = add(total, x)
	}
	return total
}

// add is the generic binary accumulator instantiated at int and float64.
func add[T Number](a, b T) T {
	return a + b
}

// Run instantiates Sum at int and float64.
func Run() (int, float64) {
	i := Sum([]int{1, 2, 3})
	f := Sum([]float64{1.5, 2.5})
	return i, f
}
