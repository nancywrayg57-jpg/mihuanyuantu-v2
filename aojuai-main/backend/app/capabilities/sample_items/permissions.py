"""Permission codes are a public API shared by routes, menus, and the UI."""

READ = "sample_items:read"
CREATE = "sample_items:create"
UPDATE = "sample_items:update"
DELETE = "sample_items:delete"

ALL_PERMISSIONS = (READ, CREATE, UPDATE, DELETE)

__all__ = ["ALL_PERMISSIONS", "CREATE", "DELETE", "READ", "UPDATE"]
