// Overview: React workflow component for transfers workflow operations.

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

type Store = {
  id: number;
  name: string;
  code: string | null;
};

type Product = {
  id: number;
  sku: string;
  name: string;
};

type Transfer = {
  id: number;
  from_store_id: number;
  to_store_id: number;
  status: string;
  reason: string | null;
  created_at: string;
  lines?: TransferLine[];
};

type TransferLine = {
  id: number;
  product_id: number;
  quantity: number;
  product_name?: string;
};

type Props = {
  storeId: number;
  isAuthed: boolean;
};

export function TransfersWorkflow({ storeId, isAuthed }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Stores and products for pickers
  const [stores, setStores] = useState<Store[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  // List of transfers
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  // Transfer creation
  const [fromStoreId, setFromStoreId] = useState<number>(storeId);
  const [toStoreId, setToStoreId] = useState<number | "">("");
  const [reason, setReason] = useState("");
  const [selectedProducts, setSelectedProducts] = useState<{ productId: number; quantity: number }[]>([]);
  const [newProductId, setNewProductId] = useState<number | "">("");
  const [newQuantity, setNewQuantity] = useState("");

  // Selected transfer for details
  const [selectedTransfer, setSelectedTransfer] = useState<Transfer | null>(null);

  async function loadStores() {
    try {
      const result = await apiGet<Store[]>("/api/stores");
      setStores(result ?? []);
    } catch (e: any) {
      console.error("Failed to load stores:", e);
    }
  }

  async function loadProducts() {
    try {
      const result = await apiGet<{ items: Product[] }>(`/api/products?store_id=${storeId}`);
      setProducts(result.items ?? []);
    } catch (e: any) {
      console.error("Failed to load products:", e);
    }
  }

  async function loadTransfers() {
    if (!isAuthed) return;
    setLoading(true);
    try {
      let url = `/api/transfers?store_id=${storeId}`;
      if (filterStatus === "pending") {
        url = `/api/transfers/pending`;
      } else if (filterStatus === "in_transit") {
        url = `/api/transfers/in-transit`;
      }
      const result = await apiGet<{ transfers: Transfer[] }>(url);
      setTransfers(result.transfers ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load transfers");
    } finally {
      setLoading(false);
    }
  }

  function addProductToTransfer() {
    if (!newProductId || !newQuantity) return;
    const qty = parseInt(newQuantity);
    if (qty <= 0) return;

    // Check if product already added
    const existing = selectedProducts.find((p) => p.productId === newProductId);
    if (existing) {
      setSelectedProducts(
        selectedProducts.map((p) =>
          p.productId === newProductId ? { ...p, quantity: p.quantity + qty } : p
        )
      );
    } else {
      setSelectedProducts([...selectedProducts, { productId: newProductId as number, quantity: qty }]);
    }
    setNewProductId("");
    setNewQuantity("");
  }

  function removeProduct(productId: number) {
    setSelectedProducts(selectedProducts.filter((p) => p.productId !== productId));
  }

  async function createTransfer() {
    if (!toStoreId || selectedProducts.length === 0) {
      setError("Select destination store and at least one product");
      return;
    }
    setError(null);
    setNotice(null);

    try {
      // Create transfer
      const result = await apiPost<{ transfer: Transfer }>("/api/transfers", {
        from_store_id: fromStoreId,
        to_store_id: toStoreId,
        reason: reason || undefined,
      });

      const transferId = result.transfer.id;

      // Add lines
      for (const item of selectedProducts) {
        await apiPost(`/api/transfers/${transferId}/lines`, {
          product_id: item.productId,
          quantity: item.quantity,
        });
      }

      setNotice(`Transfer #${transferId} created successfully`);
      setToStoreId("");
      setReason("");
      setSelectedProducts([]);
      loadTransfers();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create transfer");
    }
  }

  async function loadTransferDetails(transferId: number) {
    try {
      const result = await apiGet<{ transfer: Transfer }>(`/api/transfers/${transferId}`);
      setSelectedTransfer(result.transfer);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load transfer details");
    }
  }

  async function performAction(transferId: number, action: string, data?: Record<string, any>) {
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/api/transfers/${transferId}/${action}`, data ?? {});
      setNotice(`Transfer ${action} successfully`);
      loadTransfers();
      setSelectedTransfer(null);
    } catch (e: any) {
      setError(e?.message ?? `Failed to ${action} transfer`);
    }
  }

  useEffect(() => {
    loadStores();
    loadProducts();
    loadTransfers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthed, filterStatus, storeId]);

  useEffect(() => {
    setFromStoreId(storeId);
  }, [storeId]);

  if (!isAuthed) {
    return <p className="muted">Sign in to manage transfers.</p>;
  }

  const getStoreName = (id: number) => stores.find((s) => s.id === id)?.name ?? `Store #${id}`;
  const getProductName = (id: number) => {
    const p = products.find((p) => p.id === id);
    return p ? `${p.sku} - ${p.name}` : `Product #${id}`;
  };

  return (
    <div>
      {error && <div className="alert">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}

      {/* Create transfer section */}
      <div className="form-card" style={{ marginBottom: 16 }}>
        <h4>Create Transfer</h4>
        <div className="form-row" style={{ marginBottom: 12 }}>
          <label className="form-stack">
            <span className="form-label">From Store</span>
            <select
              className="select"
              value={fromStoreId}
              onChange={(e) => setFromStoreId(Number(e.target.value))}
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-stack">
            <span className="form-label">To Store</span>
            <select
              className="select"
              value={toStoreId}
              onChange={(e) => setToStoreId(Number(e.target.value))}
            >
              <option value="">Select destination</option>
              {stores
                .filter((s) => s.id !== fromStoreId)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="form-stack">
            <span className="form-label">Reason</span>
            <input
              className="input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Optional"
            />
          </label>
        </div>

        {/* Product selection */}
        <div style={{ marginBottom: 12 }}>
          <strong>Products:</strong>
          <div className="form-actions" style={{ marginTop: 8 }}>
            <select
              className="select"
              value={newProductId}
              onChange={(e) => setNewProductId(Number(e.target.value))}
            >
              <option value="">Select product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} - {p.name}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              value={newQuantity}
              onChange={(e) => setNewQuantity(e.target.value)}
              placeholder="Qty"
              className="input"
              style={{ width: 100 }}
            />
            <button onClick={addProductToTransfer} className="btn btn--primary btn--sm">
              Add
            </button>
          </div>

          {selectedProducts.length > 0 && (
            <ul style={{ marginTop: 8 }}>
              {selectedProducts.map((item) => (
                <li key={item.productId} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {getProductName(item.productId)} x {item.quantity}
                  <button onClick={() => removeProduct(item.productId)} className="btn btn--ghost btn--sm">
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button onClick={createTransfer} className="btn btn--primary" disabled={!toStoreId || selectedProducts.length === 0}>
          Create Transfer
        </button>
      </div>

      {/* Transfers list */}
      <div>
        <div className="form-row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <h4>Transfers ({transfers.length})</h4>
          <select className="select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
            <option value="all">All</option>
            <option value="pending">Pending Approval</option>
            <option value="in_transit">In Transit</option>
          </select>
        </div>

        {loading ? (
          <p>Loading...</p>
        ) : transfers.length === 0 ? (
          <p className="muted">No transfers found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>From</th>
                <th>To</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {transfers.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>{getStoreName(t.from_store_id)}</td>
                  <td>{getStoreName(t.to_store_id)}</td>
                  <td>
                    <span
                      className={`status-pill ${
                        t.status === "PENDING"
                          ? "status-pill--warning"
                          : t.status === "APPROVED"
                            ? "status-pill--success"
                            : t.status === "IN_TRANSIT"
                              ? "status-pill--info"
                              : t.status === "RECEIVED"
                                ? "status-pill--success"
                                : "status-pill--danger"
                      }`}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td>
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="form-actions">
                      <button onClick={() => loadTransferDetails(t.id)} className="btn btn--ghost btn--sm">
                        View
                      </button>
                      {t.status === "PENDING" && (
                        <>
                          <button onClick={() => performAction(t.id, "approve")} className="btn btn--primary btn--sm">
                            Approve
                          </button>
                          <button onClick={() => performAction(t.id, "cancel")} className="btn btn--warn btn--sm">
                            Cancel
                          </button>
                        </>
                      )}
                      {t.status === "APPROVED" && (
                        <button onClick={() => performAction(t.id, "ship")} className="btn btn--primary btn--sm">
                          Ship
                        </button>
                      )}
                      {t.status === "IN_TRANSIT" && (
                        <button onClick={() => performAction(t.id, "receive")} className="btn btn--primary btn--sm">
                          Receive
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

      {/* Transfer details modal */}
      {selectedTransfer && (
        <div className="overlay" onClick={() => setSelectedTransfer(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h3>Transfer #{selectedTransfer.id}</h3>
            <p><strong>Status:</strong> {selectedTransfer.status}</p>
            <p><strong>From:</strong> {getStoreName(selectedTransfer.from_store_id)}</p>
            <p><strong>To:</strong> {getStoreName(selectedTransfer.to_store_id)}</p>
            <p><strong>Reason:</strong> {selectedTransfer.reason || "None"}</p>
            <p><strong>Created:</strong> {new Date(selectedTransfer.created_at).toLocaleString()}</p>

            {selectedTransfer.lines && selectedTransfer.lines.length > 0 && (
              <>
                <h4>Items</h4>
                <ul>
                  {selectedTransfer.lines.map((line) => (
                    <li key={line.id}>
                      {line.product_name || getProductName(line.product_id)} x {line.quantity}
                    </li>
                  ))}
                </ul>
              </>
            )}

            <button onClick={() => setSelectedTransfer(null)} className="btn btn--ghost" style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
