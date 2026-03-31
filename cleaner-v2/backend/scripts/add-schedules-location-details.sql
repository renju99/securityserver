-- Add location_details to cleaning schedules. Safe if column already exists.
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS location_details TEXT;
