# GuardPro Webhooks

## Overview

GuardPro webhooks provide real-time notifications for various events in the security management system. Webhooks allow external systems to receive instant updates when specific events occur, enabling seamless integration and automated workflows.

## Webhook Concepts

### What are Webhooks?

Webhooks are HTTP callbacks that GuardPro sends to your application when specific events occur. Instead of polling the API for changes, your application receives real-time notifications, making integrations more efficient and responsive.

### How Webhooks Work

1. **Event Occurs**: An event happens in GuardPro (e.g., guard creates a shift)
2. **Webhook Triggered**: GuardPro identifies the event and triggers configured webhooks
3. **HTTP Request Sent**: GuardPro sends an HTTP POST request to your webhook URL
4. **Your App Responds**: Your application receives the webhook and processes the event
5. **Confirmation**: Your application responds with HTTP 200 to confirm receipt

## Webhook Events

### Guard Events

#### `guard.created`
Triggered when a new guard is created.

**Payload:**
```json
{
    "event": "guard.created",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "id": 1,
        "name": "John Doe",
        "employee_id": "EMP001",
        "email": "john.doe@company.com",
        "phone": "+1234567890",
        "status": "active",
        "hire_date": "2024-01-15",
        "site": {
            "id": 1,
            "name": "Main Office"
        }
    }
}
```

#### `guard.updated`
Triggered when guard information is updated.

**Payload:**
```json
{
    "event": "guard.updated",
    "timestamp": "2024-01-15T11:00:00Z",
    "data": {
        "id": 1,
        "name": "John Doe Updated",
        "employee_id": "EMP001",
        "email": "john.doe@company.com",
        "phone": "+1234567890",
        "status": "active",
        "changes": {
            "name": {
                "old": "John Doe",
                "new": "John Doe Updated"
            },
            "performance_score": {
                "old": 85.5,
                "new": 90.0
            }
        }
    }
}
```

#### `guard.status_changed`
Triggered when guard status changes.

**Payload:**
```json
{
    "event": "guard.status_changed",
    "timestamp": "2024-01-15T12:00:00Z",
    "data": {
        "id": 1,
        "name": "John Doe",
        "employee_id": "EMP001",
        "status": {
            "old": "active",
            "new": "suspended"
        },
        "reason": "Performance issues",
        "changed_by": {
            "id": 2,
            "name": "Manager Name"
        }
    }
}
```

### Shift Events

#### `shift.created`
Triggered when a new shift is created.

**Payload:**
```json
{
    "event": "shift.created",
    "timestamp": "2024-01-15T09:00:00Z",
    "data": {
        "id": 1,
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "site": {
            "id": 1,
            "name": "Main Office",
            "address": "123 Main St, City, State 12345"
        },
        "scheduled_date": "2024-01-16",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "status": "scheduled",
        "shift_type": "day",
        "notes": "Regular security shift"
    }
}
```

#### `shift.started`
Triggered when a shift is started.

**Payload:**
```json
{
    "event": "shift.started",
    "timestamp": "2024-01-16T08:05:00Z",
    "data": {
        "id": 1,
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "scheduled_date": "2024-01-16",
        "scheduled_start_time": "08:00:00",
        "actual_start_time": "08:05:00",
        "status": "in_progress",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    }
}
```

#### `shift.completed`
Triggered when a shift is completed.

**Payload:**
```json
{
    "event": "shift.completed",
    "timestamp": "2024-01-16T15:55:00Z",
    "data": {
        "id": 1,
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "scheduled_date": "2024-01-16",
        "scheduled_end_time": "16:00:00",
        "actual_end_time": "15:55:00",
        "status": "completed",
        "duration_minutes": 470,
        "notes": "Shift completed successfully",
        "summary": {
            "tasks_completed": 5,
            "checkpoints_visited": 8,
            "incidents_reported": 0
        }
    }
}
```

#### `shift.cancelled`
Triggered when a shift is cancelled.

