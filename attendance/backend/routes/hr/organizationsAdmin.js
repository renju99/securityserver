const { z } = require('zod');
const { deleteOrganizationById } = require('../../services/deleteOrganization');

const slugSchema = z
    .string()
    .trim()
    .min(2, 'Slug must be at least 2 characters')
    .max(64)
    .regex(/^[a-z0-9][a-z0-9-]*$/, 'Slug: lowercase letters, digits, or hyphen (must start with letter or digit)');

const createOrgSchema = z.object({
    slug: slugSchema,
    name: z.string().trim().min(1, 'Name is required').max(200),
});

async function seedDefaultShiftsForOrg(client, organizationId) {
    await client.query(
        `INSERT INTO shifts (organization_id, name, start_time, end_time)
         SELECT $1, v.name, v.start_time::time, v.end_time::time
         FROM (VALUES
             ('Morning Shift', '08:00', '17:00'),
             ('Night Shift', '20:00', '05:00')
         ) AS v(name, start_time, end_time)
         ON CONFLICT (organization_id, name) DO NOTHING`,
        [organizationId]
    );
}

module.exports = ({ router, pool, authenticateToken, authorizeRole }) => {
    router.get('/hr/admin/organizations', authenticateToken, authorizeRole(['HR Admin']), async (_req, res) => {
        try {
            const r = await pool.query(
                'SELECT id, slug, name, created_at FROM organizations ORDER BY LOWER(name) ASC, id ASC'
            );
            res.json({ organizations: r.rows });
        } catch (err) {
            console.error('[organizations-admin] list', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/admin/organizations', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = createOrgSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        }
        const slug = parsed.data.slug.toLowerCase();
        const name = parsed.data.name.trim();
        const client = await pool.connect();
        try {
            await client.query('BEGIN');
            const ins = await client.query(
                `INSERT INTO organizations (slug, name) VALUES ($1, $2)
                 RETURNING id, slug, name, created_at`,
                [slug, name]
            );
            const row = ins.rows[0];
            await seedDefaultShiftsForOrg(client, row.id);
            await client.query('COMMIT');
            res.status(201).json(row);
        } catch (err) {
            try {
                await client.query('ROLLBACK');
            } catch (_e) {
                /* no-op */
            }
            if (err && err.code === '23505') {
                return res.status(409).json({ error: 'An organization with this slug already exists' });
            }
            console.error('[organizations-admin] create', err);
            res.status(500).json({ error: 'Database error' });
        } finally {
            client.release();
        }
    });

    router.delete('/hr/admin/organizations/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const id = parseInt(req.params.id, 10);
        if (!Number.isFinite(id) || id < 1) {
            return res.status(400).json({ error: 'Invalid organization id' });
        }
        const client = await pool.connect();
        try {
            await client.query('BEGIN');
            await deleteOrganizationById(client, id);
            await client.query('COMMIT');
            return res.status(204).send();
        } catch (err) {
            try {
                await client.query('ROLLBACK');
            } catch (_e) {
                /* no-op */
            }
            if (err && err.statusCode) {
                return res.status(err.statusCode).json({ error: err.message });
            }
            console.error('[organizations-admin] delete', err);
            return res.status(500).json({ error: err.message || 'Database error' });
        } finally {
            client.release();
        }
    });
};
