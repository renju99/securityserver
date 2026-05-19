# GuardLink Mobile API

## Overview

The GuardLink Mobile API is specifically designed for mobile applications, providing optimized endpoints and features for on-the-go security management. The API supports real-time updates, offline capabilities, and mobile-specific functionality like location tracking, photo capture, and push notifications.

## Mobile API Features

### Core Features

- **Real-time Updates**: WebSocket connections for live data synchronization
- **Offline Support**: Local data storage with sync capabilities
- **Location Services**: GPS tracking and geofencing
- **Photo Capture**: Incident and checkpoint photo uploads
- **Push Notifications**: Real-time alerts and updates
- **Biometric Authentication**: Fingerprint and face recognition support
- **QR Code Scanning**: Visitor and asset QR code scanning
- **Voice Notes**: Audio recording for incidents and reports

### Mobile-Specific Endpoints

#### Base URL

```
https://your-domain.com/api/guardpro/mobile/
```

## Authentication

### Mobile Authentication Flow

#### 1. Login with Credentials

```http
POST /api/guardpro/mobile/auth/login
```

**Request Body:**
```json
{
    "username": "guard_username",
    "password": "guard_password",
    "device_info": {
        "device_id": "unique-device-id",
        "device_type": "ios",
        "app_version": "1.0.0",
        "os_version": "15.0",
        "push_token": "device-push-token"
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "refresh-token-here",
        "user": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001",
            "role": "guard",
            "site": {
                "id": 1,
                "name": "Main Office",
                "address": "123 Main St, City, State 12345"
            }
        },
        "permissions": [
            "view_shifts",
            "start_shift",
            "end_shift",
            "report_incident",
            "check_visitors",
            "scan_qr_codes"
        ],
        "expires_at": "2024-01-16T10:30:00Z"
    }
}
```

#### 2. Biometric Authentication

```http
POST /api/guardpro/mobile/auth/biometric
```

**Request Body:**
```json
{
    "device_id": "unique-device-id",
    "biometric_data": "encrypted-biometric-hash",
    "biometric_type": "fingerprint"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "user": {
            "id": 1,
            "name": "John Doe",
            "employee_id": "EMP001"
        },
        "expires_at": "2024-01-16T10:30:00Z"
    }
}
```

#### 3. Refresh Token

```http
POST /api/guardpro/mobile/auth/refresh
```

**Request Body:**
```json
{
    "refresh_token": "refresh-token-here"
}
```

## Shift Management (Mobile)

### Get Current Shift

```http
GET /api/guardpro/mobile/shifts/current
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "site": {
            "id": 1,
            "name": "Main Office",
            "address": "123 Main St, City, State 12345",
            "coordinates": {
                "latitude": 40.7128,
                "longitude": -74.0060
            },
            "geofence": {
                "radius": 100,
                "center": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
        },
        "scheduled_date": "2024-01-16",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "status": "scheduled",
        "shift_type": "day",
        "tasks": [
            {
                "id": 1,
                "title": "Patrol Building Perimeter",
                "description": "Complete security patrol of building perimeter",
                "priority": "medium",
                "due_time": "2024-01-16T10:00:00Z",
                "status": "pending",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
        ],
        "checkpoints": [
            {
                "id": 1,
                "name": "Main Entrance",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "required_checks": ["ID verification", "Visitor log"],
                "last_check": "2024-01-16T09:00:00Z"
            }
        ]
    }
}
```

### Start Shift

```http
POST /api/guardpro/mobile/shifts/{shift_id}/start
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T08:05:00Z"
    },
    "notes": "Starting shift on time"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "in_progress",
        "actual_start_time": "2024-01-16T08:05:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    },
    "message": "Shift started successfully"
}
```

### End Shift

