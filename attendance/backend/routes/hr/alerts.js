const { z } = require('zod');

const resolveAlertSchema = z.object({
    falsePositive: z.boolean().optional(),
});

module.exports = ({ router, pool, authenticateToken, authorizeRole, normalizeFilterDateToUtcIso, metrics }) => {
    // HR API: Get Alerts (paginated, filterable)
    router.get('/hr/alerts', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { staffId, siteId: filterSiteId, status, startDate, endDate, page = 1, limit = 50 } = req.query;
        const offset = (parseInt(page) - 1) * parseInt(limit);
        try {
            const conditions = [];
            const params = [];
            let idx = 1;

            // Site Supervisor: locked to their own site via employee's site
            if (req.user.role === 'Site Supervisor') {
                conditions.push(`e.site_id = $${idx++}`);
                params.push(req.user.siteId);
            } else if (filterSiteId) {
                conditions.push(`a.site_id = $${idx++}`);
                params.push(filterSiteId);
            }

            if (staffId) {
                conditions.push(`e.staff_id ILIKE $${idx++}`);
                params.push(`%${staffId}%`);
            }

            if (status) {
                conditions.push(`a.status = $${idx++}`);
                params.push(status);
            }

            const normalizedStartDate = normalizeFilterDateToUtcIso(startDate, false);
            const normalizedEndDate = normalizeFilterDateToUtcIso(endDate, true);

            if (normalizedStartDate) {
                conditions.push(`a.created_at >= $${idx++}`);
                params.push(normalizedStartDate);
            }

            if (normalizedEndDate) {
                conditions.push(`a.created_at <= $${idx++}`);
                params.push(normalizedEndDate);
            }

            const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';

            const query = `
            SELECT a.*, e.staff_id, e.first_name, e.last_name, s.name as site_name
            FROM geo_fence_alerts a
            JOIN employees e ON a.employee_id = e.id
            LEFT JOIN sites s ON a.site_id = s.id
            ${where}
            ORDER BY a.created_at DESC
            LIMIT $${idx++} OFFSET $${idx++}
        `;
            params.push(parseInt(limit), offset);

            const countQuery = `
            SELECT COUNT(*) FROM geo_fence_alerts a
            JOIN employees e ON a.employee_id = e.id
            LEFT JOIN sites s ON a.site_id = s.id
            ${where}
        `;
            const countParams = params.slice(0, -2); // exclude limit/offset

            const [result, countRes] = await Promise.all([
                pool.query(query, params),
                pool.query(countQuery, countParams)
            ]);

            res.json({
                alerts: result.rows,
                total: parseInt(countRes.rows[0].count),
                page: parseInt(page),
                totalPages: Math.ceil(parseInt(countRes.rows[0].count) / parseInt(limit))
            });
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Resolve a geo-fence alert
    router.patch('/hr/alerts/:id/resolve', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { id } = req.params;
        const parsed = resolveAlertSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid resolve payload' });
        }
        try {
            const result = await pool.query(
                `UPDATE geo_fence_alerts
                 SET status = 'resolved',
                     false_positive = COALESCE($2, false_positive)
                 WHERE id = $1
                 RETURNING *`,
                [id, parsed.data.falsePositive]
            );
            if (result.rows.length === 0) return res.status(404).json({ error: 'Alert not found' });
            if (parsed.data.falsePositive) {
                metrics?.increment?.('geofence_false_positives_total', 1);
            }
            res.json(result.rows[0]);
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    // HR API: Bulk resolve geo-fence alerts
    router.patch('/hr/alerts/bulk-resolve', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
        const { ids, falsePositive } = req.body;
        if (!ids || !Array.isArray(ids) || ids.length === 0) {
            return res.status(400).json({ error: 'Provide an array of alert IDs' });
        }
        try {
            const result = await pool.query(
                `UPDATE geo_fence_alerts
                 SET status = 'resolved',
                     false_positive = CASE WHEN $2::boolean THEN true ELSE false_positive END
                 WHERE id = ANY($1)
                 RETURNING *`,
                [ids, !!falsePositive]
            );
            if (falsePositive) {
                metrics?.increment?.('geofence_false_positives_total', result.rowCount || 0);
            }
            res.json({ message: `${result.rowCount} alert(s) resolved`, resolved: result.rows });
        } catch (err) {
            console.error('Bulk resolve error:', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
