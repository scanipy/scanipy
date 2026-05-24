# frozen_string_literal: true

# Blocks, procs, and lambdas: higher-order call edges through `yield`,
# `block.call`, and stored lambdas. The indirect call sites (`call`, `yield`)
# are flagged so call-edge recall is read as a lower bound.
class Pipeline
  def initialize
    @steps = []
  end

  def add(&block)
    @steps << block
  end

  def run(input)
    @steps.reduce(input) do |acc, step|
      apply(step, acc)
    end
  end

  def apply(step, value)
    step.call(value)
  end

  def each_step
    @steps.each do |step|
      yield step
    end
  end

  DOUBLE = ->(x) { x * 2 }

  def doubler
    DOUBLE
  end
end