```http
POST /api/guardpro/mobile/shifts/{shift_id}/end
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T15:55:00Z"
    },
    "notes": "Shift completed successfully",
    "summary": {
        "tasks_completed": 5,
        "checkpoints_visited": 8,
        "incidents_reported": 0,
        "visitors_processed": 3
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "status": "completed",
        "actual_end_time": "2024-01-16T15:55:00Z",
        "duration_minutes": 470,
        "summary": {
            "tasks_completed": 5,
            "checkpoints_visited": 8,
            "incidents_reported": 0,
            "visitors_processed": 3
        }
    },
    "message": "Shift ended successfully"
}
```

### Update Location

```http
POST /api/guardpro/mobile/shifts/{shift_id}/location
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T10:30:00Z"
    },
    "activity": "patrol"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "location_updated": true,
        "timestamp": "2024-01-16T10:30:00Z"
    }
}
```

## Task Management (Mobile)

### Get Shift Tasks

```http
GET /api/guardpro/mobile/shifts/{shift_id}/tasks
```

**Response:**
```json
{
    "success": true,
    "data": {
        "tasks": [
            {
                "id": 1,
                "title": "Patrol Building Perimeter",
                "description": "Complete security patrol of building perimeter",
                "priority": "medium",
                "due_time": "2024-01-16T10:00:00Z",
                "status": "pending",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "estimated_duration": 30,
                "instructions": "Check all entry points and report any issues"
            },
            {
                "id": 2,
                "title": "Check Security Cameras",
                "description": "Verify all security cameras are functioning",
                "priority": "high",
                "due_time": "2024-01-16T11:00:00Z",
                "status": "pending",
                "location": {
                    "latitude": 40.7129,
                    "longitude": -74.0061
                },
                "estimated_duration": 15,
                "instructions": "Test each camera and report any malfunctions"
            }
        ]
    }
}
```

### Complete Task

```http
POST /api/guardpro/mobile/tasks/{task_id}/complete
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T09:45:00Z"
    },
    "notes": "Patrol completed successfully. No issues found.",
    "photos": [
        {
            "filename": "patrol_photo_1.jpg",
            "data": "base64-encoded-image-data",
            "description": "Main entrance area"
        }
    ],
    "voice_notes": [
        {
            "filename": "voice_note_1.mp3",
            "data": "base64-encoded-audio-data",
            "duration": 30
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
        "status": "completed",
        "completed_at": "2024-01-16T09:45:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "photos_uploaded": 1,
        "voice_notes_uploaded": 1
    },
    "message": "Task completed successfully"
}
```

## Checkpoint Management (Mobile)

### Get Checkpoints

```http
GET /api/guardpro/mobile/sites/{site_id}/checkpoints
```

**Response:**
```json
{
    "success": true,
    "data": {
        "checkpoints": [
            {
                "id": 1,
                "name": "Main Entrance",
                "description": "Primary entrance checkpoint",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "required_checks": [
                    {
                        "id": 1,
                        "name": "ID Verification",
                        "type": "manual",
                        "required": true
                    },
                    {
                        "id": 2,
                        "name": "Visitor Log",
                        "type": "manual",
                        "required": true
                    },
                    {
                        "id": 3,
                        "name": "Security Scan",
                        "type": "qr_scan",
                        "required": false
                    }
                ],
                "last_check": "2024-01-16T09:00:00Z",
                "status": "active"
            }
        ]
    }
}
```

### Check-in at Checkpoint

```http
POST /api/guardpro/mobile/checkpoints/{checkpoint_id}/checkin
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T10:00:00Z"
    },
    "checks": [
        {
            "check_id": 1,
            "name": "ID Verification",
            "status": "completed",
            "notes": "All IDs verified",
            "photos": [
                {
                    "filename": "id_check_1.jpg",
                    "data": "base64-encoded-image-data"
                }
            ]
        },
        {
            "check_id": 2,
            "name": "Visitor Log",
            "status": "completed",
            "notes": "Visitor log updated",
            "data": {
                "visitors_count": 5,
                "last_visitor": "John Smith"
            }
        }
    ],
    "notes": "Checkpoint check completed successfully"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "checkpoint_id": 1,
        "checkin_time": "2024-01-16T10:00:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "checks_completed": 2,
        "status": "completed"
    },
    "message": "Checkpoint check-in completed successfully"
}
```

