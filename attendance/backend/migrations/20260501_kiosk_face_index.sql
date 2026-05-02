CREATE INDEX IF NOT EXISTS idx_employees_site_face_enrolled
ON employees (site_id)
WHERE face_descriptor IS NOT NULL
  AND COALESCE(face_auth_enabled, TRUE) = TRUE
  AND (is_active = TRUE OR is_active IS NULL);
