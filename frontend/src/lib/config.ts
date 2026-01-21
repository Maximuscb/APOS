// Overview: Centralized configuration for branding, navigation copy, and UI flags.

export type NavItem = {
  id: string;
  label: string;
  permissions?: string[];
};

export type PageCopy = {
  title: string;
  description: string;
};

export const appConfig = {
  appName: "APOS",
  brand: {
    mark: "APOS",
    subtitle: "Operations Suite",
    iconStyle: "rounded-square",
    iconHref: "/vite.svg",
  },
  headerCopy: {
    operationsEyebrow: "Operations",
    registerEyebrow: "Register Mode",
  },
  navItems: [
    { id: "overview", label: "Overview" },
    {
      id: "inventory",
      label: "Inventory",
      permissions: ["VIEW_INVENTORY", "RECEIVE_INVENTORY", "ADJUST_INVENTORY", "MANAGE_PRODUCTS"],
    },
    { id: "registers", label: "Registers", permissions: ["MANAGE_REGISTER", "CREATE_REGISTER"] },
    { id: "devices", label: "Devices", permissions: ["MANAGE_REGISTER"] },
    { id: "payments", label: "Payments", permissions: ["REFUND_PAYMENT", "VIEW_SALES_REPORTS"] },
    {
      id: "operations",
      label: "Operations",
      permissions: ["PROCESS_RETURN", "CREATE_TRANSFERS", "CREATE_COUNTS", "APPROVE_DOCUMENTS"],
    },
    { id: "documents", label: "Documents", permissions: ["VIEW_DOCUMENTS"] },
    { id: "analytics", label: "Analytics", permissions: ["VIEW_ANALYTICS"] },
    { id: "imports", label: "Imports", permissions: ["CREATE_IMPORTS"] },
    { id: "timekeeping", label: "Timekeeping", permissions: ["VIEW_TIMEKEEPING", "MANAGE_TIMEKEEPING"] },
    { id: "audits", label: "Audits", permissions: ["VIEW_AUDIT_LOG"] },
    { id: "users", label: "Users", permissions: ["VIEW_USERS", "CREATE_USER", "EDIT_USER"] },
    { id: "overrides", label: "Overrides", permissions: ["MANAGE_PERMISSIONS"] },
    { id: "auth", label: "Authentication" },
  ] satisfies NavItem[],
  pageCopy: {
    overview: {
      title: "Operations Suite",
      description: "Administrative oversight, documents, and inventory control.",
    },
    inventory: {
      title: "Inventory Control",
      description: "Manage products, receipts, adjustments, and ledger activity.",
    },
    registers: {
      title: "Register Status",
      description: "View register status, session history, and drawer events.",
    },
    devices: {
      title: "Device Management",
      description: "Manage registers, cash drawers, and receipt printers.",
    },
    payments: {
      title: "Payments Hub",
      description: "Collect tender, review balances, and handle voids.",
    },
    operations: {
      title: "Operational Documents",
      description: "Manage returns, transfers, and counts with audit-grade controls.",
    },
    documents: {
      title: "Documents Index",
      description: "Search and export posted documents across the store.",
    },
    analytics: {
      title: "Analytics",
      description: "Sales trends, inventory valuation, margin, and performance.",
    },
    imports: {
      title: "Imports",
      description: "Stage, map, and post data imports.",
    },
    timekeeping: {
      title: "Timekeeping",
      description: "Review time entries and approve corrections.",
    },
    audits: {
      title: "Audit Logs",
      description: "Review payment transactions and cash drawer events.",
    },
    auth: {
      title: "Authentication",
      description: "Manage users, sessions, and permissions entry points.",
    },
    users: {
      title: "User Management",
      description: "View users, assign roles, and manage account status.",
    },
    overrides: {
      title: "Permission Overrides",
      description: "Grant or deny permissions per user.",
    },
  } satisfies Record<string, PageCopy>,
  registerTabs: [
    { id: "sales", label: "Sales" },
    { id: "payments", label: "Payments" },
    { id: "time", label: "Timekeeping" },
  ],
  features: {
    showSystemHealth: true,
    showFullscreenBanner: true,
    showOperationsFab: true,
  },
};