## Incident Reporting (Mobile)

### Create Incident

```http
POST /api/guardpro/mobile/incidents
```

**Request Body:**
```json
{
    "incident_type": "Security Breach",
    "severity": "high",
    "site_id": 1,
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "address": "Building A, Floor 2"
    },
    "description": "Unauthorized person found in restricted area",
    "witnesses": [
        {
            "name": "Jane Smith",
            "contact": "+1234567892",
            "statement": "I saw the person entering the restricted area"
        }
    ],
    "photos": [
        {
            "filename": "incident_photo_1.jpg",
            "data": "base64-encoded-image-data",
            "description": "Person in restricted area"
        }
    ],
    "voice_notes": [
        {
            "filename": "incident_voice_1.mp3",
            "data": "base64-encoded-audio-data",
            "duration": 45
        }
    ],
    "actions_taken": [
        {
            "action": "Person escorted out of building",
            "timestamp": "2024-01-16T10:45:00Z"
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
        "status": "open",
        "created_at": "2024-01-16T10:30:00Z",
        "photos_uploaded": 1,
        "voice_notes_uploaded": 1
    },
    "message": "Incident reported successfully"
}
```

### Update Incident

```http
PUT /api/guardpro/mobile/incidents/{incident_id}
```

**Request Body:**
```json
{
    "status": "in_progress",
    "description": "Updated incident description",
    "actions_taken": [
        {
            "action": "Person escorted out of building",
            "timestamp": "2024-01-16T10:45:00Z"
        },
        {
            "action": "Security protocols reviewed",
            "timestamp": "2024-01-16T11:00:00Z"
        }
    ],
    "photos": [
        {
            "filename": "update_photo_1.jpg",
            "data": "base64-encoded-image-data",
            "description": "Updated situation"
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
        "updated_at": "2024-01-16T11:00:00Z",
        "photos_uploaded": 1
    },
    "message": "Incident updated successfully"
}
```

## Visitor Management (Mobile)

### Get Pending Visitors