**Payload:**
```json
{
    "event": "shift.cancelled",
    "timestamp": "2024-01-16T07:30:00Z",
    "data": {
        "id": 1,
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "scheduled_date": "2024-01-16",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "status": "cancelled",
        "cancellation_reason": "Emergency situation",
        "cancelled_by": {
            "id": 2,
            "name": "Manager Name"
        }
    }
}
```

### Incident Events

#### `incident.created`
Triggered when a new incident is reported.

**Payload:**
```json
{
    "event": "incident.created",
    "timestamp": "2024-01-16T10:30:00Z",
    "data": {
        "id": 1,
        "incident_number": "INC-2024-001",
        "incident_type": "Security Breach",
        "severity": "high",
        "status": "open",
        "site": {
            "id": 1,
            "name": "Main Office",
            "address": "123 Main St, City, State 12345"
        },
        "reported_by": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001",
            "phone": "+1234567890"
        },
        "incident_date": "2024-01-16T10:30:00Z",
        "description": "Unauthorized person found in restricted area",
        "location": "Building A, Floor 2",
        "witnesses": [
            {
                "name": "Jane Smith",
                "contact": "+1234567892",
                "statement": "I saw the person entering the restricted area"
            }
        ]
    }
}
```

#### `incident.updated`
Triggered when an incident is updated.

**Payload:**
```json
{
    "event": "incident.updated",
    "timestamp": "2024-01-16T11:00:00Z",
    "data": {
        "id": 1,
        "incident_number": "INC-2024-001",
        "incident_type": "Security Breach",
        "severity": "high",
        "status": "in_progress",
        "changes": {
            "status": {
                "old": "open",
                "new": "in_progress"
            },
            "description": {
                "old": "Unauthorized person found in restricted area",
                "new": "Unauthorized person found in restricted area. Person has been escorted out."
            }
        },
        "updated_by": {
            "id": 2,
            "name": "Security Manager"
        }
    }
}
```

#### `incident.resolved`
Triggered when an incident is resolved.

**Payload:**
```json
{
    "event": "incident.resolved",
    "timestamp": "2024-01-16T12:00:00Z",
    "data": {
        "id": 1,
        "incident_number": "INC-2024-001",
        "incident_type": "Security Breach",
        "severity": "high",
        "status": "resolved",
        "resolution": "Person was unauthorized visitor who entered through unlocked door. Security protocols reviewed and door lock repaired.",
        "resolved_by": {
            "id": 2,
            "name": "Security Manager"
        },
        "resolution_date": "2024-01-16T12:00:00Z"
    }
}
```

### Visitor Events

#### `visitor.created`
Triggered when a new visitor request is created.

**Payload:**
```json
{
    "event": "visitor.created",
    "timestamp": "2024-01-16T09:00:00Z",
    "data": {
        "id": 1,
        "visitor_name": "John Smith",
        "company": "XYZ Corporation",
        "email": "john.smith@xyz.com",
        "phone": "+1234567890",
        "purpose": "Business Meeting",
        "host_employee": "Jane Doe",
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "visit_date": "2024-01-16",
        "expected_time": "14:00:00",
        "status": "pending",
        "notes": "Meeting with HR department",
        "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    }
}
```

#### `visitor.approved`
Triggered when a visitor request is approved.

**Payload:**
```json
{
    "event": "visitor.approved",
    "timestamp": "2024-01-16T10:00:00Z",
    "data": {
        "id": 1,
        "visitor_name": "John Smith",
        "company": "XYZ Corporation",
        "purpose": "Business Meeting",
        "host_employee": "Jane Doe",
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "visit_date": "2024-01-16",
        "expected_time": "14:00:00",
        "status": "approved",
        "approved_by": {
            "id": 2,
            "name": "Security Manager"
        },
        "approval_notes": "Approved for meeting with HR department"
    }
}
```

#### `visitor.checked_in`
Triggered when a visitor checks in.

