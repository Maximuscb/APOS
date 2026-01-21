// Overview: Manage per-user permission overrides.

import { useState } from "react";
import { apiGet, apiPost, apiDelete } from "../lib/api";

type Override = {
  id: number;
  user_id: number;
  permission_code: string;
  override_type: string;
  is_active: boolean;
};

export function PermissionOverridesPanel() {
  const [userId, setUserId] = useState("");
  const [permissionCode, setPermissionCode] = useState("");
  const [overrideType, setOverrideType] = useState("GRANT");
  const [overrides, setOverrides] = useState<Override[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    if (!userId) {
      setError("Enter a user ID.");
      return;
    }
    try {
      const result = await apiGet<{ overrides: Override[] }>(
        `/api/admin/users/${userId}/permission-overrides`
      );
      setOverrides(result.overrides ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load overrides.");
    }
  }

  async function saveOverride() {
    setError(null);
    if (!userId || !permissionCode) {
      setError("User ID and permission code required.");
      return;
    }
    try {
      await apiPost(`/api/admin/users/${userId}/permission-overrides`, {
        permission_code: permissionCode,
        override_type: overrideType,
      });
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Failed to save override.");
    }
  }

  async function revoke(code: string) {
    setError(null);
    try {
      await apiDelete(`/api/admin/users/${userId}/permission-overrides/${code}`);
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Failed to revoke override.");
    }
  }

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Permission Overrides</h2>
          <p className="muted">Grant or deny permissions per user.</p>
        </div>
      </div>

      <div className="panel__grid">
        <div className="panel__section">
          <label className="field">
            <span>User ID</span>
            <input className="input" value={userId} onChange={(e) => setUserId(e.target.value)} />
          </label>
          <button className="btn btn--ghost" type="button" onClick={load}>
            Load overrides
          </button>
        </div>
        <div className="panel__section">
          <label className="field">
            <span>Permission code</span>
            <input className="input" value={permissionCode} onChange={(e) => setPermissionCode(e.target.value)} />
          </label>
          <label className="field">
            <span>Override type</span>
            <select className="input" value={overrideType} onChange={(e) => setOverrideType(e.target.value)}>
              <option value="GRANT">GRANT</option>
              <option value="DENY">DENY</option>
            </select>
          </label>
          <button className="btn btn--primary" type="button" onClick={saveOverride}>
            Save override
          </button>
        </div>
      </div>

      <div className="table">
        <div className="table__head">
          <span>Permission</span>
          <span>Type</span>
          <span>Active</span>
          <span>Actions</span>
        </div>
        {overrides.length === 0 ? (
          <div className="table__empty muted">No overrides loaded.</div>
        ) : (
          overrides.map((ovr) => (
            <div key={ovr.id} className="table__row">
              <span>{ovr.permission_code}</span>
              <span>{ovr.override_type}</span>
              <span>{ovr.is_active ? "Yes" : "No"}</span>
              <span>
                <button className="btn btn--ghost" type="button" onClick={() => revoke(ovr.permission_code)}>
                  Revoke
                </button>
              </span>
            </div>
          ))
        )}
      </div>

      {error && <div className="alert">{error}</div>}
    </div>
  );
}