```http
GET /api/guardpro/mobile/visitors/pending
```

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
                "visit_date": "2024-01-16",
                "expected_time": "14:00:00",
                "status": "approved",
                "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                "notes": "Meeting with HR department"
            }
        ]
    }
}
```

### Check-in Visitor

```http
POST /api/guardpro/mobile/visitors/{visitor_id}/checkin
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T14:05:00Z"
    },
    "actual_time": "14:05:00",
    "notes": "Visitor arrived 5 minutes late",
    "photos": [
        {
            "filename": "visitor_checkin_1.jpg",
            "data": "base64-encoded-image-data",
            "description": "Visitor ID verification"
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
        "status": "checked_in",
        "checkin_time": "2024-01-16T14:05:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "photos_uploaded": 1
    },
    "message": "Visitor checked in successfully"
}
```

### Check-out Visitor

```http
POST /api/guardpro/mobile/visitors/{visitor_id}/checkout
```

**Request Body:**
```json
{
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T16:30:00Z"
    },
    "actual_time": "16:30:00",
    "notes": "Meeting completed successfully",
    "photos": [
        {
            "filename": "visitor_checkout_1.jpg",
            "data": "base64-encoded-image-data",
            "description": "Visitor exit verification"
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
        "status": "completed",
        "checkout_time": "2024-01-16T16:30:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "photos_uploaded": 1
    },
    "message": "Visitor checked out successfully"
}
```

## QR Code Scanning

### Scan QR Code

```http
POST /api/guardpro/mobile/qr/scan
```

**Request Body:**
```json
{
    "qr_data": "VISITOR:12345:John Smith:XYZ Corporation",
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 5.0,
        "timestamp": "2024-01-16T14:05:00Z"
    },
    "scan_type": "visitor"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "scan_type": "visitor",
        "scan_data": {
            "visitor_id": 12345,
            "visitor_name": "John Smith",
            "company": "XYZ Corporation",
            "status": "approved",
            "expected_time": "14:00:00"
        },
        "action_required": "checkin",
        "scan_time": "2024-01-16T14:05:00Z"
    },
    "message": "QR code scanned successfully"
}
```

## Offline Support

### Sync Offline Data

```http
POST /api/guardpro/mobile/sync
```

**Request Body:**
```json
{
    "offline_data": {
        "tasks_completed": [
            {
                "task_id": 1,
                "completed_at": "2024-01-16T09:45:00Z",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "notes": "Task completed offline",
                "photos": [
                    {
                        "filename": "offline_photo_1.jpg",
                        "data": "base64-encoded-image-data"
                    }
                ]
            }
        ],
        "checkpoints_visited": [
            {
                "checkpoint_id": 1,
                "checkin_time": "2024-01-16T10:00:00Z",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "checks": [
                    {
                        "check_id": 1,
                        "status": "completed",
                        "notes": "Check completed offline"
                    }
                ]
            }
        ],
        "incidents_reported": [
            {
                "incident_type": "Security Breach",
                "severity": "medium",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "description": "Incident reported offline",
                "photos": [
                    {
                        "filename": "offline_incident_1.jpg",
                        "data": "base64-encoded-image-data"
                    }
                ]
            }
        ]
    },
    "last_sync": "2024-01-16T08:00:00Z"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "synced_items": {
            "tasks_completed": 1,
            "checkpoints_visited": 1,
            "incidents_reported": 1
        },
        "conflicts": [],
        "sync_time": "2024-01-16T16:00:00Z"
    },
    "message": "Offline data synced successfully"
}
```

### Get Offline Data

```http
GET /api/guardpro/mobile/offline/data
```

**Response:**
```json
{
    "success": true,
    "data": {
        "tasks": [
            {
                "id": 1,
                "title": "Patrol Building Perimeter",
                "description": "Complete security patrol of building perimeter",
                "priority": "medium",
                "due_time": "2024-01-16T10:00:00Z",
                "status": "pending",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
        ],
        "checkpoints": [
            {
                "id": 1,
                "name": "Main Entrance",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "required_checks": [
                    {
                        "id": 1,
                        "name": "ID Verification",
                        "type": "manual",
                        "required": true
                    }
                ]
            }
        ],
        "visitors": [
            {
                "id": 1,
                "visitor_name": "John Smith",
                "company": "XYZ Corporation",
                "purpose": "Business Meeting",
                "visit_date": "2024-01-16",
                "expected_time": "14:00:00",
                "status": "approved",
                "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
            }
        ]
    }
}
```

## Push Notifications

### Register Device

```http
POST /api/guardpro/mobile/notifications/register
```

**Request Body:**
```json
{
    "device_token": "device-push-token",
    "device_type": "ios",
    "app_version": "1.0.0",
    "os_version": "15.0",
    "notification_preferences": {
        "shift_reminders": true,
        "incident_alerts": true,
        "visitor_notifications": true,
        "task_reminders": true,
        "system_updates": false
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "device_registered": true,
        "notification_preferences": {
            "shift_reminders": true,
            "incident_alerts": true,
            "visitor_notifications": true,
            "task_reminders": true,
            "system_updates": false
        }
    },
    "message": "Device registered for notifications successfully"
}
```

### Update Notification Preferences

```http
PUT /api/guardpro/mobile/notifications/preferences
```

**Request Body:**
```json
{
    "shift_reminders": true,
    "incident_alerts": true,
    "visitor_notifications": false,
    "task_reminders": true,
    "system_updates": false
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "notification_preferences": {
            "shift_reminders": true,
            "incident_alerts": true,
            "visitor_notifications": false,
            "task_reminders": true,
            "system_updates": false
        }
    },
    "message": "Notification preferences updated successfully"
}
```

## File Upload

### Upload Photo

```http
POST /api/guardpro/mobile/upload/photo
```

**Request Body:**
```json
{
    "filename": "incident_photo_1.jpg",
    "data": "base64-encoded-image-data",
    "description": "Incident photo",
    "related_type": "incident",
    "related_id": 1,
    "metadata": {
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "timestamp": "2024-01-16T10:30:00Z",
        "camera_info": {
            "make": "Apple",
            "model": "iPhone 13",
            "resolution": "4032x3024"
        }
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "file_id": 1,
        "filename": "incident_photo_1.jpg",
        "url": "/api/guardpro/files/1",
        "size": 2048576,
        "uploaded_at": "2024-01-16T10:30:00Z"
    },
    "message": "Photo uploaded successfully"
}
```

### Upload Voice Note

```http
POST /api/guardpro/mobile/upload/voice
```

**Request Body:**
```json
{
    "filename": "voice_note_1.mp3",
    "data": "base64-encoded-audio-data",
    "description": "Incident voice note",
    "related_type": "incident",
    "related_id": 1,
    "metadata": {
        "duration": 45,
        "format": "mp3",
        "bitrate": 128,
        "sample_rate": 44100
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "file_id": 2,
        "filename": "voice_note_1.mp3",
        "url": "/api/guardpro/files/2",
        "size": 1024768,
        "duration": 45,
        "uploaded_at": "2024-01-16T10:30:00Z"
    },
    "message": "Voice note uploaded successfully"
}
```

## Real-time Updates (WebSocket)

### WebSocket Connection

```javascript
// Connect to WebSocket
const ws = new WebSocket('wss://your-domain.com/ws/guardpro/mobile');

