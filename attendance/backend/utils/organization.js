/** Default tenant slug when clients omit organization (single-tenant / legacy). */
const DEFAULT_ORG_SLUG = 'default';

const hrDashboardRoom = (organizationId) => {
    const id = Number(organizationId);
    if (!Number.isFinite(id) || id <= 0) return 'org:invalid:hr-dashboard';
    return `org:${id}:hr-dashboard`;
};

const hrSiteRoom = (organizationId, siteId) => {
    const oid = Number(organizationId);
    const sid = Number(siteId);
    if (!Number.isFinite(oid) || oid <= 0 || !Number.isFinite(sid) || sid <= 0) return null;
    return `org:${oid}:hr-site:${sid}`;
};

/** Resolve org id from JWT; missing field defaults to 1 for legacy tokens. */
const organizationIdFromUser = (user) => {
    const raw = user?.organizationId ?? user?.organization_id;
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) return n;
    return 1;
};

module.exports = {
    DEFAULT_ORG_SLUG,
    hrDashboardRoom,
    hrSiteRoom,
    organizationIdFromUser,
};
