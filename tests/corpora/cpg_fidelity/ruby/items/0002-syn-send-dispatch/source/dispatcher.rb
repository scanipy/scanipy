# frozen_string_literal: true

# Dynamic dispatch via `send` / `public_send`. The call target is computed at
# runtime from a string/symbol; it is NOT statically resolvable in general.
# Ground-truth call graph records these as `dynamic_sites` (lower-bound).
class Dispatcher
  def initialize(handler)
    @handler = handler
  end

  def run(action, payload)
    name = normalize(action)
    @handler.send(name, payload)
  end

  def run_safe(action, payload)
    name = normalize(action)
    @handler.public_send(name, payload)
  end

  def normalize(action)
    action.to_s.downcase
  end
end