// Authentication
ws.onopen = function() {
    ws.send(JSON.stringify({
        type: 'auth',
        token: 'your-access-token'
    }));
};

// Handle messages
ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'shift_update':
            handleShiftUpdate(message.data);
            break;
        case 'task_assigned':
            handleTaskAssigned(message.data);
            break;
        case 'incident_alert':
            handleIncidentAlert(message.data);
            break;
        case 'visitor_notification':
            handleVisitorNotification(message.data);
            break;
    }
};

// Handle shift updates
function handleShiftUpdate(data) {
    console.log('Shift updated:', data);
    // Update UI with new shift information
}

// Handle task assignments
function handleTaskAssigned(data) {
    console.log('New task assigned:', data);
    // Show task notification and update task list
}

// Handle incident alerts
function handleIncidentAlert(data) {
    console.log('Incident alert:', data);
    // Show incident notification and update incident list
}

// Handle visitor notifications
function handleVisitorNotification(data) {
    console.log('Visitor notification:', data);
    // Show visitor notification and update visitor list
}
```

### WebSocket Message Types

#### Shift Update
```json
{
    "type": "shift_update",
    "data": {
        "shift_id": 1,
        "status": "in_progress",
        "actual_start_time": "2024-01-16T08:05:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    }
}
```

#### Task Assigned
```json
{
    "type": "task_assigned",
    "data": {
        "task_id": 1,
        "title": "Patrol Building Perimeter",
        "description": "Complete security patrol of building perimeter",
        "priority": "medium",
        "due_time": "2024-01-16T10:00:00Z",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    }
}
```

#### Incident Alert
```json
{
    "type": "incident_alert",
    "data": {
        "incident_id": 1,
        "incident_number": "INC-2024-001",
        "incident_type": "Security Breach",
        "severity": "high",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060
        },
        "description": "Unauthorized person found in restricted area"
    }
}
```

#### Visitor Notification
```json
{
    "type": "visitor_notification",
    "data": {
        "visitor_id": 1,
        "visitor_name": "John Smith",
        "company": "XYZ Corporation",
        "purpose": "Business Meeting",
        "expected_time": "14:00:00",
        "status": "approved"
    }
}
```

## Error Handling

### Mobile-Specific Error Codes

- `LOCATION_REQUIRED`: Location data is required for this operation
- `GEOFENCE_VIOLATION`: Operation outside allowed geofence
- `OFFLINE_SYNC_REQUIRED`: Offline data needs to be synced
- `DEVICE_NOT_REGISTERED`: Device not registered for notifications
- `FILE_UPLOAD_FAILED`: File upload failed
- `QR_SCAN_INVALID`: Invalid QR code scanned
- `BIOMETRIC_AUTH_FAILED`: Biometric authentication failed

### Error Response Format

```json
{
    "success": false,
    "error": {
        "code": "LOCATION_REQUIRED",
        "message": "Location data is required for this operation",
        "details": {
            "field": "location",
            "message": "GPS coordinates must be provided"
        }
    },
    "timestamp": "2024-01-16T10:30:00Z"
}
```

## Mobile SDK Examples

### iOS Swift Example

```swift
import Foundation
import CoreLocation

