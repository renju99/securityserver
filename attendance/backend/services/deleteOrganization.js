/**
 * Hard-delete one organization and all tenant-scoped rows (transaction caller supplies `client`).
 * Caller must BEGIN/COMMIT/ROLLBACK. Throws if org is missing or slug is `default`.
 *
 * @param {import('pg').PoolClient} client
 * @param {number} orgId
 */
async function deleteOrganizationById(client, orgId) {
    const org = await client.query('SELECT id, slug, name FROM organizations WHERE id = $1', [orgId]);
    if (!org.rows[0]) {
        const e = new Error('Organization not found');
        e.statusCode = 404;
        throw e;
    }
    if (org.rows[0].slug === 'default') {
        const e = new Error('The default organization cannot be deleted');
        e.statusCode = 400;
        throw e;
    }

    const empRes = await client.query('SELECT id FROM employees WHERE organization_id = $1', [orgId]);
    const empIds = empRes.rows.map((r) => r.id);
    const siteRes = await client.query('SELECT id FROM sites WHERE organization_id = $1', [orgId]);
    const siteIds = siteRes.rows.map((r) => r.id);
    const shiftRes = await client.query('SELECT id FROM shifts WHERE organization_id = $1', [orgId]);
    const shiftIds = shiftRes.rows.map((r) => r.id);

    await client.query('DELETE FROM scheduled_report_export_templates WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM scheduled_report_export_audit WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM scheduled_report_exports WHERE organization_id = $1', [orgId]);

    if (empIds.length) {
        await client.query(
            `DELETE FROM attendance_sync_outbox
             WHERE attendance_id IN (SELECT id FROM attendance WHERE employee_id = ANY($1::int[]))`,
            [empIds]
        );
        await client.query(
            `DELETE FROM attendance_sync_mapping
             WHERE attendance_id IN (SELECT id FROM attendance WHERE employee_id = ANY($1::int[]))
                OR organization_id = $2`,
            [empIds, orgId]
        );
        await client.query(
            `DELETE FROM attendance_approval_logs
             WHERE attendance_id IN (SELECT id FROM attendance WHERE employee_id = ANY($1::int[]))`,
            [empIds]
        );
        await client.query('DELETE FROM attendance WHERE employee_id = ANY($1::int[])', [empIds]);
        await client.query(
            'DELETE FROM face_auth_events WHERE employee_id = ANY($1::int[]) OR actor_id = ANY($1::int[])',
            [empIds]
        );
        await client.query('DELETE FROM live_logs WHERE employee_id = ANY($1::int[])', [empIds]);
    } else {
        await client.query('DELETE FROM attendance_sync_mapping WHERE organization_id = $1', [orgId]);
    }

    if (empIds.length) {
        await client.query('DELETE FROM geo_fence_alerts WHERE employee_id = ANY($1::int[])', [empIds]);
    }
    if (siteIds.length) {
        await client.query('DELETE FROM geo_fence_alerts WHERE site_id = ANY($1::int[])', [siteIds]);
    }

    const devRes = await client.query('SELECT id FROM biometric_devices WHERE organization_id = $1', [orgId]);
    const deviceIds = devRes.rows.map((r) => r.id);
    if (deviceIds.length) {
        await client.query('DELETE FROM biometric_logs WHERE device_id = ANY($1::int[])', [deviceIds]);
    }
    if (empIds.length) {
        await client.query('DELETE FROM biometric_logs WHERE employee_id = ANY($1::int[])', [empIds]);
    }

    if (siteIds.length || shiftIds.length) {
        await client.query(
            `DELETE FROM attendance_policy_rules
             WHERE (site_id IS NOT NULL AND site_id = ANY($1::int[]))
                OR (shift_id IS NOT NULL AND shift_id = ANY($2::int[]))`,
            [siteIds.length ? siteIds : [-1], shiftIds.length ? shiftIds : [-1]]
        );
    }

    await client.query('DELETE FROM job_codes WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM report_presets WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM roster_templates WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM public_holidays WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM kiosk_devices WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM biometric_devices WHERE organization_id = $1', [orgId]);

    await client.query('DELETE FROM staff_odoo_routing WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM odoo_instances WHERE organization_id = $1', [orgId]);

    await client.query(
        'UPDATE employees SET face_enrolled_by = NULL WHERE face_enrolled_by IN (SELECT id FROM employees WHERE organization_id = $1)',
        [orgId]
    );
    await client.query('DELETE FROM employees WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM shifts WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM sites WHERE organization_id = $1', [orgId]);
    await client.query('DELETE FROM settings WHERE organization_id = $1', [orgId]);

    await client.query('DELETE FROM organizations WHERE id = $1', [orgId]);
}

module.exports = { deleteOrganizationById };
