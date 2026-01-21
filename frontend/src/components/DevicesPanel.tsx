// Overview: Device management panel for registers, drawers, and printers.

import { useEffect, useState } from "react";
import { apiGet, apiPatch, apiPost } from "../lib/api";

type Register = {
  id: number;
  store_id: number;
  register_number: string;
  name: string;
  location: string | null;
  device_id: string | null;
  is_active: boolean;
  current_session?: { id: number; status: string } | null;
};

type DevicesPanelProps = {
  storeId: number;
  isAuthed: boolean;
};

export function DevicesPanel({ storeId, isAuthed }: DevicesPanelProps) {
  const [activeTab, setActiveTab] = useState<"registers" | "drawers" | "printers">("registers");
  const [registers, setRegisters] = useState<Register[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create register form
  const [createForm, setCreateForm] = useState({
    register_number: "",
    name: "",
    location: "",
    device_id: "",
  });

  // Edit register state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    location: "",
    device_id: "",
    is_active: true,
  });

  async function loadRegisters() {
    if (!isAuthed) {
      setRegisters([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<{ registers: Register[] }>(`/api/registers?store_id=${storeId}`);
      setRegisters(result.registers ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load registers");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateRegister() {
    if (!isAuthed) {
      setError("Login required.");
      return;
    }
    if (!createForm.register_number || !createForm.name) {
      setError("Register number and name are required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/registers/", {
        store_id: storeId,
        register_number: createForm.register_number,
        name: createForm.name,
        location: createForm.location || null,
        device_id: createForm.device_id || null,
      });
      setCreateForm({ register_number: "", name: "", location: "", device_id: "" });
      await loadRegisters();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create register");
    } finally {
      setLoading(false);
    }
  }

  function startEditing(register: Register) {
    setEditingId(register.id);
    setEditForm({
      name: register.name,
      location: register.location ?? "",
      device_id: register.device_id ?? "",
      is_active: register.is_active,
    });
  }

  function cancelEditing() {
    setEditingId(null);
    setEditForm({ name: "", location: "", device_id: "", is_active: true });
  }

  async function handleUpdateRegister(registerId: number) {
    if (!isAuthed) {
      setError("Login required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPatch(`/api/registers/${registerId}`, {
        name: editForm.name,
        location: editForm.location || null,
        device_id: editForm.device_id || null,
        is_active: editForm.is_active,
      });
      setEditingId(null);
      await loadRegisters();
    } catch (e: any) {
      setError(e?.message ?? "Failed to update register");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleActive(register: Register) {
    if (!isAuthed) {
      setError("Login required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPatch(`/api/registers/${register.id}`, {
        is_active: !register.is_active,
      });
      await loadRegisters();
    } catch (e: any) {
      setError(e?.message ?? "Failed to update register");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === "registers") {
      loadRegisters();
    }
  }, [storeId, isAuthed, activeTab]);

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Device Management</h2>
          <p className="muted">Manage registers, cash drawers, and receipt printers for Store {storeId}.</p>
        </div>
        <div className="panel__actions">
          <button className="btn btn--ghost" type="button" onClick={loadRegisters} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {!isAuthed && <div className="alert">Login required to manage devices.</div>}
      {error && <div className="alert">{error}</div>}

      <nav className="devices-tabs">
        <button
          className={`devices-tab ${activeTab === "registers" ? "devices-tab--active" : ""}`}
          onClick={() => setActiveTab("registers")}
        >
          Registers
        </button>
        <button
          className={`devices-tab ${activeTab === "drawers" ? "devices-tab--active" : ""}`}
          onClick={() => setActiveTab("drawers")}
        >
          Cash Drawers
        </button>
        <button
          className={`devices-tab ${activeTab === "printers" ? "devices-tab--active" : ""}`}
          onClick={() => setActiveTab("printers")}
        >
          Printers
        </button>
      </nav>

      {activeTab === "registers" && (
        <div className="devices-content">
          <div className="panel__grid">
            <div className="panel__section">
              <h3>Create Register</h3>
              <div className="form-grid">
                <input
                  className="input"
                  placeholder="Register number (e.g., REG-01)"
                  value={createForm.register_number}
                  onChange={(e) => setCreateForm({ ...createForm, register_number: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Name (e.g., Front Counter)"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Location (optional)"
                  value={createForm.location}
                  onChange={(e) => setCreateForm({ ...createForm, location: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Device ID (optional)"
                  value={createForm.device_id}
                  onChange={(e) => setCreateForm({ ...createForm, device_id: e.target.value })}
                />
                <button className="btn btn--primary" type="button" onClick={handleCreateRegister} disabled={loading}>
                  Create Register
                </button>
              </div>
            </div>
          </div>

          <div className="panel__section">
            <h3>Registers</h3>
            <div className="table">
              <div className="table__head">
                <span>Number</span>
                <span>Name</span>
                <span>Location</span>
                <span>Device ID</span>
                <span>Status</span>
                <span>Session</span>
                <span>Actions</span>
              </div>
              {registers.length === 0 ? (
                <div className="table__empty muted">No registers found.</div>
              ) : (
                registers.map((register) => (
                  <div key={register.id} className="table__row">
                    {editingId === register.id ? (
                      <>
                        <span>{register.register_number}</span>
                        <span>
                          <input
                            className="input input--sm"
                            value={editForm.name}
                            onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                          />
                        </span>
                        <span>
                          <input
                            className="input input--sm"
                            value={editForm.location}
                            onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                          />
                        </span>
                        <span>
                          <input
                            className="input input--sm"
                            value={editForm.device_id}
                            onChange={(e) => setEditForm({ ...editForm, device_id: e.target.value })}
                          />
                        </span>
                        <span>
                          <label className="inline-toggle">
                            <input
                              type="checkbox"
                              checked={editForm.is_active}
                              onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                            />
                            Active
                          </label>
                        </span>
                        <span>--</span>
                        <span className="table__actions">
                          <button className="btn btn--sm btn--primary" onClick={() => handleUpdateRegister(register.id)} disabled={loading}>
                            Save
                          </button>
                          <button className="btn btn--sm btn--ghost" onClick={cancelEditing} disabled={loading}>
                            Cancel
                          </button>
                        </span>
                      </>
                    ) : (
                      <>
                        <span><strong>{register.register_number}</strong></span>
                        <span>{register.name}</span>
                        <span className="muted">{register.location ?? "--"}</span>
                        <span className="muted">{register.device_id ?? "--"}</span>
                        <span>
                          <span className={`chip ${register.is_active ? "chip--success" : "chip--warn"}`}>
                            {register.is_active ? "Active" : "Inactive"}
                          </span>
                        </span>
                        <span>
                          {register.current_session?.status === "OPEN" ? (
                            <span className="chip chip--success">In Use</span>
                          ) : (
                            <span className="muted">Available</span>
                          )}
                        </span>
                        <span className="table__actions">
                          <button className="btn btn--sm btn--ghost" onClick={() => startEditing(register)} disabled={loading}>
                            Edit
                          </button>
                          <button
                            className="btn btn--sm btn--ghost"
                            onClick={() => handleToggleActive(register)}
                            disabled={loading || register.current_session?.status === "OPEN"}
                            title={register.current_session?.status === "OPEN" ? "Cannot deactivate while session is open" : ""}
                          >
                            {register.is_active ? "Deactivate" : "Activate"}
                          </button>
                        </span>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === "drawers" && (
        <div className="devices-content">
          <div className="panel__section">
            <h3>Cash Drawers</h3>
            <div className="devices-placeholder">
              <p className="muted">Cash drawer management coming soon.</p>
              <p className="muted">Drawers will be assignable to registers with tracking for serial numbers and pairing status.</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === "printers" && (
        <div className="devices-content">
          <div className="panel__section">
            <h3>Receipt Printers</h3>
            <div className="devices-placeholder">
              <p className="muted">Printer management coming soon.</p>
              <p className="muted">Configure receipt, kitchen, and label printers with network settings and test print functionality.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
