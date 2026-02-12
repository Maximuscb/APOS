export type Permission = { code: string; name?: string; category?: string };

export const WORKSPACE_GROUPS: Record<string, { label: string; categories: string[] }> = {
  sales: {
    label: 'Sales',
    categories: ['SALES', 'REGISTERS'],
  },
  inventory: {
    label: 'Inventory',
    categories: ['INVENTORY'],
  },
  documents: {
    label: 'Documents',
    categories: ['DOCUMENTS'],
  },
  communications: {
    label: 'Communications',
    categories: ['COMMUNICATIONS', 'PROMOTIONS'],
  },
  timekeeping: {
    label: 'Timekeeping',
    categories: ['TIMEKEEPING'],
  },
  management: {
    label: 'Management',
    categories: ['USERS', 'ORGANIZATION', 'DEVICES', 'SYSTEM'],
  },
};

export const CATEGORY_LABELS: Record<string, string> = {
  SALES: 'Sales',
  REGISTERS: 'Registers',
  INVENTORY: 'Inventory',
  DOCUMENTS: 'Documents',
  COMMUNICATIONS: 'Communications',
  PROMOTIONS: 'Promotions',
  TIMEKEEPING: 'Timekeeping',
  USERS: 'Users',
  ORGANIZATION: 'Organization',
  DEVICES: 'Devices',
  SYSTEM: 'System',
};

export function groupPermissions(permissions: Permission[]) {
  const grouped: Record<string, Record<string, Permission[]>> = {};
  for (const ws of Object.keys(WORKSPACE_GROUPS)) {
    grouped[ws] = {};
    for (const cat of WORKSPACE_GROUPS[ws].categories) {
      grouped[ws][cat] = [];
    }
  }
  for (const p of permissions) {
    const cat = p.category ?? 'SYSTEM';
    for (const [ws, config] of Object.entries(WORKSPACE_GROUPS)) {
      if (config.categories.includes(cat)) {
        if (!grouped[ws][cat]) grouped[ws][cat] = [];
        grouped[ws][cat].push(p);
        break;
      }
    }
  }
  return grouped;
}
