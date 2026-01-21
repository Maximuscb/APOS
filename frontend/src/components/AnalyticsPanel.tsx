// Overview: Analytics dashboard with quick reports.

import { useState } from "react";
import { apiGet } from "../lib/api";

type AnalyticsPanelProps = {
  storeId: number;
};

export function AnalyticsPanel({ storeId }: AnalyticsPanelProps) {
  const [output, setOutput] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function run(path: string) {
    setError(null);
    try {
      const result = await apiGet<any>(`${path}?store_id=${storeId}`);
      setOutput(JSON.stringify(result, null, 2));
    } catch (e: any) {
      setError(e?.message ?? "Failed to load analytics.");
    }
  }

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Analytics</h2>
          <p className="muted">Select a report to view.</p>
        </div>
      </div>
      <div className="panel__grid">
        <div className="panel__section">
          <button className="btn btn--primary" onClick={() => run("/api/analytics/sales-trends")}>Sales trends</button>
          <button className="btn btn--ghost" onClick={() => run("/api/analytics/inventory-valuation")}>Inventory valuation</button>
          <button className="btn btn--ghost" onClick={() => run("/api/analytics/margin-cogs")}>Margin / COGS</button>
          <button className="btn btn--ghost" onClick={() => run("/api/analytics/slow-stock")}>Slow & dead stock</button>
          <button className="btn btn--ghost" onClick={() => run("/api/analytics/cashier-performance")}>Cashier performance</button>
          <button className="btn btn--ghost" onClick={() => run("/api/analytics/register-performance")}>Register performance</button>
        </div>
        <div className="panel__section">
          {error && <div className="alert">{error}</div>}
          {output && (
            <pre className="code-block">{output}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
