# GuardLink REST API

## Overview

The GuardLink REST API provides programmatic access to all GuardLink functionality, enabling integration with third-party systems, mobile applications, and custom workflows. The API follows RESTful principles and provides comprehensive endpoints for managing guards, shifts, incidents, and other security operations.

## Authentication

### API Key Authentication

```python
# API Key Authentication Example
import requests

headers = {
    'X-API-Key': 'your-api-key-here',
    'Content-Type': 'application/json'
}

response = requests.get('https://your-domain.com/api/guardpro/guards', headers=headers)
```

### Bearer Token Authentication

```python
# Bearer Token Authentication Example
import requests

headers = {
    'Authorization': 'Bearer your-bearer-token-here',
    'Content-Type': 'application/json'
}

response = requests.get('https://your-domain.com/api/guardpro/guards', headers=headers)
```

### Session Authentication

```python
# Session Authentication Example
import requests

session = requests.Session()
session.post('https://your-domain.com/api/guardpro/auth/login', json={
    'username': 'your-username',
    'password': 'your-password'
})

response = session.get('https://your-domain.com/api/guardpro/guards')
```

## Base URL

```
https://your-domain.com/api/guardpro/
```

## Response Format

### Success Response

```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "John Doe",
        "employee_id": "EMP001",
        "status": "active"
    },
    "message": "Operation completed successfully",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Error Response

```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data",
        "details": {
            "field": "name",
            "message": "Name is required"
        }
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Endpoints

### Authentication Endpoints

#### Login

```http
POST /api/guardpro/auth/login
```

**Request Body:**
```json
{
    "username": "your-username",
    "password": "your-password"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "user": {
            "id": 1,
            "name": "John Doe",
            "email": "john.doe@company.com",
            "groups": ["guardpro.group_guardpro_admin"]
        },
        "expires_at": "2024-01-16T10:30:00Z"
    }
}
```

#### Logout

```http
POST /api/guardpro/auth/logout
```

**Response:**
```json
{
    "success": true,
    "message": "Logged out successfully"
}
```

#### Refresh Token

```http
POST /api/guardpro/auth/refresh
```

**Request Body:**
```json
{
    "refresh_token": "your-refresh-token"
}
```

### Guard Management Endpoints

#### List Guards

```http
GET /api/guardpro/guards
```

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `limit` (optional): Records per page (default: 20, max: 100)
- `search` (optional): Search term for name or employee ID
- `status` (optional): Filter by status (active, inactive, suspended)
- `site_id` (optional): Filter by site ID

**Example:**
```http
GET /api/guardpro/guards?page=1&limit=10&search=john&status=active
```

**Response:**
```json
{
    "success": true,
    "data": {
        "guards": [
            {
                "id": 1,
                "name": "John Doe",
                "employee_id": "EMP001",
                "email": "john.doe@company.com",
                "phone": "+1234567890",
                "status": "active",
                "hire_date": "2023-01-15",
                "performance_score": 85.5,
                "attendance_rate": 95.0,
                "site": {
                    "id": 1,
                    "name": "Main Office"
                }
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 10,
            "total": 25,
            "pages": 3
        }
    }
}
```

#### Get Guard Details

```http
GET /api/guardpro/guards/{guard_id}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "John Doe",
        "employee_id": "EMP001",
        "email": "john.doe@company.com",
        "phone": "+1234567890",
        "address": "123 Main St, City, State 12345",
        "status": "active",
        "hire_date": "2023-01-15",
        "performance_score": 85.5,
        "attendance_rate": 95.0,
        "emergency_contact": {
            "name": "Jane Doe",
            "relationship": "Spouse",
            "phone": "+1234567891"
        },
        "skills": [
            {
                "id": 1,
                "name": "First Aid",
                "level": "Advanced"
            }
        ],
        "certifications": [
            {
                "id": 1,
                "name": "Security Guard License",
                "issued_date": "2023-01-01",
                "expiry_date": "2024-01-01"
            }
        ]
    }
}
```

#### Create Guard

```http
POST /api/guardpro/guards
```

