-- Vendor-specific integration settings (push URLs, ADMS paths, API ports, UAE timezone defaults, etc.)
ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS ip_address VARCHAR(128);
ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS port VARCHAR(32);
ALTER TABLE biometric_devices ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb;
