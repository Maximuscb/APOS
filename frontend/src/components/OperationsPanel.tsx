// Overview: React component for operations panel UI.

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
      <div className="register-tabs" style={{ marginBottom: 16 }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`register-tab ${activeTab === tab.id ? "register-tab--active" : ""}`}
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
