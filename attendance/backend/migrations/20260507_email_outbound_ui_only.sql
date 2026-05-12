-- Outbound app email is configured per org (HR → Email settings), not server env.
UPDATE settings
SET value = jsonb_set(value, '{outboundMode}', '"none"'::jsonb, true)
WHERE key = 'email_messaging'
  AND (value->>'outboundMode' IS NULL OR value->>'outboundMode' = 'env');