**Payload:**
```json
{
    "event": "visitor.checked_in",
    "timestamp": "2024-01-16T14:05:00Z",
    "data": {
        "id": 1,
        "visitor_name": "John Smith",
        "company": "XYZ Corporation",
        "purpose": "Business Meeting",
        "host_employee": "Jane Doe",
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "visit_date": "2024-01-16",
        "expected_time": "14:00:00",
        "actual_checkin_time": "14:05:00",
        "status": "checked_in",
        "checked_in_by": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "checkin_notes": "Visitor arrived 5 minutes late"
    }
}
```

#### `visitor.checked_out`
Triggered when a visitor checks out.

**Payload:**
```json
{
    "event": "visitor.checked_out",
    "timestamp": "2024-01-16T16:30:00Z",
    "data": {
        "id": 1,
        "visitor_name": "John Smith",
        "company": "XYZ Corporation",
        "purpose": "Business Meeting",
        "host_employee": "Jane Doe",
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "visit_date": "2024-01-16",
        "checkin_time": "14:05:00",
        "actual_checkout_time": "16:30:00",
        "status": "completed",
        "checked_out_by": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "checkout_notes": "Meeting completed successfully"
    }
}
```

### Task Events

#### `task.created`
Triggered when a new task is created.

**Payload:**
```json
{
    "event": "task.created",
    "timestamp": "2024-01-16T08:00:00Z",
    "data": {
        "id": 1,
        "title": "Patrol Building Perimeter",
        "description": "Complete security patrol of building perimeter",
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "shift": {
            "id": 1,
            "scheduled_date": "2024-01-16"
        },
        "priority": "medium",
        "due_time": "2024-01-16T10:00:00Z",
        "status": "pending",
        "created_by": {
            "id": 2,
            "name": "Manager Name"
        }
    }
}
```

#### `task.completed`
Triggered when a task is completed.

**Payload:**
```json
{
    "event": "task.completed",
    "timestamp": "2024-01-16T09:45:00Z",
    "data": {
        "id": 1,
        "title": "Patrol Building Perimeter",
        "description": "Complete security patrol of building perimeter",
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "site": {
            "id": 1,
            "name": "Main Office"
        },
        "shift": {
            "id": 1,
            "scheduled_date": "2024-01-16"
        },
        "priority": "medium",
        "due_time": "2024-01-16T10:00:00Z",
        "actual_completion_time": "2024-01-16T09:45:00Z",
        "status": "completed",
        "completion_notes": "Patrol completed successfully. No issues found."
    }
}
```

### Site Events

#### `site.created`
Triggered when a new site is created.

**Payload:**
```json
{
    "event": "site.created",
    "timestamp": "2024-01-16T10:00:00Z",
    "data": {
        "id": 1,
        "name": "New Branch Office",
        "address": "456 Oak St, City, State 12345",
        "status": "active",
        "client": {
            "id": 1,
            "name": "ABC Corporation"
        },
        "contact_person": {
            "name": "Jane Smith",
            "email": "jane.smith@abc.com",
            "phone": "+1234567890"
        },
        "security_requirements": [
            "24/7 security coverage",
            "Access control monitoring"
        ],
        "created_by": {
            "id": 2,
            "name": "Manager Name"
        }
    }
}
```

#### `site.updated`
Triggered when site information is updated.

**Payload:**
```json
{
    "event": "site.updated",
    "timestamp": "2024-01-16T11:00:00Z",
    "data": {
        "id": 1,
        "name": "New Branch Office",
        "address": "456 Oak St, City, State 12345",
        "status": "active",
        "changes": {
            "name": {
                "old": "New Branch Office",
                "new": "Updated Branch Office"
            },
            "security_requirements": {
                "old": ["24/7 security coverage", "Access control monitoring"],
                "new": ["24/7 security coverage", "Access control monitoring", "Visitor management"]
            }
        },
        "updated_by": {
            "id": 2,
            "name": "Manager Name"
        }
    }
}
```

## Webhook Configuration

### Creating Webhooks

#### API Endpoint

```http
POST /api/guardpro/webhooks
```

#### Request Body

