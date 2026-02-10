# Assessment of GuardPro Features

This document outlines the assessment of the `guardpro` module for missing features, based on code review, TODOs, and disabled configurations.

## Summary of Findings

Overall, the module is feature-rich but contains several disabled components and pending tasks documented in TODO comments.

### 1. Fixed Items
The following items were identified as broken or disabled and have been **fixed** during this assessment:

*   **Email Templates**:
    *   **Task Assignment Notification**: Corrected invalid field reference `${item.description}` to `${item.name}` in the checklist loop. `guard.task.checklist` uses `name` for the item description.
    *   **Key Overdue Notification**: Re-enabled this template. It was commented out due to a belief that `model_key_register` did not exist. Verification confirmed `models/key_management.py` defines `key.register`, so the template is now active and functional.

*   **Mobile App** (`static/src/js/mobile_navigation.js`):
    *   **Implemented Views**: Profile, Site Info, Emergency Procedures, Settings.
    *   **Action**: Created new controller routes, QWeb templates, and updated JavaScript navigation logic to enable these previously missing sections.

### 2. Disabled Features (Requires Action)
The following features are currently disabled in the code and may need significant effort to re-enable:

*   **Audit Logging** (`models/audit_log.py`):
    *   Status: **Disabled**.
    *   Reason: "Temporarily disabled to resolve Many2many field conflicts".
    *   Impact: Critical models (Incident Report, Guard Shift, etc.) are not generating audit logs.
    *   Action: Requires investigating the specific M2M conflict in `AuditMixin` or the target models.

*   **Auto Followers** (`models/auto_followers_mixin.py`):
    *   Status: **Disabled**.
    *   Reason: "Temporarily disabled to resolve Many2many field conflicts".
    *   Impact: Stakeholders (Managers, Clients) are not automatically added as followers to new records.

*   **SLA Breach Alert Email** (`data/additional_email_templates.xml`):
    *   Status: **Disabled**.
    *   Reason: "SLA model is properly defined".
    *   Analysis: The template references `model_sla_management` which matches `sla.definition`, but the template logic (iterating KPIs and checking `actual_value`) conflicts with the unified `sla.definition` model structure.
    *   Action: Requires rewriting the template to target `sla.performance` (per breach) or creating a custom report method.

### 3. Missing Features (TODOs)
The following features are unimplemented logic marked with `TODO`:


*   **Training & Education** (`models/training_course.py`):
    *   **Lesson Tracking**: `record.progress_percentage` is hardcoded to `0.0`. Logic to calculate progress based on completed lessons is missing.

*   **Messaging** (`controllers/messaging_api.py`):
    *   **Urgent Notifications**: Logic to send urgent notifications (e.g., Push/SMS) is missing in the API.

*   **API Management** (`models/api_key.py`):
    *   **Usage Logging**: No logic to log API request usage.

*   **Emergency Procedures** (`models/emergency_procedure.py`):
    *   **Notifications**: "Actual notification logic (SMS, email, etc.)" is missing.

*   **Wizards**:
    *   **Package Collection**: SMS gateway integration is missing.
    *   **GDPR Request**: PDF report generation is missing.

## Recommendations

1.  **Prioritize Audit Logging**: Security modules require robust auditing. Investigating the "Many2many conflict" should be a high priority.
2.  **Implement Mobile Views**: If mobile usage is critical for guards, the missing views in `mobile_navigation.js` should be implemented.
3.  **Review SLA Alerts**: Decide if email alerts for SLA breaches are needed alongside the existing internal activity alerts.

