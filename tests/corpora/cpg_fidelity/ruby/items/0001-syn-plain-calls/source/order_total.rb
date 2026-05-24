# frozen_string_literal: true

# Closed-world: every call target is statically resolvable. No dynamic dispatch.
# Exercises plain intra-file call edges + simple branch CFG + def-use PDG.
class OrderTotal
  def initialize(items)
    @items = items
  end

  def subtotal
    sum = 0
    @items.each do |line|
      sum = add(sum, line)
    end
    sum
  end

  def add(running, line)
    running + line
  end

  def with_tax(rate)
    base = subtotal
    if rate > 0
      base + tax(base, rate)
    else
      base
    end
  end

  def tax(base, rate)
    base * rate
  end
end
