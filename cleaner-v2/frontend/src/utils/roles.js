export const ROLE_OPTIONS = [
    { value: 'cleaner', label: 'Cleaner', description: 'Check-in at locations, complete checklists' },
    { value: 'supervisor', label: 'Supervisor', description: 'View reports and schedules, oversee cleaners' },
    { value: 'manager', label: 'Manager', description: 'Manage schedules, staff, and reports' },
    { value: 'admin', label: 'Full Admin', description: 'Full access: projects, locations, users, all settings' },
];

export const roleLabel = (role) => ROLE_OPTIONS.find(r => r.value === role)?.label || role;