class GuardLinkMobileAPI {
    private let baseURL = "https://your-domain.com/api/guardpro/mobile"
    private var accessToken: String?
    
    func login(username: String, password: String, deviceInfo: DeviceInfo) async throws -> LoginResponse {
        let url = URL(string: "\(baseURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let loginData = LoginRequest(
            username: username,
            password: password,
            device_info: deviceInfo
        )
        
        request.httpBody = try JSONEncoder().encode(loginData)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.loginFailed
        }
        
        let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
        self.accessToken = loginResponse.data.access_token
        
        return loginResponse
    }
    
    func startShift(shiftId: Int, location: CLLocation) async throws -> ShiftResponse {
        let url = URL(string: "\(baseURL)/shifts/\(shiftId)/start")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let locationData = LocationData(
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            accuracy: location.horizontalAccuracy,
            timestamp: Date()
        )
        
        let startData = StartShiftRequest(location: locationData, notes: "Starting shift")
        request.httpBody = try JSONEncoder().encode(startData)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.shiftStartFailed
        }
        
        return try JSONDecoder().decode(ShiftResponse.self, from: data)
    }
    
    func completeTask(taskId: Int, location: CLLocation, notes: String, photos: [PhotoData]) async throws -> TaskResponse {
        let url = URL(string: "\(baseURL)/tasks/\(taskId)/complete")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        
        let locationData = LocationData(
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            accuracy: location.horizontalAccuracy,
            timestamp: Date()
        )
        
        let completeData = CompleteTaskRequest(
            location: locationData,
            notes: notes,
            photos: photos
        )
        
        request.httpBody = try JSONEncoder().encode(completeData)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.taskCompleteFailed
        }
        
        return try JSONDecoder().decode(TaskResponse.self, from: data)
    }
}

// Data Models
struct LoginRequest: Codable {
    let username: String
    let password: String
    let device_info: DeviceInfo
}

struct DeviceInfo: Codable {
    let device_id: String
    let device_type: String
    let app_version: String
    let os_version: String
    let push_token: String
}

struct LoginResponse: Codable {
    let success: Bool
    let data: LoginData
}

struct LoginData: Codable {
    let access_token: String
    let refresh_token: String
    let user: User
    let permissions: [String]
    let expires_at: String
}

struct User: Codable {
    let id: Int
    let name: String
    let employee_id: String
    let role: String
    let site: Site
}

struct Site: Codable {
    let id: Int
    let name: String
    let address: String
}
```

### Android Kotlin Example

```kotlin
import android.content.Context
import android.location.Location
import com.google.gson.Gson
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

class GuardLinkMobileAPI(private val context: Context) {
    private val baseURL = "https://your-domain.com/api/guardpro/mobile"
    private val client = OkHttpClient()
    private val gson = Gson()
    private var accessToken: String? = null
    
    suspend fun login(username: String, password: String, deviceInfo: DeviceInfo): LoginResponse {
        val url = "$baseURL/auth/login"
        val requestBody = gson.toJson(LoginRequest(username, password, deviceInfo))
            .toRequestBody("application/json".toMediaType())
        
        val request = Request.Builder()
            .url(url)
            .post(requestBody)
            .build()
        
        val response = client.newCall(request).execute()
        
        if (!response.isSuccessful) {
            throw APIException("Login failed")
        }
        
        val responseBody = response.body?.string()
        val loginResponse = gson.fromJson(responseBody, LoginResponse::class.java)
        accessToken = loginResponse.data.access_token
        
        return loginResponse
    }
    
