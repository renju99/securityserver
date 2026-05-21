# -*- coding: utf-8 -*-
"""GuardLink Models."""

from . import website_fix  # Fix for REQUEST_URI KeyError in website module
from . import ir_http  # Permissions-Policy for mobile PWA (camera)
from . import ir_rule
from . import photo_attachment_mixin  # Mixin for photo attachments
from . import mail_activity  # Suppress noisy activity assignment emails
from . import mail_mail  # mail.mail retention (optional cron)
from . import mail_template_guardpro  # Odoo 18 mail template syntax migration
from . import res_partner
from . import res_users
from . import gps_diagnostic
from . import guard_profile
from . import credential_type
from . import guard_credential
from . import guard_background_check
from . import guard_drug_test
from . import guard_vaccination
from . import guard_location_history
from . import guard_location_live
from . import geofence_alert
from . import client_site
from . import location_hierarchy
from . import tenant_resident
from . import resident_complaint
from . import security_tour
from . import security_tour_checkpoint_line
from . import checkpoint
from . import guard_shift
from . import shift_swap_request
from . import shift_template
# New HR-based attendance and shift planning (simplified)
# OPTIONAL: Requires hr_attendance module
# from . import hr_attendance_guard
# from . import guard_shift_plan
# from . import guard_shift_template
from . import guard_task
from . import guard_message
from . import guard_message_channel_all_sites
from . import guard_biometric_template
from . import guard_biometric_verification
from . import guard_biometric_device
from . import push_to_talk
from . import push_to_talk_all_sites
from . import task_suggestion
from . import incident_report
from . import incident_sla_policy
from . import incident_escalation_log
from . import incident_investigation
from . import incident_investigation_timeline
from . import incident_investigation_evidence
from . import incident_investigation_witness
from . import incident_investigation_finding
from . import incident_investigation_template
from . import incident_investigation_checklist
from . import incident_status_update
from . import incident_template
from . import visitor_management
from . import lost_found
from . import package_management
from . import key_management
from . import compliance_audit
from . import daily_activity_report
from . import sla_management
from . import sla_template
from . import emergency_procedure
from . import emergency_broadcast
from . import guard_attendance
from . import equipment
# OPTIONAL: Requires maintenance module
# from . import equipment_maintenance  # Equipment using native maintenance module
from . import cctv_camera  # CCTV Camera management
from . import tour_log
from . import tour_patrol_reminder
from . import checkpoint_scan
from . import facility_patrol_issue
from . import webhook
from . import client_feedback
from . import training_course
# eLearning integration (requires website_slides module)
from . import slide_channel_inherit  # eLearning course extensions
from . import guard_elearning  # Guard eLearning extensions
# OPTIONAL: Requires project module
# from . import project_task_guard  # Guard tasks using native project module
from . import knowledge_article
from . import notification_preference
from . import api_key
from . import favorites
from . import client_dashboard
from . import dashboard_diagnostics
from . import analytics
from . import guardpro_analytics_dashboard  # GuardLink Analytics Dashboard
from . import guardpro_tours_dashboard  # GuardLink Tours Dashboard
from . import guard_performance  # Performance scoring and reviews
from . import auto_followers_mixin  # Load before audit_log
from . import audit_log  # Must be after models it inherits from
from . import res_config_settings
from . import performance_indexes  # Performance optimization indexes
from . import mobile_outbox  # Unified TWA push notification outbox


