#!/bin/bash
# Verify Email Configuration Endpoints
echo "Verifying Email Configuration Endpoints..."

# 1. GET /email-config
echo "1. GET /email-config"
curl -s -X GET http://localhost:8000/email-config | grep "smtp.sendgrid.net" > /dev/null
if [ $? -eq 0 ]; then
  echo "GET /email-config: SUCCESS"
else
  echo "GET /email-config: FAILED"
fi

# 2. POST /email-config (Save)
echo "2. POST /email-config"
curl -s -X POST http://localhost:8000/email-config \
  -H "Content-Type: application/json" \
  -d '{"smtp_server": "smtp.example.com", "smtp_port": 587, "username": "testuser", "password": "testpassword", "from_email": "test@example.com", "from_name": "Test Notifications", "encryption": "tls", "imap_server": "imap.example.com", "imap_port": 993, "imap_ssl": true}' \
  | grep "smtp.example.com" > /dev/null
if [ $? -eq 0 ]; then
  echo "POST /email-config: SUCCESS"
else
  echo "POST /email-config: FAILED"
fi

# 3. Test SMTP (Requires valid credentials to fully succeed, but we check if endpoint is reachable)
# We expect 400 or 500 error if connection fails, but endpoint should exist.
echo "3. Testing SMTP Endpoint Presence"
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/email-config/test \
  -H "Content-Type: application/json" \
  -d '{"target_email": "test@example.com"}' | grep -E "200|400|500" > /dev/null
if [ $? -eq 0 ]; then
   echo "POST /email-config/test: REACHABLE"
else
   echo "POST /email-config/test: UNREACHABLE"
fi

# 4. Test IMAP (Requires valid credentials to fully succeed, but we check if endpoint is reachable)
echo "4. Testing IMAP Endpoint Presence"
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/email-config/test-incoming \
  -H "Content-Type: application/json" \
  -d '{}' | grep -E "200|400|500" > /dev/null
if [ $? -eq 0 ]; then
   echo "POST /email-config/test-incoming: REACHABLE"
else
   echo "POST /email-config/test-incoming: UNREACHABLE"
fi

echo "Verification Complete."