```json
{
    "name": "My Integration Webhook",
    "url": "https://your-domain.com/webhook/guardpro",
    "events": [
        "guard.created",
        "shift.started",
        "shift.completed",
        "incident.created",
        "visitor.checked_in",
        "visitor.checked_out"
    ],
    "secret": "your-webhook-secret",
    "active": true,
    "retry_policy": {
        "max_retries": 3,
        "retry_delay": 60
    },
    "headers": {
        "X-Custom-Header": "custom-value"
    }
}
```

#### Response

```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "My Integration Webhook",
        "url": "https://your-domain.com/webhook/guardpro",
        "events": [
            "guard.created",
            "shift.started",
            "shift.completed",
            "incident.created",
            "visitor.checked_in",
            "visitor.checked_out"
        ],
        "active": true,
        "created_at": "2024-01-16T10:00:00Z"
    },
    "message": "Webhook created successfully"
}
```

### Updating Webhooks

#### API Endpoint

```http
PUT /api/guardpro/webhooks/{webhook_id}
```

#### Request Body

```json
{
    "name": "Updated Integration Webhook",
    "events": [
        "guard.created",
        "guard.updated",
        "shift.started",
        "shift.completed",
        "incident.created",
        "incident.updated",
        "visitor.checked_in",
        "visitor.checked_out"
    ],
    "active": true
}
```

### Listing Webhooks

#### API Endpoint

```http
GET /api/guardpro/webhooks
```

#### Response

```json
{
    "success": true,
    "data": {
        "webhooks": [
            {
                "id": 1,
                "name": "My Integration Webhook",
                "url": "https://your-domain.com/webhook/guardpro",
                "events": [
                    "guard.created",
                    "shift.started",
                    "shift.completed"
                ],
                "active": true,
                "created_at": "2024-01-16T10:00:00Z",
                "last_triggered": "2024-01-16T14:05:00Z"
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 1,
            "pages": 1
        }
    }
}
```

### Deleting Webhooks

#### API Endpoint

```http
DELETE /api/guardpro/webhooks/{webhook_id}
```

#### Response

```json
{
    "success": true,
    "message": "Webhook deleted successfully"
}
```

## Webhook Security

### Signature Verification

GuardPro includes a signature header with each webhook request to verify authenticity:

```http
X-GuardPro-Signature: sha256=abc123def456...
```

#### Verification Process

1. **Extract Signature**: Get the signature from the `X-GuardPro-Signature` header
2. **Calculate Expected Signature**: Use HMAC-SHA256 with your webhook secret
3. **Compare Signatures**: Use constant-time comparison to prevent timing attacks

#### Example Implementation

```python
import hmac
import hashlib
import base64

def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature"""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    # Use constant-time comparison
    return hmac.compare_digest(expected_signature, signature)

# Usage
payload = request.get_data(as_text=True)
signature = request.headers.get('X-GuardPro-Signature')
secret = 'your-webhook-secret'

if verify_webhook_signature(payload, signature, secret):
    # Process webhook
    pass
else:
    # Reject webhook
    return 'Unauthorized', 401
```

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
    const expectedSignature = crypto
        .createHmac('sha256', secret)
        .update(payload, 'utf8')
        .digest('hex');
    
    // Remove 'sha256=' prefix if present
    const receivedSignature = signature.startsWith('sha256=') 
        ? signature.slice(7) 
        : signature;
    
    // Use constant-time comparison
    return crypto.timingSafeEqual(
        Buffer.from(expectedSignature, 'hex'),
        Buffer.from(receivedSignature, 'hex')
    );
}

// Usage
const payload = req.body;
const signature = req.headers['x-guardpro-signature'];
const secret = 'your-webhook-secret';