    suspend fun startShift(shiftId: Int, location: Location): ShiftResponse {
        val url = "$baseURL/shifts/$shiftId/start"
        val locationData = LocationData(
            location.latitude,
            location.longitude,
            location.accuracy.toDouble(),
            System.currentTimeMillis()
        )
        
        val requestBody = gson.toJson(StartShiftRequest(locationData, "Starting shift"))
            .toRequestBody("application/json".toMediaType())
        
        val request = Request.Builder()
            .url(url)
            .post(requestBody)
            .addHeader("Authorization", "Bearer $accessToken")
            .build()
        
        val response = client.newCall(request).execute()
        
        if (!response.isSuccessful) {
            throw APIException("Shift start failed")
        }
        
        val responseBody = response.body?.string()
        return gson.fromJson(responseBody, ShiftResponse::class.java)
    }
    
    suspend fun completeTask(taskId: Int, location: Location, notes: String, photos: List<PhotoData>): TaskResponse {
        val url = "$baseURL/tasks/$taskId/complete"
        val locationData = LocationData(
            location.latitude,
            location.longitude,
            location.accuracy.toDouble(),
            System.currentTimeMillis()
        )
        
        val requestBody = gson.toJson(CompleteTaskRequest(locationData, notes, photos))
            .toRequestBody("application/json".toMediaType())
        
        val request = Request.Builder()
            .url(url)
            .post(requestBody)
            .addHeader("Authorization", "Bearer $accessToken")
            .build()
        
        val response = client.newCall(request).execute()
        
        if (!response.isSuccessful) {
            throw APIException("Task completion failed")
        }
        
        val responseBody = response.body?.string()
        return gson.fromJson(responseBody, TaskResponse::class.java)
    }
}

// Data Classes
data class LoginRequest(
    val username: String,
    val password: String,
    val device_info: DeviceInfo
)

data class DeviceInfo(
    val device_id: String,
    val device_type: String,
    val app_version: String,
    val os_version: String,
    val push_token: String
)

data class LoginResponse(
    val success: Boolean,
    val data: LoginData
)

data class LoginData(
    val access_token: String,
    val refresh_token: String,
    val user: User,
    val permissions: List<String>,
    val expires_at: String
)

data class User(
    val id: Int,
    val name: String,
    val employee_id: String,
    val role: String,
    val site: Site
)

data class Site(
    val id: Int,
    val name: String,
    val address: String
)

data class LocationData(
    val latitude: Double,
    val longitude: Double,
    val accuracy: Double,
    val timestamp: Long
)

data class StartShiftRequest(
    val location: LocationData,
    val notes: String
)

data class CompleteTaskRequest(
    val location: LocationData,
    val notes: String,
    val photos: List<PhotoData>
)

data class PhotoData(
    val filename: String,
    val data: String,
    val description: String
)
```

## Best Practices

### Mobile Development

1. **Offline Support**: Implement robust offline capabilities with local data storage
2. **Location Services**: Use GPS and geofencing for location-based features
3. **Push Notifications**: Implement real-time notifications for important events
4. **File Upload**: Optimize photo and audio uploads with compression
5. **Security**: Use biometric authentication and secure token storage

### Performance

1. **Caching**: Implement intelligent caching for frequently accessed data
2. **Compression**: Compress images and audio files before upload
3. **Batch Operations**: Group multiple operations to reduce API calls
4. **Background Sync**: Sync data in the background when network is available
5. **Error Handling**: Implement retry logic for failed operations

### User Experience

1. **Real-time Updates**: Use WebSocket connections for live data
2. **Offline Indicators**: Show users when they're offline
3. **Progress Indicators**: Display upload and sync progress
4. **Intuitive UI**: Design mobile-first user interfaces
5. **Accessibility**: Ensure accessibility compliance

---

*GuardLink Mobile API: On-the-Go Security Management*
