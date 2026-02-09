import WorkflowsPage from '@/routes/operations/WorkflowsPage';

export default function InventoryWorkflowsPage() {
  return (
    <div className="w-full">
      <WorkflowsPage embedded includeReturns={false} />
    </div>
  );
}
