import { useEffect, useState } from "react";
import { apiGet, apiPost, apiDelete } from "../lib/api";

type User = {
  id: number;
  username: string;
  email: string;
  store_id: number | null;
  is_active: boolean;
  created_at: string;
  roles?: string[];
  permissions?: string[];
};

type Role = {
  id: number;
  name: string;
  description: string | null;
};

type Props = {
  storeId: number;
  isAuthed: boolean;
};

export function AdminUsersPanel({ storeId, isAuthed }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(false);

  // Selected user for detail view
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedUserRoles, setSelectedUserRoles] = useState<string[]>([]);

  // Create user form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("cashier");
  const [creating, setCreating] = useState(false);

  async function loadUsers() {
    if (!isAuthed) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<{ users: User[] }>(
        `/api/admin/users?include_inactive=${showInactive}`
      );
      setUsers(result.users);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  async function loadRoles() {
    if (!isAuthed) return;
    try {
      const result = await apiGet<{ roles: Role[] }>("/api/admin/roles");
      setRoles(result.roles);
    } catch (e: any) {
      // Roles are optional for display
      console.error("Failed to load roles:", e);
    }
  }

  async function loadUserDetails(userId: number) {
    setError(null);
    try {
      const result = await apiGet<{ user: User }>(`/api/admin/users/${userId}`);
      setSelectedUser(result.user);
      setSelectedUserRoles(result.user.roles ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load user details");
    }
  }

  async function deactivateUser(userId: number) {
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/api/admin/users/${userId}/deactivate`, {});
      setNotice("User deactivated successfully");
      await loadUsers();
      if (selectedUser?.id === userId) {
        await loadUserDetails(userId);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to deactivate user");
    }
  }

  async function reactivateUser(userId: number) {
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/api/admin/users/${userId}/reactivate`, {});
      setNotice("User reactivated successfully");
      await loadUsers();
      if (selectedUser?.id === userId) {
        await loadUserDetails(userId);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to reactivate user");
    }
  }

  async function assignRole(userId: number, roleName: string) {
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/api/admin/users/${userId}/roles`, { role_name: roleName });
      setNotice(`Role "${roleName}" assigned successfully`);
      await loadUserDetails(userId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to assign role");
    }
  }

  async function removeRole(userId: number, roleName: string) {
    setError(null);
    setNotice(null);
    try {
      await apiDelete(`/api/admin/users/${userId}/roles/${roleName}`);
      setNotice(`Role "${roleName}" removed successfully`);
      await loadUserDetails(userId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to remove role");
    }
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setCreating(true);

    try {
      const result = await apiPost<{ user: User }>("/api/admin/users", {
        username: newUsername,
        email: newEmail,
        password: newPassword,
        store_id: storeId,
        role: newRole,
      });
      setNotice(`User "${result.user.username}" created successfully`);
      setShowCreateForm(false);
      setNewUsername("");
      setNewEmail("");
      setNewPassword("");
      setNewRole("cashier");
      await loadUsers();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    loadUsers();
    loadRoles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthed, showInactive]);

  if (!isAuthed) {
    return (
      <div className="panel panel--full">
        <div className="panel__header">
          <div>
            <h2>User Management</h2>
            <p className="muted">Sign in to manage users.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel panel--full">
      <div className="panel__header panel__header--split">
        <div>
          <h2>User Management</h2>
          <p className="muted">View, create, and manage user accounts and roles.</p>
        </div>
        <div className="panel__actions">
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
            />
            Show inactive
          </label>
          <button
            className="btn btn--primary"
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            {showCreateForm ? "Cancel" : "Create User"}
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}

      {showCreateForm && (
        <form onSubmit={createUser} style={{ marginBottom: 16, padding: 12, border: "1px solid #ddd", background: "#f9f9f9" }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Create New User</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span>Username</span>
              <input
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                required
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span>Email</span>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span>Password</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span>Role</span>
              <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                {roles.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={creating}
              style={{ padding: "8px 12px", cursor: "pointer", marginTop: 18 }}
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
          <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
            Password must be 8+ characters with uppercase, lowercase, digit, and special character.
          </p>
        </form>
      )}

      <div style={{ display: "flex", gap: 16 }}>
        {/* Users list */}
        <div style={{ flex: 1 }}>
          <h3>Users ({users.length})</h3>
          {loading ? (
            <p>Loading users...</p>
          ) : users.length === 0 ? (
            <p>No users found.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>
                    Username
                  </th>
                  <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>
                    Email
                  </th>
                  <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>
                    Status
                  </th>
                  <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr
                    key={user.id}
                    style={{
                      background: selectedUser?.id === user.id ? "#e3f2fd" : "transparent",
                      opacity: user.is_active ? 1 : 0.6,
                    }}
                  >
                    <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                      {user.username}
                    </td>
                    <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                      {user.email}
                    </td>
                    <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                      <span
                        style={{
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: user.is_active ? "#c8e6c9" : "#ffcdd2",
                          fontSize: 12,
                        }}
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          onClick={() => loadUserDetails(user.id)}
                          style={{ padding: "4px 8px", cursor: "pointer", fontSize: 12 }}
                        >
                          Details
                        </button>
                        {user.is_active ? (
                          <button
                            onClick={() => deactivateUser(user.id)}
                            style={{ padding: "4px 8px", cursor: "pointer", fontSize: 12 }}
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            onClick={() => reactivateUser(user.id)}
                            style={{ padding: "4px 8px", cursor: "pointer", fontSize: 12 }}
                          >
                            Reactivate
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* User details panel */}
        {selectedUser && (
          <div
            style={{
              width: 300,
              padding: 16,
              border: "1px solid #ddd",
              background: "#f9f9f9",
            }}
          >
            <h3>User Details</h3>
            <p>
              <strong>Username:</strong> {selectedUser.username}
            </p>
            <p>
              <strong>Email:</strong> {selectedUser.email}
            </p>
            <p>
              <strong>Store ID:</strong> {selectedUser.store_id ?? "None"}
            </p>
            <p>
              <strong>Status:</strong>{" "}
              <span
                style={{
                  padding: "2px 6px",
                  borderRadius: 4,
                  background: selectedUser.is_active ? "#c8e6c9" : "#ffcdd2",
                }}
              >
                {selectedUser.is_active ? "Active" : "Inactive"}
              </span>
            </p>
            <p>
              <strong>Created:</strong>{" "}
              {new Date(selectedUser.created_at).toLocaleDateString()}
            </p>

            <h4 style={{ marginTop: 16 }}>Roles</h4>
            {selectedUserRoles.length === 0 ? (
              <p style={{ color: "#666" }}>No roles assigned</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {selectedUserRoles.map((role) => (
                  <li key={role} style={{ marginBottom: 4 }}>
                    {role}
                    <button
                      onClick={() => removeRole(selectedUser.id, role)}
                      style={{
                        marginLeft: 8,
                        padding: "2px 6px",
                        cursor: "pointer",
                        fontSize: 11,
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <h4 style={{ marginTop: 16 }}>Assign Role</h4>
            <div style={{ display: "flex", gap: 8 }}>
              <select id="assign-role-select" defaultValue="">
                <option value="" disabled>
                  Select role
                </option>
                {roles
                  .filter((r) => !selectedUserRoles.includes(r.name))
                  .map((r) => (
                    <option key={r.name} value={r.name}>
                      {r.name}
                    </option>
                  ))}
              </select>
              <button
                onClick={() => {
                  const select = document.getElementById(
                    "assign-role-select"
                  ) as HTMLSelectElement;
                  if (select.value) {
                    assignRole(selectedUser.id, select.value);
                    select.value = "";
                  }
                }}
                style={{ padding: "4px 8px", cursor: "pointer" }}
              >
                Assign
              </button>
            </div>

            {selectedUser.permissions && selectedUser.permissions.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>Permissions</h4>
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: 20,
                    fontSize: 12,
                    maxHeight: 150,
                    overflow: "auto",
                  }}
                >
                  {selectedUser.permissions.map((perm) => (
                    <li key={perm}>{perm}</li>
                  ))}
                </ul>
              </>
            )}

            <button
              onClick={() => setSelectedUser(null)}
              style={{ marginTop: 16, padding: "6px 12px", cursor: "pointer" }}
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
