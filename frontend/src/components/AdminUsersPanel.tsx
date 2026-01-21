// Overview: React component for admin users panel UI.

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
          <label className="inline-toggle">
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
        <form onSubmit={createUser} className="form-card" style={{ marginBottom: 16 }}>
          <div className="form-title">Create New User</div>
          <div className="form-row">
            <label className="form-stack">
              <span className="form-label">Username</span>
              <input
                className="input"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                required
              />
            </label>
            <label className="form-stack">
              <span className="form-label">Email</span>
              <input
                className="input"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
              />
            </label>
            <label className="form-stack">
              <span className="form-label">Password</span>
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
              />
            </label>
            <label className="form-stack">
              <span className="form-label">Role</span>
              <select className="select" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
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
              className="btn btn--primary"
              style={{ marginTop: 18 }}
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
          <p className="helper-text" style={{ marginTop: 8 }}>
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
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr
                    key={user.id}
                    className={selectedUser?.id === user.id ? "table-row--selected" : ""}
                    style={{ opacity: user.is_active ? 1 : 0.6 }}
                  >
                    <td>{user.username}</td>
                    <td>{user.email}</td>
                    <td>
                      <span
                        className={`status-pill ${
                          user.is_active ? "status-pill--success" : "status-pill--danger"
                        }`}
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <div className="form-actions">
                        <button
                          onClick={() => loadUserDetails(user.id)}
                          className="btn btn--ghost btn--sm"
                        >
                          Details
                        </button>
                        {user.is_active ? (
                          <button
                            onClick={() => deactivateUser(user.id)}
                            className="btn btn--ghost btn--sm"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            onClick={() => reactivateUser(user.id)}
                            className="btn btn--ghost btn--sm"
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
          <div className="form-card" style={{ width: 320 }}>
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
                className={`status-pill ${
                  selectedUser.is_active ? "status-pill--success" : "status-pill--danger"
                }`}
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
              <p className="helper-text">No roles assigned</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {selectedUserRoles.map((role) => (
                  <li key={role} style={{ marginBottom: 4 }}>
                    {role}
                    <button
                      onClick={() => removeRole(selectedUser.id, role)}
                      className="btn btn--ghost btn--sm"
                      style={{ marginLeft: 8 }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <h4 style={{ marginTop: 16 }}>Assign Role</h4>
            <div className="form-actions">
              <select id="assign-role-select" defaultValue="" className="select">
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
                className="btn btn--primary btn--sm"
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
              className="btn btn--ghost"
              style={{ marginTop: 16 }}
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
