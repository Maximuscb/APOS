import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input, Select } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';

interface NotificationRow {
  kind: 'ANNOUNCEMENT' | 'REMINDER';
  id: number;
  title: string;
  body: string;
  priority: string;
  target_type: 'USER' | 'STORE' | 'ORG' | 'ROLE';
  target_id: number | null;
  store_id: number | null;
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
  assigned_to_register_id: number | null;
  due_at: string | null;
  created_at: string;
}

interface UserOption {
  id: number;
  username: string;
  store_id: number | null;
  roles: string[];
  explicit_manager_store_ids: number[];
}

interface RoleOption {
  id: number;
  name: string;
}

interface RecipientOption {
  value: string;
  label: string;
}

const priorityVariant: Record<string, 'default' | 'primary' | 'warning' | 'danger'> = {
  LOW: 'default',
  NORMAL: 'primary',
  HIGH: 'warning',
  URGENT: 'danger',
};

function formatUserLabel(username: string | null | undefined) {
  const base = (username || '').trim();
  if (!base) return 'User';
  if (base.toLowerCase() === 'admin') return 'Admin';
  if (base.toLowerCase() === 'cashier') return 'Cashier';
  if (base.toLowerCase() === 'manager') return 'Manager';
  if (base.toLowerCase() === 'developer') return 'Developer';
  return base;
}

function hasRole(user: UserOption, roleName: string) {
  const target = roleName.toLowerCase();
  return (user.roles ?? []).some((r) => (r || '').toLowerCase() === target);
}

function isManagerForStore(user: UserOption, storeId: number) {
  if (hasRole(user, 'admin')) return true;
  if (hasRole(user, 'manager') && user.store_id === storeId) return true;
  return (user.explicit_manager_store_ids ?? []).includes(storeId);
}

function recipientLabel(
  n: NotificationRow,
  stores: Array<{ id: number; name: string }>,
  users: UserOption[],
  roles: RoleOption[],
) {
  if (n.target_type === 'ORG') return 'Organization-wide';
  if (n.target_type === 'STORE') {
    const storeName = stores.find((s) => s.id === n.target_id)?.name ?? `#${n.target_id}`;
    return `Store: ${storeName}`;
  }
  if (n.target_type === 'USER') {
    const userName = users.find((u) => u.id === n.target_id)?.username;
    return `User: ${formatUserLabel(userName)}`;
  }
  const roleName = roles.find((r) => r.id === n.target_id)?.name ?? `#${n.target_id}`;
  if (n.store_id) {
    const storeName = stores.find((s) => s.id === n.store_id)?.name ?? `#${n.store_id}`;
    return `Role: ${roleName} in ${storeName}`;
  }
  return `Role: ${roleName} (Organization)`;
}