if (verifyWebhookSignature(payload, signature, secret)) {
    // Process webhook
} else {
    // Reject webhook
    res.status(401).send('Unauthorized');
}
```

### IP Whitelisting

GuardPro webhook requests come from specific IP addresses. You can whitelist these IPs for additional security:

```
# GuardPro Webhook IPs
203.0.113.0/24
198.51.100.0/24
```

### HTTPS Requirement

All webhook URLs must use HTTPS to ensure secure transmission of data.

## Webhook Delivery

### Delivery Process

1. **Event Triggered**: Event occurs in GuardPro
2. **Webhook Queued**: Webhook added to delivery queue
3. **HTTP Request Sent**: POST request sent to webhook URL
4. **Response Received**: Your application responds
5. **Delivery Confirmed**: Success or failure recorded

### Response Requirements

Your webhook endpoint must respond with:

- **HTTP 200-299**: Success (webhook processed)
- **HTTP 400-499**: Client error (webhook rejected)
- **HTTP 500-599**: Server error (retry later)

### Timeout

Webhook requests timeout after 30 seconds. Your endpoint should respond within this timeframe.

### Retry Policy

Failed webhooks are retried according to the configured retry policy:

- **Default**: 3 retries with exponential backoff
- **Retry Delays**: 1 minute, 5 minutes, 15 minutes
- **Max Retries**: Configurable per webhook

### Delivery Logs

GuardPro maintains delivery logs for all webhook attempts:

```json
{
    "webhook_id": 1,
    "event": "guard.created",
    "url": "https://your-domain.com/webhook/guardpro",
    "status": "success",
    "response_code": 200,
    "response_time_ms": 150,
    "attempt": 1,
    "timestamp": "2024-01-16T10:30:00Z"
}
```

## Webhook Testing

### Test Webhook

#### API Endpoint

```http
POST /api/guardpro/webhooks/{webhook_id}/test
```

#### Request Body

```json
{
    "event": "guard.created",
    "test_data": {
        "id": 999,
        "name": "Test Guard",
        "employee_id": "TEST001",
        "email": "test@example.com",
        "status": "active"
    }
}
```

#### Response

```json
{
    "success": true,
    "data": {
        "webhook_id": 1,
        "test_event": "guard.created",
        "delivery_status": "success",
        "response_code": 200,
        "response_time_ms": 120,
        "timestamp": "2024-01-16T10:30:00Z"
    },
    "message": "Test webhook sent successfully"
}
```

### Webhook Logs

#### API Endpoint

```http
GET /api/guardpro/webhooks/{webhook_id}/logs
```

#### Query Parameters

- `page` (optional): Page number
- `limit` (optional): Records per page
- `status` (optional): Filter by status (success, failed, pending)
- `date_from` (optional): Start date filter
- `date_to` (optional): End date filter

#### Response

```json
{
    "success": true,
    "data": {
        "logs": [
            {
                "id": 1,
                "webhook_id": 1,
                "event": "guard.created",
                "url": "https://your-domain.com/webhook/guardpro",
                "status": "success",
                "response_code": 200,
                "response_time_ms": 150,
                "attempt": 1,
                "timestamp": "2024-01-16T10:30:00Z",
                "error_message": null
            },
            {
                "id": 2,
                "webhook_id": 1,
                "event": "shift.started",
                "url": "https://your-domain.com/webhook/guardpro",
                "status": "failed",
                "response_code": 500,
                "response_time_ms": 30000,
                "attempt": 3,
                "timestamp": "2024-01-16T11:00:00Z",
                "error_message": "Connection timeout"
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 50,
            "pages": 3
        }
    }
}
```

## Webhook Implementation Examples

### Python Flask Example

```python
from flask import Flask, request, jsonify
import hmac
import hashlib
import json

app = Flask(__name__)

# Webhook secret
WEBHOOK_SECRET = 'your-webhook-secret'

def verify_signature(payload, signature):
    """Verify webhook signature"""
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    return hmac.compare_digest(expected_signature, signature)

@app.route('/webhook/guardpro', methods=['POST'])
def handle_webhook():
    """Handle GuardPro webhook"""
    # Get payload and signature
    payload = request.get_data(as_text=True)
    signature = request.headers.get('X-GuardPro-Signature')
    
    # Verify signature
    if not verify_signature(payload, signature):
        return 'Unauthorized', 401
    
    # Parse payload
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return 'Invalid JSON', 400
    
    # Process webhook based on event type
    event = data.get('event')
    
    if event == 'guard.created':
        handle_guard_created(data['data'])
    elif event == 'shift.started':
        handle_shift_started(data['data'])
    elif event == 'shift.completed':
        handle_shift_completed(data['data'])
    elif event == 'incident.created':
        handle_incident_created(data['data'])
    elif event == 'visitor.checked_in':
        handle_visitor_checked_in(data['data'])
    elif event == 'visitor.checked_out':
        handle_visitor_checked_out(data['data'])
    else:
        print(f"Unknown event: {event}")
    
    return 'OK', 200

def handle_guard_created(data):
    """Handle guard created event"""
    print(f"New guard created: {data['name']} ({data['employee_id']})")
    # Add your logic here
    # e.g., sync with HR system, send welcome email, etc.

def handle_shift_started(data):
    """Handle shift started event"""
    print(f"Shift started: {data['guard']['name']} at {data['site']['name']}")
    # Add your logic here
    # e.g., update time tracking system, send notifications, etc.

def handle_shift_completed(data):
    """Handle shift completed event"""
    print(f"Shift completed: {data['guard']['name']} at {data['site']['name']}")
    # Add your logic here
    # e.g., update payroll system, generate reports, etc.

def handle_incident_created(data):
    """Handle incident created event"""
    print(f"New incident: {data['incident_number']} - {data['incident_type']}")
    # Add your logic here
    # e.g., send alerts, update incident tracking system, etc.

def handle_visitor_checked_in(data):
    """Handle visitor checked in event"""
    print(f"Visitor checked in: {data['visitor_name']} from {data['company']}")
    # Add your logic here
    # e.g., update visitor management system, send notifications, etc.

def handle_visitor_checked_out(data):
    """Handle visitor checked out event"""
    print(f"Visitor checked out: {data['visitor_name']} from {data['company']}")
    # Add your logic here
    # e.g., update visitor management system, generate reports, etc.

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
```

### Node.js Express Example

```javascript
const express = require('express');
const crypto = require('crypto');
const app = express();

// Webhook secret
const WEBHOOK_SECRET = 'your-webhook-secret';

// Middleware to parse JSON
app.use(express.json());

function verifySignature(payload, signature) {
    const expectedSignature = crypto
        .createHmac('sha256', WEBHOOK_SECRET)
        .update(payload, 'utf8')
        .digest('hex');
    
    const receivedSignature = signature.startsWith('sha256=') 
        ? signature.slice(7) 
        : signature;
    
    return crypto.timingSafeEqual(
        Buffer.from(expectedSignature, 'hex'),
        Buffer.from(receivedSignature, 'hex')
    );
}

app.post('/webhook/guardpro', (req, res) => {
    const payload = JSON.stringify(req.body);
    const signature = req.headers['x-guardpro-signature'];
    
    // Verify signature
    if (!verifySignature(payload, signature)) {
        return res.status(401).send('Unauthorized');
    }
    
    const { event, data } = req.body;
    
    // Process webhook based on event type
    switch (event) {
        case 'guard.created':
            handleGuardCreated(data);
            break;
        case 'shift.started':
            handleShiftStarted(data);
            break;
        case 'shift.completed':
            handleShiftCompleted(data);
            break;
        case 'incident.created':
            handleIncidentCreated(data);
            break;
        case 'visitor.checked_in':
            handleVisitorCheckedIn(data);
            break;
        case 'visitor.checked_out':
            handleVisitorCheckedOut(data);
            break;
        default:
            console.log(`Unknown event: ${event}`);
    }
    
    res.status(200).send('OK');
});

function handleGuardCreated(data) {
    console.log(`New guard created: ${data.name} (${data.employee_id})`);
    // Add your logic here
}

function handleShiftStarted(data) {
    console.log(`Shift started: ${data.guard.name} at ${data.site.name}`);
    // Add your logic here
}

function handleShiftCompleted(data) {
    console.log(`Shift completed: ${data.guard.name} at ${data.site.name}`);
    // Add your logic here
}

function handleIncidentCreated(data) {
    console.log(`New incident: ${data.incident_number} - ${data.incident_type}`);
    // Add your logic here
}

function handleVisitorCheckedIn(data) {
    console.log(`Visitor checked in: ${data.visitor_name} from ${data.company}`);
    // Add your logic here
}

function handleVisitorCheckedOut(data) {
    console.log(`Visitor checked out: ${data.visitor_name} from ${data.company}`);
    // Add your logic here
}

app.listen(3000, () => {
    console.log('Webhook server running on port 3000');
});
```

### PHP Example

```php
<?php
// webhook.php

$webhook_secret = 'your-webhook-secret';

function verifySignature($payload, $signature, $secret) {
    $expected_signature = hash_hmac('sha256', $payload, $secret);
    
    if (strpos($signature, 'sha256=') === 0) {
        $signature = substr($signature, 7);
    }
    
    return hash_equals($expected_signature, $signature);
}

// Get payload and signature
$payload = file_get_contents('php://input');
$signature = $_SERVER['HTTP_X_GUARDPRO_SIGNATURE'] ?? '';

// Verify signature
if (!verifySignature($payload, $signature, $webhook_secret)) {
    http_response_code(401);
    echo 'Unauthorized';
    exit;
}

// Parse payload
$data = json_decode($payload, true);

if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(400);
    echo 'Invalid JSON';
    exit;
}

