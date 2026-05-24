// Package ifacedispatch exercises dynamic dispatch over a Go interface.
// This is the central Stage-C challenge (CLAR-FE-02): a sound front-end must
// resolve an interface call site to the set of concrete methods that may run.
// CHA (class-hierarchy analysis) over-approximates this set with all methods
// whose receiver type implements the interface; that over-approximation is the
// recall-safe ground truth recorded here.
package ifacedispatch

// Shape is the dispatch interface.
type Shape interface {
	Area() float64
}

// Rect implements Shape.
type Rect struct{ W, H float64 }

// Area returns the rectangle area.
func (r Rect) Area() float64 { return r.W * r.H }

// Circle implements Shape.
type Circle struct{ R float64 }

// Area returns the circle area.
func (c Circle) Area() float64 { return 3.14159 * c.R * c.R }

// Triangle implements Shape but is never instantiated in TotalArea; it exists
// to verify the front-end does not under-count the CHA cone of Area().
type Triangle struct{ B, H float64 }

// Area returns the triangle area.
func (t Triangle) Area() float64 { return 0.5 * t.B * t.H }

// TotalArea sums the areas of a slice of shapes via a dynamic Area() call.
// The call site s.Area() dispatches to one of {Rect,Circle,Triangle}.Area.
func TotalArea(shapes []Shape) float64 {
	var sum float64
	for _, s := range shapes {
		sum += s.Area()
	}
	return sum
}

// Run builds two concrete shapes and totals their area through the interface.
func Run() float64 {
	shapes := []Shape{Rect{2, 3}, Circle{1}}
	return TotalArea(shapes)
}
