// Package embedding exercises method promotion through struct embedding.
// An embedded type's methods are promoted to the outer struct; a call on the
// outer value may dispatch to the embedded method. A front-end must resolve the
// promoted call to the embedded method's definition, not lose it at the
// embedding boundary.
package embedding

// Base provides a Describe method that is promoted into Service.
type Base struct{ Name string }

// Describe returns the base name. Promoted into Service.
func (b Base) Describe() string { return b.Name }

// Logger is embedded by pointer to test pointer-embedding promotion.
type Logger struct{ Prefix string }

// Log formats a message with the prefix. Promoted into Service.
func (l *Logger) Log(msg string) string { return l.Prefix + msg }

// Service embeds Base (by value) and Logger (by pointer); both method sets are
// promoted onto *Service.
type Service struct {
	Base
	*Logger
}

// Handle uses the promoted Describe and Log methods. The call sites
// s.Describe() and s.Log(...) resolve to Base.Describe and (*Logger).Log.
func (s *Service) Handle(req string) string {
	name := s.Describe()
	return s.Log(name + ":" + req)
}

// Run constructs a Service and invokes the promoted-method path.
func Run() string {
	s := &Service{Base{"svc"}, &Logger{"["}}
	return s.Handle("req")
}