export function CommunicationsPage() {
  const { currentStoreId, stores } = useStore();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('MANAGE_COMMUNICATIONS');

  const [activeTab, setActiveTab] = useState('notifications');
  const [notifications, setNotifications] = useState<NotificationRow[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loading, setLoading] = useState(true);

  const [showCreate, setShowCreate] = useState(false);
  const [showCreateTask, setShowCreateTask] = useState(false);
  const [formType, setFormType] = useState<'ANNOUNCEMENT' | 'REMINDER'>('ANNOUNCEMENT');
  const [formTitle, setFormTitle] = useState('');
  const [formBody, setFormBody] = useState('');
  const [formPriority, setFormPriority] = useState('NORMAL');
  const [selectedRecipients, setSelectedRecipients] = useState<string[]>([]);
  const [recipientSearch, setRecipientSearch] = useState('');
  const [formActive, setFormActive] = useState(true);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [taskAssignee, setTaskAssignee] = useState('');

  const fetchAll = useCallback(() => {
    setLoading(true);
    const sid = currentStoreId ? `?store_id=${currentStoreId}` : '';
    Promise.all([
      api.get<NotificationRow[]>(`/api/communications/notifications${sid}`),
      api.get<TaskItem[]>(`/api/communications/tasks${sid}`),
      api
        .get<{ users: Array<{ id: number; username: string; store_id: number | null; roles?: string[]; explicit_manager_store_ids?: number[] }> }>(
          '/api/admin/users',
        )
        .catch(() => ({ users: [] })),
      api.get<{ roles: Array<{ id: number; name: string }> }>('/api/admin/roles').catch(() => ({ roles: [] })),
    ])
      .then(([n, t, u, r]) => {
        setNotifications(n);
        setTasks(t);
        setUsers(
          (u.users ?? []).map((row) => ({
            id: row.id,
            username: row.username,
            store_id: row.store_id ?? null,
            roles: row.roles ?? [],
            explicit_manager_store_ids: row.explicit_manager_store_ids ?? [],
          })),
        );
        setRoles((r.roles ?? []).map((row) => ({ id: row.id, name: row.name })));
      })
      .finally(() => setLoading(false));
  }, [currentStoreId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const recipientCatalog = useMemo<RecipientOption[]>(() => {
    return [
      { value: 'SPECIAL:ALL_USERS', label: 'All Users (Organization)' },
      { value: 'SPECIAL:ALL_MANAGERS', label: 'All Managers (Organization)' },
      { value: 'SPECIAL:ALL_CASHIERS', label: 'All Cashiers (Organization)' },
      ...stores.flatMap((s) => [
        { value: `SPECIAL:STORE_USERS:${s.id}`, label: `Store - ${s.name} - All Users` },
        { value: `SPECIAL:STORE_MANAGERS:${s.id}`, label: `Store - ${s.name} - Managers` },
        { value: `SPECIAL:STORE_CASHIERS:${s.id}`, label: `Store - ${s.name} - Cashiers` },
      ]),
      ...users.map((u) => {
        const storeName = stores.find((s) => s.id === u.store_id)?.name ?? 'No Store';
        const roleText = u.roles.length > 0 ? u.roles.join(', ') : 'no role';
        return {
          value: `USER:${u.id}`,
          label: `${formatUserLabel(u.username)} - ${storeName} - ${roleText}`,
        };
      }),
    ];
  }, [stores, users]);

  const recipientOptions = useMemo<RecipientOption[]>(() => {
    const all = recipientCatalog;
    const search = recipientSearch.trim().toLowerCase();
    if (!search) return all;
    return all.filter((opt) => opt.label.toLowerCase().includes(search));
  }, [recipientSearch, recipientCatalog]);

  const selectedRecipientLabels = useMemo(() => {
    const lookup = new Map(recipientCatalog.map((r) => [r.value, r.label]));
    return selectedRecipients.map((value) => ({ value, label: lookup.get(value) ?? value }));
  }, [recipientCatalog, selectedRecipients]);

  const addRecipient = (value: string) => {
    if (!value) return;
    setSelectedRecipients((prev) => (prev.includes(value) ? prev : [...prev, value]));
  };

  const createNotification = async () => {
    if (!formTitle.trim() || !formBody.trim() || selectedRecipients.length === 0) return;

    const recipients = selectedRecipients;
    const userIds = new Set<number>();

    for (const recipient of recipients) {
      if (recipient.startsWith('USER:')) {
        const userId = Number(recipient.split(':')[1]);
        if (Number.isFinite(userId) && userId > 0) userIds.add(userId);
        continue;
      }
      if (recipient === 'SPECIAL:ALL_USERS') {
        users.forEach((u) => userIds.add(u.id));
        continue;
      }
      if (recipient === 'SPECIAL:ALL_MANAGERS') {
        users
          .filter((u) => hasRole(u, 'manager') || hasRole(u, 'admin') || (u.explicit_manager_store_ids?.length ?? 0) > 0)
          .forEach((u) => userIds.add(u.id));
        continue;
      }
      if (recipient === 'SPECIAL:ALL_CASHIERS') {
        users.filter((u) => hasRole(u, 'cashier')).forEach((u) => userIds.add(u.id));
        continue;
      }
      if (recipient.startsWith('SPECIAL:STORE_USERS:')) {
        const storeId = Number(recipient.split(':')[2]);
        if (Number.isFinite(storeId) && storeId > 0) users.filter((u) => u.store_id === storeId).forEach((u) => userIds.add(u.id));
        continue;
      }
      if (recipient.startsWith('SPECIAL:STORE_MANAGERS:')) {
        const storeId = Number(recipient.split(':')[2]);
        if (Number.isFinite(storeId) && storeId > 0) users.filter((u) => isManagerForStore(u, storeId)).forEach((u) => userIds.add(u.id));
        continue;
      }
      if (recipient.startsWith('SPECIAL:STORE_CASHIERS:')) {
        const storeId = Number(recipient.split(':')[2]);
        if (Number.isFinite(storeId) && storeId > 0) users.filter((u) => hasRole(u, 'cashier') && u.store_id === storeId).forEach((u) => userIds.add(u.id));
      }
    }

    for (const userId of userIds) {
      await api.post('/api/communications/notifications', {
        communication_type: formType,
        title: formTitle.trim(),
        body: formBody.trim(),
        priority: formPriority,
        is_active: formActive,
        target_type: 'USER',
        target_id: userId,
      });
    }

    setShowCreate(false);
    setFormTitle('');
    setFormBody('');
    setFormPriority('NORMAL');
    setSelectedRecipients([]);
    setRecipientSearch('');
    setFormType('ANNOUNCEMENT');
    setFormActive(true);
    fetchAll();
  };

  const createTask = async () => {
    if (!taskTitle.trim()) return;
    const payload: Record<string, unknown> = {
      title: taskTitle.trim(),
      description: taskDescription.trim() || undefined,
      store_id: currentStoreId,
      task_type: taskAssignee ? 'USER' : 'REGISTER',
    };
    if (taskAssignee) payload.assigned_to_user_id = Number(taskAssignee);
    await api.post('/api/communications/tasks', payload);
    setShowCreateTask(false);
    setTaskTitle('');
    setTaskDescription('');
    setTaskAssignee('');
    fetchAll();
  };

  const toggleActive = async (n: NotificationRow) => {
    await api.patch(`/api/communications/notifications/${n.kind}/${n.id}`, { is_active: !n.is_active });
    fetchAll();
  };

  const updateTaskStatus = async (id: number, status: 'COMPLETED' | 'DEFERRED') => {
    const deferredReason = status === 'DEFERRED' ? (window.prompt('Optional defer reason') ?? undefined) : undefined;
    await api.patch(`/api/communications/tasks/${id}`, { status, deferred_reason: deferredReason });
    fetchAll();
  };

  const tabs = [
    { value: 'notifications', label: `Notifications (${notifications.length})` },
    { value: 'tasks', label: `Tasks (${tasks.length})` },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Communications</h1>
        {canManage && activeTab === 'notifications' && <Button onClick={() => setShowCreate(true)}>+ New Notification</Button>}
        {canManage && activeTab === 'tasks' && <Button onClick={() => setShowCreateTask(true)}>+ New Task</Button>}
      </div>

      <Tabs tabs={tabs} value={activeTab} onValueChange={setActiveTab} />

      {loading ? (
        <p className="text-muted">Loading...</p>
      ) : activeTab === 'notifications' ? (
        <div className="space-y-3">
          {notifications.length === 0 && <p className="text-muted text-sm">No notifications.</p>}
          {notifications.map((n) => (
            <Card key={`${n.kind}-${n.id}`} className="p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={n.kind === 'REMINDER' ? 'warning' : (priorityVariant[n.priority] ?? 'default')}>{n.kind}</Badge>
                  {n.kind === 'ANNOUNCEMENT' && <Badge variant={priorityVariant[n.priority] ?? 'default'}>{n.priority}</Badge>}
                  {!n.is_active && <Badge variant="default">Inactive</Badge>}
                </div>
                <h3 className="font-semibold text-slate-900">{n.title}</h3>
                <p className="text-sm text-muted mt-1">{n.body}</p>
                <p className="text-xs text-muted mt-1">{recipientLabel(n, stores, users, roles)} - {formatDateTime(n.created_at)}</p>
              </div>
              {canManage && (
                <Button size="sm" variant="secondary" onClick={() => toggleActive(n)}>
                  {n.is_active ? 'Deactivate' : 'Activate'}
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
                  <Badge variant={t.status === 'COMPLETED' ? 'primary' : t.status === 'DEFERRED' ? 'warning' : 'default'}>{t.status}</Badge>
                  <Badge variant="default">{t.task_type}</Badge>
                </div>
                <h3 className="font-semibold text-slate-900">{t.title}</h3>
                {t.description && <p className="text-sm text-muted mt-1">{t.description}</p>}
                <p className="text-xs text-muted mt-1">
                  {t.assigned_to_user_id ? `User #${t.assigned_to_user_id}` : 'Store Task'}
                  {t.due_at ? ` - Due ${formatDateTime(t.due_at)}` : ''}
                </p>
              </div>
              {t.status === 'PENDING' && (
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" onClick={() => updateTaskStatus(t.id, 'COMPLETED')}>Complete</Button>
                  <Button size="sm" variant="secondary" onClick={() => updateTaskStatus(t.id, 'DEFERRED')}>Defer</Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="New Notification">
        <div className="space-y-4 p-1">
          <Select
            label="Type"
            value={formType}
            onChange={(e) => setFormType(e.target.value as 'ANNOUNCEMENT' | 'REMINDER')}
            options={[
              { label: 'Announcement', value: 'ANNOUNCEMENT' },
              { label: 'Reminder', value: 'REMINDER' },
            ]}
          />
          <Input label="Title" value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Body</label>
            <textarea
              className="w-full rounded-xl border border-border px-3 py-2 text-sm min-h-[80px]"
              value={formBody}
              onChange={(e) => setFormBody(e.target.value)}
            />
          </div>
          {formType === 'ANNOUNCEMENT' && (
            <Select
              label="Priority"
              value={formPriority}
              onChange={(e) => setFormPriority(e.target.value)}
              options={[
                { label: 'Low', value: 'LOW' },
                { label: 'Normal', value: 'NORMAL' },
                { label: 'High', value: 'HIGH' },
                { label: 'Urgent', value: 'URGENT' },
              ]}
            />
          )}
          <div className="space-y-2">
            <Input label="Recipient" value={recipientSearch} onChange={(e) => setRecipientSearch(e.target.value)} placeholder="Search: all managers, cashier, user, store..." />
            <div className="rounded-xl border border-border bg-white max-h-48 overflow-auto">
              {recipientOptions.length === 0 ? (
                <div className="px-3 py-2 text-sm text-muted">No recipients match search</div>
              ) : (
                recipientOptions.map((opt) => {
                  const isSelected = selectedRecipients.includes(opt.value);
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${isSelected ? 'bg-slate-100 text-slate-500' : 'text-slate-700'}`}
                      onClick={() => {
                        addRecipient(opt.value);
                        setRecipientSearch('');
                      }}
                    >
                      {opt.label}
                    </button>
                  );
                })
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedRecipientLabels.map((r) => (
                <div key={r.value} className="inline-flex items-center gap-2 px-2.5 h-8 rounded-lg border border-border bg-slate-50 text-xs text-slate-700">
                  <span>{r.label}</span>
                  <button type="button" onClick={() => setSelectedRecipients((prev) => prev.filter((x) => x !== r.value))} className="text-slate-500 hover:text-slate-700">
                    x
                  </button>
                </div>
              ))}
            </div>
            {selectedRecipients.length === 0 && <p className="text-xs text-amber-700">Select at least one recipient.</p>}
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={formActive} onChange={(e) => setFormActive(e.target.checked)} />
            Active
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={createNotification} disabled={selectedRecipients.length === 0}>Create</Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={showCreateTask} onClose={() => setShowCreateTask(false)} title="New Task">
        <div className="space-y-4 p-1">
          <Input label="Title" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea
              className="w-full rounded-xl border border-border px-3 py-2 text-sm min-h-[80px]"
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
            />
          </div>
          <Select
            label="Assign To User (optional)"
            value={taskAssignee}
            onChange={(e) => setTaskAssignee(e.target.value)}
            options={[{ label: 'Store Task (any user)', value: '' }, ...users.map((u) => ({ label: formatUserLabel(u.username), value: String(u.id) }))]}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowCreateTask(false)}>Cancel</Button>
            <Button onClick={createTask}>Create Task</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

