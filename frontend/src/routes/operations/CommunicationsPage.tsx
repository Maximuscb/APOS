import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';

interface Announcement {
  id: number;
  title: string;
  body: string;
  priority: string;
  target_type: string;
  is_active: boolean;
  created_at: string;
}

interface Reminder {
  id: number;
  title: string;
  body: string;
  repeat_type: string;
  is_active: boolean;
  created_at: string;
}

interface TaskItem {
  id: number;
  title: string;
  description: string | null;
  task_type: string;
  status: string;
  assigned_to_user_id: number | null;
  due_at: string | null;
  created_at: string;
}

const priorityVariant: Record<string, 'default' | 'primary' | 'warning' | 'danger'> = {
  LOW: 'default',
  NORMAL: 'primary',
  HIGH: 'warning',
  URGENT: 'danger',
};

export function CommunicationsPage() {
  const { currentStoreId } = useStore();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('MANAGE_COMMUNICATIONS');

  const [activeTab, setActiveTab] = useState('announcements');
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false);
  const [formTitle, setFormTitle] = useState('');
  const [formBody, setFormBody] = useState('');
  const [formPriority, setFormPriority] = useState('NORMAL');

  const fetchAll = useCallback(() => {
    if (!currentStoreId) return;
    setLoading(true);
    Promise.all([
      api.get<Announcement[]>(`/api/communications/announcements?store_id=${currentStoreId}`),
      api.get<Reminder[]>(`/api/communications/reminders?store_id=${currentStoreId}`),
      api.get<TaskItem[]>(`/api/communications/tasks?store_id=${currentStoreId}`),
    ])
      .then(([a, r, t]) => {
        setAnnouncements(a);
        setReminders(r);
        setTasks(t);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [currentStoreId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleCreate = async () => {
    if (!formTitle.trim()) return;
    const endpoint = activeTab === 'announcements'
      ? '/api/communications/announcements'
      : activeTab === 'reminders'
        ? '/api/communications/reminders'
        : '/api/communications/tasks';

    const body: Record<string, unknown> = { title: formTitle, store_id: currentStoreId };
    if (activeTab !== 'tasks') body.body = formBody;
    else body.description = formBody;
    if (activeTab === 'announcements') body.priority = formPriority;

    await api.post(endpoint, body);
    setShowCreate(false);
    setFormTitle('');
    setFormBody('');
    setFormPriority('NORMAL');
    fetchAll();
  };

  const toggleActive = async (type: 'announcements' | 'reminders', id: number, isActive: boolean) => {
    await api.patch(`/api/communications/${type}/${id}`, { is_active: !isActive });
    fetchAll();
  };

  const updateTaskStatus = async (id: number, status: string) => {
    await api.patch(`/api/communications/tasks/${id}`, { status });
    fetchAll();
  };

  const tabs = [
    { value: 'announcements', label: `Announcements (${announcements.length})` },
    { value: 'reminders', label: `Reminders (${reminders.length})` },
    { value: 'tasks', label: `Tasks (${tasks.length})` },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Communications</h1>
        {canManage && (
          <Button onClick={() => setShowCreate(true)}>
            + New {activeTab === 'announcements' ? 'Announcement' : activeTab === 'reminders' ? 'Reminder' : 'Task'}
          </Button>
        )}
      </div>

      <Tabs tabs={tabs} value={activeTab} onValueChange={setActiveTab} />

      {loading ? (
        <p className="text-muted">Loading...</p>
      ) : activeTab === 'announcements' ? (
        <div className="space-y-3">
          {announcements.length === 0 && <p className="text-muted text-sm">No announcements.</p>}
          {announcements.map((a) => (
            <Card key={a.id} className="p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={priorityVariant[a.priority] ?? 'default'}>{a.priority}</Badge>
                  {!a.is_active && <Badge variant="default">Inactive</Badge>}
                </div>
                <h3 className="font-semibold text-slate-900">{a.title}</h3>
                <p className="text-sm text-muted mt-1 line-clamp-2">{a.body}</p>
                <p className="text-xs text-muted mt-1">{formatDateTime(a.created_at)}</p>
              </div>
              {canManage && (
                <Button size="sm" variant="outline" onClick={() => toggleActive('announcements', a.id, a.is_active)}>
                  {a.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              )}
            </Card>
          ))}
        </div>
      ) : activeTab === 'reminders' ? (
        <div className="space-y-3">
          {reminders.length === 0 && <p className="text-muted text-sm">No reminders.</p>}
          {reminders.map((r) => (
            <Card key={r.id} className="p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="primary">{r.repeat_type}</Badge>
                  {!r.is_active && <Badge variant="default">Inactive</Badge>}
                </div>
                <h3 className="font-semibold text-slate-900">{r.title}</h3>
                <p className="text-sm text-muted mt-1 line-clamp-2">{r.body}</p>
                <p className="text-xs text-muted mt-1">{formatDateTime(r.created_at)}</p>
              </div>
              {canManage && (
                <Button size="sm" variant="outline" onClick={() => toggleActive('reminders', r.id, r.is_active)}>
                  {r.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.length === 0 && <p className="text-muted text-sm">No tasks.</p>}
          {tasks.map((t) => (
            <Card key={t.id} className="p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={t.status === 'COMPLETED' ? 'primary' : t.status === 'DEFERRED' ? 'warning' : 'default'}>
                    {t.status}
                  </Badge>
                  <Badge variant="default">{t.task_type}</Badge>
                </div>
                <h3 className="font-semibold text-slate-900">{t.title}</h3>
                {t.description && <p className="text-sm text-muted mt-1 line-clamp-2">{t.description}</p>}
                <p className="text-xs text-muted mt-1">{formatDateTime(t.created_at)}</p>
              </div>
              {t.status === 'PENDING' && (
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" onClick={() => updateTaskStatus(t.id, 'COMPLETED')}>Complete</Button>
                  <Button size="sm" variant="outline" onClick={() => updateTaskStatus(t.id, 'DEFERRED')}>Defer</Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title={`New ${activeTab === 'announcements' ? 'Announcement' : activeTab === 'reminders' ? 'Reminder' : 'Task'}`}>
        <div className="space-y-4 p-1">
          <Input label="Title" value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {activeTab === 'tasks' ? 'Description' : 'Body'}
            </label>
            <textarea
              className="w-full rounded-xl border border-border px-3 py-2 text-sm min-h-[80px]"
              value={formBody}
              onChange={(e) => setFormBody(e.target.value)}
            />
          </div>
          {activeTab === 'announcements' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Priority</label>
              <select
                className="w-full rounded-xl border border-border px-3 py-2 text-sm"
                value={formPriority}
                onChange={(e) => setFormPriority(e.target.value)}
              >
                <option value="LOW">Low</option>
                <option value="NORMAL">Normal</option>
                <option value="HIGH">High</option>
                <option value="URGENT">Urgent</option>
              </select>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Create</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
