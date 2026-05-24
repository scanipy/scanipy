# frozen_string_literal: true

# `define_method` metaprogramming: methods are synthesized at class-load time
# from data. The defined methods have no static `def` site; the ground-truth
# records `define_method` as a dynamic site (lower-bound).
class DynamicAccessors
  FIELDS = %i[name email role].freeze

  FIELDS.each do |field|
    define_method(field) do
      fetch(field)
    end

    define_method("#{field}=") do |value|
      store(field, value)
    end
  end

  def initialize
    @data = {}
  end

  def fetch(field)
    @data[field]
  end

  def store(field, value)
    @data[field] = value
  end
end
