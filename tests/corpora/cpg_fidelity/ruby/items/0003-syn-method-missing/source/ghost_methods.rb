# frozen_string_literal: true

# `method_missing` ghost methods: calls to undefined names are intercepted at
# runtime. No static call edge exists for `record.find_by_name(...)`; the
# ground-truth flags `method_missing` as a dynamic site (lower-bound recall).
class GhostRecord
  def initialize(attrs)
    @attrs = attrs
  end

  def method_missing(name, *args)
    key = decode(name)
    if @attrs.key?(key)
      @attrs[key]
    else
      super
    end
  end

  def respond_to_missing?(name, include_private = false)
    @attrs.key?(decode(name)) || super
  end

  def decode(name)
    name.to_s.sub(/^find_by_/, '').to_sym
  end
end