**Request Body:**
```json
{
    "name": "John Doe",
    "employee_id": "EMP001",
    "email": "john.doe@company.com",
    "phone": "+1234567890",
    "address": "123 Main St, City, State 12345",
    "hire_date": "2023-01-15",
    "emergency_contact": {
        "name": "Jane Doe",
        "relationship": "Spouse",
        "phone": "+1234567891"
    },
    "skills": [1, 2, 3],
    "certifications": [
        {
            "name": "Security Guard License",
            "issued_date": "2023-01-01",
            "expiry_date": "2024-01-01"
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "John Doe",
        "employee_id": "EMP001",
        "status": "active"
    },
    "message": "Guard created successfully"
}
```

#### Update Guard

```http
PUT /api/guardpro/guards/{guard_id}
```

**Request Body:**
```json
{
    "name": "John Doe Updated",
    "phone": "+1234567890",
    "performance_score": 90.0
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "John Doe Updated",
        "phone": "+1234567890",
        "performance_score": 90.0
    },
    "message": "Guard updated successfully"
}
```

#### Delete Guard

```http
DELETE /api/guardpro/guards/{guard_id}
```

**Response:**
```json
{
    "success": true,
    "message": "Guard deleted successfully"
}
```

### Shift Management Endpoints

#### List Shifts

```http
GET /api/guardpro/shifts
```

**Query Parameters:**
- `page` (optional): Page number
- `limit` (optional): Records per page
- `guard_id` (optional): Filter by guard ID
- `site_id` (optional): Filter by site ID
- `date_from` (optional): Start date filter (YYYY-MM-DD)
- `date_to` (optional): End date filter (YYYY-MM-DD)
- `status` (optional): Filter by status (scheduled, in_progress, completed, cancelled)

**Example:**
```http
GET /api/guardpro/shifts?guard_id=1&date_from=2024-01-01&date_to=2024-01-31&status=scheduled
```