// Process webhook based on event type
$event = $data['event'] ?? '';
$eventData = $data['data'] ?? [];

switch ($event) {
    case 'guard.created':
        handleGuardCreated($eventData);
        break;
    case 'shift.started':
        handleShiftStarted($eventData);
        break;
    case 'shift.completed':
        handleShiftCompleted($eventData);
        break;
    case 'incident.created':
        handleIncidentCreated($eventData);
        break;
    case 'visitor.checked_in':
        handleVisitorCheckedIn($eventData);
        break;
    case 'visitor.checked_out':
        handleVisitorCheckedOut($eventData);
        break;
    default:
        error_log("Unknown event: $event");
}

function handleGuardCreated($data) {
    error_log("New guard created: {$data['name']} ({$data['employee_id']})");
    // Add your logic here
}

function handleShiftStarted($data) {
    error_log("Shift started: {$data['guard']['name']} at {$data['site']['name']}");
    // Add your logic here
}

function handleShiftCompleted($data) {
    error_log("Shift completed: {$data['guard']['name']} at {$data['site']['name']}");
    // Add your logic here
}

function handleIncidentCreated($data) {
    error_log("New incident: {$data['incident_number']} - {$data['incident_type']}");
    // Add your logic here
}

function handleVisitorCheckedIn($data) {
    error_log("Visitor checked in: {$data['visitor_name']} from {$data['company']}");
    // Add your logic here
}

function handleVisitorCheckedOut($data) {
    error_log("Visitor checked out: {$data['visitor_name']} from {$data['company']}");
    // Add your logic here
}

// Respond with success
http_response_code(200);
echo 'OK';
?>
```

## Best Practices

### Webhook Implementation

1. **Idempotency**: Make your webhook handlers idempotent to handle duplicate deliveries
2. **Async Processing**: Process webhooks asynchronously to respond quickly
3. **Error Handling**: Implement proper error handling and logging
4. **Security**: Always verify webhook signatures
5. **HTTPS**: Use HTTPS for all webhook endpoints

### Performance

1. **Quick Response**: Respond to webhooks within 30 seconds
2. **Async Processing**: Use background jobs for heavy processing
3. **Monitoring**: Monitor webhook delivery and performance
4. **Scaling**: Design your webhook endpoint to handle high volume

### Reliability

1. **Retry Logic**: Implement retry logic for failed webhook processing
2. **Dead Letter Queue**: Use dead letter queues for failed webhooks
3. **Monitoring**: Set up monitoring and alerting for webhook failures
4. **Testing**: Test webhook endpoints thoroughly

---

*GuardPro Webhooks: Real-time Integration and Automation*