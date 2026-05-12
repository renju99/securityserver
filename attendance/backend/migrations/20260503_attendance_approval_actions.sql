-- Extend approval log actions for conflict resolution audit trail.
ALTER TABLE attendance_approval_logs DROP CONSTRAINT IF EXISTS attendance_approval_logs_action_check;
ALTER TABLE attendance_approval_logs
    ADD CONSTRAINT attendance_approval_logs_action_check
    CHECK (action IN ('submitted', 'approved', 'rejected', 'merged', 'split', 'void_duplicate'));