**Response:**
```json
{
    "success": true,
    "data": {
        "shifts": [
            {
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
                "scheduled_date": "2024-01-15",
                "start_time": "08:00:00",
                "end_time": "16:00:00",
                "status": "scheduled",
                "shift_type": "day",
                "notes": "Regular security shift"
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

#### Get Shift Details

```http
GET /api/guardpro/shifts/{shift_id}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "guard": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001",
            "phone": "+1234567890"
        },
        "site": {
            "id": 1,
            "name": "Main Office",
            "address": "123 Main St, City, State 12345",
            "client": {
                "id": 1,
                "name": "ABC Corporation"
            }
        },
        "scheduled_date": "2024-01-15",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "actual_start_time": "08:05:00",
        "actual_end_time": "15:55:00",
        "status": "completed",
        "shift_type": "day",
        "notes": "Regular security shift",
        "tasks": [
            {
                "id": 1,
                "description": "Patrol building perimeter",
                "status": "completed",
                "completed_at": "2024-01-15T10:30:00Z"
            }
        ],
        "checkpoints": [
            {
                "id": 1,
                "name": "Main Entrance",
                "check_time": "2024-01-15T09:00:00Z",
                "status": "completed"
            }
        ]
    }
}
```

#### Create Shift

```http
POST /api/guardpro/shifts
```

**Request Body:**
```json
{
    "guard_id": 1,
    "site_id": 1,
    "scheduled_date": "2024-01-15",
    "start_time": "08:00:00",
    "end_time": "16:00:00",
    "shift_type": "day",
    "notes": "Regular security shift"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "guard_id": 1,
        "site_id": 1,
        "scheduled_date": "2024-01-15",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "status": "scheduled"
    },
    "message": "Shift created successfully"
}
```

#### Update Shift

```http
PUT /api/guardpro/shifts/{shift_id}
```

**Request Body:**
```json
{
    "start_time": "08:30:00",
    "end_time": "16:30:00",
    "notes": "Updated shift timing"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "start_time": "08:30:00",
        "end_time": "16:30:00",
        "notes": "Updated shift timing"
    },
    "message": "Shift updated successfully"
}
```

#### Start Shift

```http
POST /api/guardpro/shifts/{shift_id}/start
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "in_progress",
        "actual_start_time": "2024-01-15T08:05:00Z"
    },
    "message": "Shift started successfully"
}
```

#### End Shift

```http
POST /api/guardpro/shifts/{shift_id}/end
```

**Request Body:**
```json
{
    "notes": "Shift completed successfully"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "completed",
        "actual_end_time": "2024-01-15T15:55:00Z"
    },
    "message": "Shift ended successfully"
}
```

### Incident Management Endpoints

#### List Incidents

```http
GET /api/guardpro/incidents
```

**Query Parameters:**
- `page` (optional): Page number
- `limit` (optional): Records per page
- `guard_id` (optional): Filter by reporting guard ID
- `site_id` (optional): Filter by site ID
- `date_from` (optional): Start date filter
- `date_to` (optional): End date filter
- `severity` (optional): Filter by severity (low, medium, high, critical)
- `status` (optional): Filter by status (open, in_progress, resolved, closed)

**Example:**
```http
GET /api/guardpro/incidents?site_id=1&severity=high&status=open
```

**Response:**
```json
{
    "success": true,
    "data": {
        "incidents": [
            {
                "id": 1,
                "incident_number": "INC-2024-001",
                "incident_type": "Security Breach",
                "severity": "high",
                "status": "open",
                "site": {
                    "id": 1,
                    "name": "Main Office"
                },
                "reported_by": {
                    "id": 1,
                    "name": "John Doe",
                    "employee_id": "EMP001"
                },
                "incident_date": "2024-01-15T10:30:00Z",
                "description": "Unauthorized person found in restricted area",
                "location": "Building A, Floor 2",
                "created_at": "2024-01-15T10:35:00Z"
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 15,
            "pages": 1
        }
    }
}
```

#### Get Incident Details

```http
GET /api/guardpro/incidents/{incident_id}
```

**Response:**
```json
{
    "success": true,
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
        "incident_date": "2024-01-15T10:30:00Z",
        "description": "Unauthorized person found in restricted area",
        "location": "Building A, Floor 2",
        "witnesses": [
            {
                "name": "Jane Smith",
                "contact": "+1234567892",
                "statement": "I saw the person entering the restricted area"
            }
        ],
        "actions_taken": [
            {
                "action": "Person escorted out of building",
                "taken_by": "John Doe",
                "timestamp": "2024-01-15T10:45:00Z"
            }
        ],
        "attachments": [
            {
                "id": 1,
                "filename": "incident_photo.jpg",
                "url": "/api/guardpro/incidents/1/attachments/1"
            }
        ],
        "created_at": "2024-01-15T10:35:00Z",
        "updated_at": "2024-01-15T10:45:00Z"
    }
}
```

#### Create Incident

```http
POST /api/guardpro/incidents
```

**Request Body:**
```json
{
    "incident_type": "Security Breach",
    "severity": "high",
    "site_id": 1,
    "incident_date": "2024-01-15T10:30:00Z",
    "description": "Unauthorized person found in restricted area",
    "location": "Building A, Floor 2",
    "witnesses": [
        {
            "name": "Jane Smith",
            "contact": "+1234567892",
            "statement": "I saw the person entering the restricted area"
        }
    ],
    "actions_taken": [
        {
            "action": "Person escorted out of building",
            "taken_by": "John Doe"
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "incident_number": "INC-2024-001",
        "status": "open"
    },
    "message": "Incident created successfully"
}
```

#### Update Incident

```http
PUT /api/guardpro/incidents/{incident_id}
```

**Request Body:**
```json
{
    "status": "in_progress",
    "description": "Updated incident description",
    "actions_taken": [
        {
            "action": "Person escorted out of building",
            "taken_by": "John Doe",
            "timestamp": "2024-01-15T10:45:00Z"
        },
        {
            "action": "Security protocols reviewed",
            "taken_by": "Security Manager",
            "timestamp": "2024-01-15T11:00:00Z"
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "in_progress",
        "updated_at": "2024-01-15T11:00:00Z"
    },
    "message": "Incident updated successfully"
}
```

### Site Management Endpoints

#### List Sites

```http
GET /api/guardpro/sites
```

**Query Parameters:**
- `page` (optional): Page number
- `limit` (optional): Records per page
- `client_id` (optional): Filter by client ID
- `status` (optional): Filter by status (active, inactive)

**Response:**
```json
{
    "success": true,
    "data": {
        "sites": [
            {
                "id": 1,
                "name": "Main Office",
                "address": "123 Main St, City, State 12345",
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
                    "Access control monitoring",
                    "Incident reporting"
                ]
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 5,
            "pages": 1
        }
    }
}
```

#### Get Site Details

```http
GET /api/guardpro/sites/{site_id}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "Main Office",
        "address": "123 Main St, City, State 12345",
        "status": "active",
        "client": {
            "id": 1,
            "name": "ABC Corporation",
            "contact_email": "contact@abc.com",
            "contact_phone": "+1234567890"
        },
        "contact_person": {
            "name": "Jane Smith",
            "email": "jane.smith@abc.com",
            "phone": "+1234567890",
            "position": "Security Manager"
        },
        "security_requirements": [
            "24/7 security coverage",
            "Access control monitoring",
            "Incident reporting",
            "Visitor management"
        ],
        "access_points": [
            {
                "id": 1,
                "name": "Main Entrance",
                "type": "entrance",
                "status": "active"
            },
            {
                "id": 2,
                "name": "Emergency Exit",
                "type": "exit",
                "status": "active"
            }
        ],
        "checkpoints": [
            {
                "id": 1,
                "name": "Reception Desk",
                "location": "Ground Floor",
                "required_checks": ["ID verification", "Visitor log"]
            }
        ]
    }
}
```

### Visitor Management Endpoints

#### List Visitors

```http
GET /api/guardpro/visitors
```

**Query Parameters:**
- `page` (optional): Page number
- `limit` (optional): Records per page
- `site_id` (optional): Filter by site ID
- `date_from` (optional): Start date filter
- `date_to` (optional): End date filter
- `status` (optional): Filter by status (pending, approved, rejected, completed)

**Response:**
```json
{
    "success": true,
    "data": {
        "visitors": [
            {
                "id": 1,
                "visitor_name": "John Smith",
                "company": "XYZ Corporation",
                "purpose": "Business Meeting",
                "host_employee": "Jane Doe",
                "site": {
                    "id": 1,
                    "name": "Main Office"
                },
                "visit_date": "2024-01-15",
                "expected_time": "14:00:00",
                "status": "approved",
                "created_at": "2024-01-15T09:00:00Z"
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 25,
            "pages": 2
        }
    }
}
```

#### Create Visitor Request

```http
POST /api/guardpro/visitors
```

**Request Body:**
```json
{
    "visitor_name": "John Smith",
    "company": "XYZ Corporation",
    "email": "john.smith@xyz.com",
    "phone": "+1234567890",
    "purpose": "Business Meeting",
    "host_employee": "Jane Doe",
    "site_id": 1,
    "visit_date": "2024-01-15",
    "expected_time": "14:00:00",
    "notes": "Meeting with HR department"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "visitor_name": "John Smith",
        "status": "pending",
        "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    },
    "message": "Visitor request created successfully"
}
```

#### Approve Visitor Request

```http
POST /api/guardpro/visitors/{visitor_id}/approve
```

**Request Body:**
```json
{
    "notes": "Approved for meeting with HR department"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "approved",
        "approved_at": "2024-01-15T10:00:00Z"
    },
    "message": "Visitor request approved successfully"
}
```

#### Check-in Visitor

```http
POST /api/guardpro/visitors/{visitor_id}/checkin
```

**Request Body:**
```json
{
    "actual_time": "14:05:00",
    "notes": "Visitor arrived 5 minutes late"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "checked_in",
        "checkin_time": "2024-01-15T14:05:00Z"
    },
    "message": "Visitor checked in successfully"
}
```

#### Check-out Visitor

```http
POST /api/guardpro/visitors/{visitor_id}/checkout
```

**Request Body:**
```json
{
    "actual_time": "16:30:00",
    "notes": "Meeting completed successfully"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "completed",
        "checkout_time": "2024-01-15T16:30:00Z"
    },
    "message": "Visitor checked out successfully"
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data",
        "details": [
            {
                "field": "name",
                "message": "Name is required"
            },
            {
                "field": "email",
                "message": "Invalid email format"
            }
        ]
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes

- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_FAILED`: Invalid credentials
- `PERMISSION_DENIED`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource not found
- `DUPLICATE_RESOURCE`: Resource already exists
- `BUSINESS_LOGIC_ERROR`: Business rule violation
- `SYSTEM_ERROR`: Internal system error

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Standard Users**: 100 requests per hour
- **API Key Users**: 1000 requests per hour
- **Premium Users**: 10000 requests per hour

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642258800
```

## Pagination

All list endpoints support pagination:

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Records per page (default: 20, max: 100)

**Response Format:**
```json
{
    "data": {
        "items": [...],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 100,
            "pages": 5
        }
    }
}
```

## Filtering and Sorting

### Filtering

Use query parameters to filter results:

```http
GET /api/guardpro/guards?status=active&site_id=1&created_after=2024-01-01
```

### Sorting

Use the `sort` parameter to specify sort order:

```http
GET /api/guardpro/guards?sort=name:asc
GET /api/guardpro/guards?sort=created_at:desc
```

Multiple sort criteria:

```http
GET /api/guardpro/guards?sort=status:asc,name:asc
```

## Webhooks

### Webhook Events

GuardLink can send webhook notifications for various events:

- `guard.created`: New guard created
- `guard.updated`: Guard information updated
- `shift.created`: New shift scheduled
- `shift.started`: Shift started
- `shift.completed`: Shift completed
- `incident.created`: New incident reported
- `incident.updated`: Incident updated
- `visitor.created`: New visitor request
- `visitor.approved`: Visitor request approved
- `visitor.checked_in`: Visitor checked in
- `visitor.checked_out`: Visitor checked out

