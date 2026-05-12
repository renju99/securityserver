-- Voided rows must not remain "open" (null check_out_time) or they block check-in,
-- auto-checkout, and HR summaries. Backfill any legacy rows from before void-duplicate closed opens.
UPDATE attendance
SET check_out_time = check_in_time
WHERE status = 'voided'
  AND check_out_time IS NULL
  AND check_in_time IS NOT NULL;
