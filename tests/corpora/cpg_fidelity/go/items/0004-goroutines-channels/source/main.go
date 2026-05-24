// Package concurrency exercises goroutine spawn sites and channel data flow.
// `go f(...)` is a call edge from the spawning function to f that a front-end
// must not drop merely because it is asynchronous. Channel send/receive pairs
// are PDG data-dependence edges, not call edges.
package concurrency

// produce sends n integers onto out then closes it.
func produce(n int, out chan<- int) {
	for i := 0; i < n; i++ {
		out <- i
	}
	close(out)
}

// consume sums every value received from in.
func consume(in <-chan int) int {
	sum := 0
	for v := range in {
		sum += v
	}
	return sum
}

// Run spawns produce as a goroutine and consumes its output synchronously.
// The `go produce(...)` statement is a call edge Run -> produce.
func Run(n int) int {
	ch := make(chan int)
	go produce(n, ch)
	return consume(ch)
}
