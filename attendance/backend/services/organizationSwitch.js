/** Roles that may use the HR / finance dashboard and switch organization context. */
const DASHBOARD_ROLES = ['HR Admin', 'Site Supervisor', 'Payroll', 'Finance'];

/**
 * Organizations where this employee has a linked dashboard account.
 * Link: same normalized email (preferred) or same staff_id when email is missing on the current record.
 *
 * @param {import('pg').Pool} pool
 * @param {number} employeeId
 */
async function listAccessibleOrganizations(pool, employeeId) {
    const r = await pool.query(
        `WITH current AS (
            SELECT e.id, e.staff_id, NULLIF(trim(lower(e.email)), '') AS norm_email
            FROM employees e
            WHERE e.id = $1
        ),
        linked_orgs AS (
            SELECT DISTINCT e2.organization_id
            FROM employees e2
            JOIN roles r ON r.id = e2.role_id
            CROSS JOIN current c
            WHERE (e2.is_active IS NULL OR e2.is_active = TRUE)
              AND r.name = ANY($2::text[])
              AND (
                  (c.norm_email IS NOT NULL AND NULLIF(trim(lower(e2.email)), '') = c.norm_email)
                  OR (c.norm_email IS NULL AND e2.staff_id = c.staff_id)
                  OR (c.norm_email IS NOT NULL AND (e2.email IS NULL OR trim(e2.email) = '') AND e2.staff_id = c.staff_id)
              )
        )
        SELECT o.id, o.slug, o.name
        FROM organizations o
        WHERE o.id IN (SELECT organization_id FROM linked_orgs)
        ORDER BY o.name ASC`,
        [employeeId, DASHBOARD_ROLES]
    );
    return r.rows;
}

/**
 * Resolve the employee row in the target org for the same operator (email / staff rules).
 *
 * @param {import('pg').Pool} pool
 * @param {number} currentEmployeeId
 * @param {number} targetOrganizationId
 */
async function resolveTargetEmployeeForOrgSwitch(pool, currentEmployeeId, targetOrganizationId) {
    const tid = Number(targetOrganizationId);
    if (!Number.isFinite(tid) || tid <= 0) return null;

    const r = await pool.query(
        `SELECT e.*, r.name AS role_name, s.name AS site_name, o.slug AS organization_slug, o.name AS organization_name
         FROM employees e
         JOIN roles r ON e.role_id = r.id
         JOIN organizations o ON e.organization_id = o.id
         LEFT JOIN sites s ON e.site_id = s.id
         CROSS JOIN (
             SELECT staff_id, NULLIF(trim(lower(email)), '') AS norm_email
             FROM employees WHERE id = $1
         ) c
         WHERE e.organization_id = $2
           AND (e.is_active IS NULL OR e.is_active = TRUE)
           AND r.name = ANY($3::text[])
           AND (
               (c.norm_email IS NOT NULL AND NULLIF(trim(lower(e.email)), '') = c.norm_email)
               OR (c.norm_email IS NULL AND e.staff_id = c.staff_id)
               OR (c.norm_email IS NOT NULL AND (e.email IS NULL OR trim(e.email) = '') AND e.staff_id = c.staff_id)
           )
         LIMIT 1`,
        [currentEmployeeId, tid, DASHBOARD_ROLES]
    );
    return r.rows[0] || null;
}

module.exports = {
    DASHBOARD_ROLES,
    listAccessibleOrganizations,
    resolveTargetEmployeeForOrgSwitch,
};