### Webhook Configuration

```http
POST /api/guardpro/webhooks
```

**Request Body:**
```json
{
    "url": "https://your-domain.com/webhook/guardpro",
    "events": ["guard.created", "shift.started", "incident.created"],
    "secret": "your-webhook-secret"
}
```

### Webhook Payload

```json
{
    "event": "guard.created",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "id": 1,
        "name": "John Doe",
        "employee_id": "EMP001",
        "status": "active"
    }
}
```

### Webhook Security

Webhooks include a signature header for verification:

```http
X-GuardLink-Signature: sha256=abc123def456...
```

## SDK Examples

### Python SDK

```python
from guardpro_api import GuardLinkClient

# Initialize client
client = GuardLinkClient(
    base_url='https://your-domain.com/api/guardpro',
    api_key='your-api-key'
)

# List guards
guards = client.guards.list(page=1, limit=10)

# Create guard
new_guard = client.guards.create({
    'name': 'John Doe',
    'employee_id': 'EMP001',
    'email': 'john.doe@company.com'
})

# Update guard
client.guards.update(1, {'performance_score': 90.0})

# Create shift
shift = client.shifts.create({
    'guard_id': 1,
    'site_id': 1,
    'scheduled_date': '2024-01-15',
    'start_time': '08:00:00',
    'end_time': '16:00:00'
})

# Start shift
client.shifts.start(shift['id'])

# End shift
client.shifts.end(shift['id'], {'notes': 'Shift completed successfully'})
```

### JavaScript SDK

```javascript
import { GuardLinkClient } from '@guardpro/api-client';

// Initialize client
const client = new GuardLinkClient({
    baseUrl: 'https://your-domain.com/api/guardpro',
    apiKey: 'your-api-key'
});

// List guards
const guards = await client.guards.list({ page: 1, limit: 10 });

// Create guard
const newGuard = await client.guards.create({
    name: 'John Doe',
    employee_id: 'EMP001',
    email: 'john.doe@company.com'
});

// Update guard
await client.guards.update(1, { performance_score: 90.0 });

// Create shift
const shift = await client.shifts.create({
    guard_id: 1,
    site_id: 1,
    scheduled_date: '2024-01-15',
    start_time: '08:00:00',
    end_time: '16:00:00'
});

// Start shift
await client.shifts.start(shift.id);

// End shift
await client.shifts.end(shift.id, { notes: 'Shift completed successfully' });
```

## Testing

### API Testing

Use tools like Postman, Insomnia, or curl to test the API:

```bash
# Test authentication
curl -X POST https://your-domain.com/api/guardpro/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your-username", "password": "your-password"}'

# Test guard listing
curl -X GET https://your-domain.com/api/guardpro/guards \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json"

# Test guard creation
curl -X POST https://your-domain.com/api/guardpro/guards \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "employee_id": "EMP001", "email": "john.doe@company.com"}'
```

### Postman Collection

Import the GuardLink API Postman collection for comprehensive testing:

1. Download the collection file
2. Import into Postman
3. Set up environment variables
4. Run tests and examples

---

*GuardLink REST API: Comprehensive Security Management Integration*
