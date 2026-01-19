import { useState } from "react";
import { ReturnsWorkflow } from "./operations/ReturnsWorkflow";
import { TransfersWorkflow } from "./operations/TransfersWorkflow";
import { CountsWorkflow } from "./operations/CountsWorkflow";

type Props = {
  storeId: number;
  isAuthed: boolean;
};

type Tab = "returns" | "transfers" | "counts";

export function OperationsPanel({ storeId, isAuthed }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("returns");

  const tabs: { id: Tab; label: string }[] = [
    { id: "returns", label: "Returns" },
    { id: "transfers", label: "Transfers" },
    { id: "counts", label: "Inventory Counts" },
  ];

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Operations</h2>
          <p className="muted">Manage returns, transfers, and inventory counts.</p>
        </div>
      </div>

      {/* Tab navigation */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #ddd", marginBottom: 16 }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "12px 24px",
              border: "none",
              background: activeTab === tab.id ? "#fff" : "#f5f5f5",
              borderBottom: activeTab === tab.id ? "2px solid #2563eb" : "2px solid transparent",
              cursor: "pointer",
              fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? "#2563eb" : "#666",
              transition: "all 0.15s ease",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ padding: "0 4px" }}>
        {activeTab === "returns" && <ReturnsWorkflow storeId={storeId} isAuthed={isAuthed} />}
        {activeTab === "transfers" && <TransfersWorkflow storeId={storeId} isAuthed={isAuthed} />}
        {activeTab === "counts" && <CountsWorkflow storeId={storeId} isAuthed={isAuthed} />}
      </div>
    </div>
  );
}
