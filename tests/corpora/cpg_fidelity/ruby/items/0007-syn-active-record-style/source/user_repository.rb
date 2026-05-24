# frozen_string_literal: true

# Rails ActiveRecord-style idiom (no Rails dependency): a repository that
# builds queries through `where`/`order` chaining and uses `send` to apply a
# scope by name. Models the dynamic-finder pattern the Joern Ruby front-end
# struggles with. `send`-based scope application is a dynamic site.
class UserRepository
  def initialize(connection)
    @connection = connection
  end

  def active_admins
    scope = base_scope
    scope = apply_scope(scope, :admins)
    apply_scope(scope, :active)
  end

  def base_scope
    @connection.table(:users)
  end

  def apply_scope(scope, name)
    scope.send(name)
  end

  def find(id)
    base_scope.where(id: id).first
  end
end
