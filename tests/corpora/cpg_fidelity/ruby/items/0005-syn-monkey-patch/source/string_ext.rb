# frozen_string_literal: true

# Monkey-patch: a core class is reopened and a method added/overridden. A call
# to `"x".shout` resolves to this reopened definition only if this file is
# loaded. The ground-truth records the reopened def as a real call target; the
# open-class nature is flagged in the item's `monkey_patch` category tag.
class String
  def shout
    upcase_words + '!'
  end

  def upcase_words
    split(' ').map(&:upcase).join(' ')
  end
end

class Megaphone
  def announce(text)
    text.shout
  end
end
