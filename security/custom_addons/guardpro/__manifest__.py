# -*- coding: utf-8 -*-
{
    'name': 'GuardLink - Security Guard Management',
    'version': '18.0.1.1.225',
    'category': 'Services/Security',
    'summary': 'Win premium guard contracts with an Odoo-native suite for mobile patrols, SLA automation, client portals, and analytics.',
    'description': """
GuardLink - Enterprise Security Operations Suite
===============================================

GuardLink centralizes security guard field operations, compliance, and client reporting inside Odoo 18 Community Edition. The suite connects supervisors, control rooms, guards, and clients with real-time visibility, mobile-first workflows, and automated analytics.

Core Highlights
---------------
* Mobile-first guard experience with offline-ready PWA, live GPS tracking, and checkpoint verification (NFC, QR, geofencing)
* Incident, emergency, and compliance management with evidence capture, workflows, escalation ladders, and SLA tracking
* Centralized scheduling, attendance control, and guard credential lifecycle management with conflict detection
* 30+ operational modules covering tasks, visitors, packages, keys, tours, audits, daily activity reports, and more
* Client and guard portals with secure role-based access, dashboards, and self-service reporting

Mobile & Field Operations
-------------------------
* Progressive Web App installable on iOS and Android with offline synchronization
* GPS diagnostics, location history, panic alerts, and live geofence monitoring
* Patrol tour designer, checkpoint map creator, optimized route planner, and bulk assignment wizards
* Guard shift management with swap approvals, availability planning, and attendance reconciliation

Control Room & Compliance
-------------------------
* Incident lifecycle coverage: reporting, investigation, escalation logs, SLA breach alerts, and client notifications
* Visitor, contractor, package, key, and lost and found workflows with automated reminders
* Compliance audits, SOP knowledge base, emergency procedures, broadcast templates, and audit-ready trails
* Performance dashboards, analytics grids, KPI tracking, and exportable PDF or Excel reports

Automation & Integrations
-------------------------
* 18 scheduled actions handling alerts, daily activity report generation, SLA calculations, credential renewals, and messaging
* REST API endpoints, webhook framework, and portal enhancements for external integrations
* Odoo-native collaboration with mail chatter, project tasks, HR employees, website slides eLearning, and portal

Included Components
-------------------
* Models: guard profiles, client projects, tours, checkpoints, shifts, incidents, attendance, credentials, equipment, analytics, and more
* Views: form, kanban, calendar, map, dashboard templates, portal pages, mobile layouts, and documentation center
* Wizards: shift assignment, conflict resolver, route optimizer, GDPR requests, emergency broadcast, task creation, package collection
* Reports: full PDF suite (incidents, daily activity reports, attendance, site summary, training certificates, compliance, equipment)

Technical Requirements
----------------------
* Odoo 18 Community Edition, Python 3.10+, PostgreSQL 13+
* Mandatory dependencies: base, web, website, hr, project, contacts, mail, portal, auth_signup, website_slides
* Optional integrations: hr_attendance for attendance syncing, maintenance for equipment lifecycle
* External Python dependency: markdown (documentation rendering)

Implementation Guidance
-----------------------
* Delivered with built-in documentation (getting started, user, developer, API, best practices) accessible inside Odoo
* Security-first design with granular groups, access control lists, record rules, and audit logging
* Follows modern Odoo ORM patterns, batched operations, computed fields, chatter integration, and multi-site awareness

Support & Roadmap
-----------------
* Version 18.0.1.0.8 consolidates the 2025 enhancement wave: analytics dashboards, emergency broadcast suite, eLearning content, and security audit tooling
* Roadmap items include AI-assisted scheduling, expanded compliance automation, and customer success analytics. Feedback is welcomed via the GuardLink support channel.
    """,
    'author': 'GuardLink',
    'website': 'https://guardlink.app/',
    'support': 'mails4ranjith@gmail.com',
    'maintainers': ['guardlink'],
    'license': 'LGPL-3',
    'price': 1000,
    'currency': 'USD',
    'depends': [
        'base',
        'web',
        'muk_web_appsbar',  # Apps sidebar; owns res.users.sidebar_type (do not redefine in guardpro)
        'website',  # Required for PWA routes
        'hr',
        # 'hr_attendance',  # Optional - For guard check-in/out tracking integration
        'project',
        'project_todo',
        'contacts',
        'mail',
        'portal',
        'auth_signup',  # Required for portal user signup tokens
        # 'maintenance',  # Optional - Equipment and asset management integration
        'website_slides',  # eLearning module for training management
        # 'website_slides_survey',  # Optional - eLearning certification and survey features
        # 'muk_web_dialog',  # REMOVED - Not installable in this environment

    ],
    'data': [
        # Security - XML files defining groups MUST be loaded before CSV
        'security/guardpro_security.xml',
        'security/guard_task_security.xml',
        'security/visitor_management_security.xml',
        'security/guard_performance_security.xml',
        'security/credential_security.xml',
        'security/portal_enhancements_security.xml',
        'security/resident_complaint_security.xml',
        'security/audit_log_security.xml',  # Audit log security (Oct 2025)
        'security/elearning_security.xml',  # eLearning record rules for guards
        # CSV file MUST be loaded AFTER all group definitions
        'security/ir.model.access.csv',
        'security/guardpro_record_rules.xml',
        'security/guardpro_isolation_rules.xml',
        'security/guardpro_zone_record_rules.xml',
        # OPTIONAL: Requires hr_attendance module
        # 'security/hr_attendance_guard_security.csv',
        # OPTIONAL: Requires project module
        # 'security/project_task_guard_security.csv',
        
        # Sequences (MUST load before other data)
        'data/sequences.xml',
        'data/investigation_sequences.xml',
        'data/checkpoint_sequence.xml',
        
        # Master Data (always load)
        'data/incident_categories.xml',
        'data/facility_issue_filters.xml',
        'data/checkpoint_types.xml',
        'data/shift_management_config.xml',  # Shift conflict detection configuration
        'data/email_templates.xml',
        'data/email_templates_odoo18.xml',
        'data/portal_email_templates.xml',
        'data/additional_email_templates.xml',  # High-priority email templates (Oct 2025)
        'data/missing_email_templates.xml',  # Missing email templates (Nov 2025)
        'data/email_templates_fixes.xml',  # Fixed disabled templates (Nov 2025)
        'data/phase2_email_templates_fixed.xml',  # Phase 2 email templates - Recreated with clean structure
        # 'data/phase2_email_templates.xml',  # BROKEN VERSION - DO NOT USE (HTML escaping issue)
        'data/mail_message_subtypes.xml',  # Standardized chatter subtypes (Oct 2025)
        'data/performance_criteria_data.xml',
        'data/credential_types_data.xml',
        'data/guardpro_analytics_dashboard_data.xml',
        'data/guardpro_tours_dashboard_data.xml',  # Tours Dashboard
        'data/compliance_audit_templates_data.xml',
        'data/uae_compliance_audit_templates_data.xml',
        'data/sla_template_data.xml',  # SLA Templates for easy setup
        # Knowledge Base & SOPs - UAE/SIRA Standards (Nov 2025)
        'data/knowledge_guard_roles_uae.xml',
        'data/knowledge_categories_uae.xml',
        'data/knowledge_tags_uae.xml',
        'data/knowledge_sops_uae.xml',
        'data/knowledge_articles_uae.xml',
        
        # Emergency Procedures - Dubai/SIRA Standards (Nov 2025)
        'data/emergency_procedures_dubai_data.xml',
        
        # Investigation Templates and Checklists (Jan 2026)
        'data/investigation_templates_data.xml',
        'data/investigation_checklist_items_data.xml',
        'data/fire_emergency_category.xml',
        'data/door_lock_category.xml',
        
        # Guard Task Templates - UAE Standards (Jan 2026)
        'data/guard_task_templates_uae.xml',
        'data/guard_task_templates_uae_extended.xml',
        
        # Scheduled Actions (Cron Jobs)
        'data/mail_mail_retention_config.xml',
        'data/ir_cron.xml',
        'data/attendance_auto_checkout_cron.xml',
        'data/new_modules_cron.xml',
        'data/elearning_cron.xml',
        'data/messaging_cron.xml',
        'data/performance_cron.xml',
        'data/credential_cron.xml',
        'data/portal_enhancement_cron.xml',
        'data/sla_escalation_cron.xml',  # SLA-based escalation cron jobs
        'data/mobile_outbox_cron.xml',  # Unified mobile outbox purge
        'data/tour_manual_generation_server_actions.xml',
        # 'data/populate_quiz_data_action.xml',  # Populate test quiz question data - DISABLED (has syntax issue)
        # OPTIONAL: Requires hr_attendance module
        # 'data/hr_attendance_cron.xml',
        
        # eLearning Courses Data - Guard-Focused Training
        'data/elearning/elearning_courses_data.xml',
        'data/elearning/elearning_slides_fundamentals.xml',
        'data/elearning/elearning_slides_guard_operations.xml',
        'data/elearning/elearning_slides_supervisor_ops.xml',
        'data/elearning/elearning_slides_basic_security.xml',
        'data/elearning/elearning_slides_emergency_response.xml',
        'data/elearning/elearning_slides_fire_safety.xml',
        'data/elearning/elearning_slides_first_aid.xml',
        'data/elearning/elearning_slides_conflict_resolution.xml',
        'data/elearning/elearning_slides_customer_service.xml',
        'data/elearning/elearning_slides_legal_compliance.xml',
        'data/elearning/elearning_slides_patrol_techniques.xml',
        'data/elearning/elearning_slides_report_writing.xml',
        # 'data/elearning/guard_training_courses_data.xml',
        'data/elearning/guard_training_content_fill.xml',
        
        # Dubai & SIRA Specific Training Content
        'data/elearning/elearning_slides_sira_compliance.xml',
        'data/elearning/elearning_slides_uae_culture.xml',
        'data/elearning/elearning_slides_dubai_operations.xml',
        'data/elearning/elearning_slides_advanced_operations.xml',
        # New UAE regulatory courses
        'data/elearning/elearning_slides_uae_licensing.xml',
        'data/elearning/elearning_slides_dubai_police_regs.xml',
        'data/elearning/elearning_slides_uae_labor_law.xml',
        'data/elearning/elearning_slides_uae_penal_code.xml',
        'data/elearning/elearning_slides_uae_commercial_security.xml',
        'data/elearning/elearning_slides_uae_residential_security.xml',
        'data/elearning/elearning_slides_drone_attack_procedures.xml',
        'data/elearning/elearning_slides_security_cordons_incident_site.xml',
        
        # Reports (PDF) - Must load before views that reference them
        'data/id_card_paperformat.xml',
        'reports/guard_id_card_template.xml',
        
        # Views - Models (MUST be loaded before menus)
        'views/user_views.xml',
        'views/guard_profile_views.xml',
        'views/gps_diagnostic_views.xml',
        'views/guard_credential_views.xml',
        'views/credential_type_views.xml',
        'views/guard_background_check_views.xml',
        'views/guard_drug_test_views.xml',
        'views/guard_vaccination_views.xml',
        'views/guard_location_history_views.xml',
        'views/geofence_alert_views.xml',
        'views/client_site_views.xml',
        'views/guard_site_views.xml',
        'views/tenant_resident_views.xml',
        'views/resident_complaint_views.xml',
        'views/security_tour_checkpoint_line_views.xml',
        'views/security_tour_views.xml',
        'views/checkpoint_map_creator.xml',
        'views/checkpoint_views.xml',
        'views/guard_shift_views.xml',
        'views/shift_swap_views.xml',
        'wizard/shift_template_generate_wizard_views.xml',  # Must load before shift_template_views.xml
        'views/shift_template_views.xml',
        # OPTIONAL: Requires hr_attendance module
        # 'views/hr_attendance_guard_views.xml',
        # 'views/guard_shift_plan_views.xml',
        # 'views/guard_shift_template_views.xml',
        'views/guard_task_views.xml',
        'views/visitor_management_views.xml',
        'views/package_management_views.xml',
        'views/lost_found_views.xml',
        'views/key_management_views.xml',
        'views/compliance_audit_views.xml',
        'views/sla_management_views.xml',
        'views/sla_template_views.xml',
        'views/sla_wizard_views.xml',
        'views/incident_report_views.xml',
        'views/incident_form_definition_views.xml',
        'views/incident_sla_policy_views.xml',
        'views/incident_escalation_log_views.xml',
        'views/incident_investigation_views.xml',
        'views/incident_investigation_components_views.xml',
        'views/incident_investigation_checklist_views.xml',
        'views/incident_status_update_views.xml',
        'views/emergency_procedure_views.xml',
        'views/emergency_broadcast_views.xml',
        'views/push_to_talk_views.xml',  # Push-to-Talk (Walkie-Talkie) feature
        'views/guard_message_views.xml',  # Internal messaging system
        'views/guard_attendance_views.xml',
        'views/guard_performance_views.xml',
        'views/equipment_views.xml',
        'views/equipment_handover_views.xml',
        # OPTIONAL: Requires maintenance module
        # 'views/equipment_maintenance_views.xml',  # Native maintenance module extension
        # OPTIONAL: Requires project module
        # 'views/project_task_guard_views.xml',  # Native project module extension
        'views/tour_log_views.xml',
        'views/facility_issue_views.xml',
        'views/checkpoint_scan_views.xml',
        'views/daily_activity_report_views.xml',
        'views/guard_activity_report_views.xml',
        'views/webhook_views.xml',
        'views/client_feedback_views.xml',
        'views/client_dashboard_views.xml',
        'views/training_views.xml',
        'views/training_session_views.xml',
        # eLearning integration views (requires website_slides module)
        'views/guard_elearning_views.xml',
        'views/quiz_response_views.xml',  # Question-level quiz response views
        # 'views/elearning_navigation.xml',  # Temporarily disabled due to template conflicts
        'views/knowledge_views.xml',
        'reports/sop_report_template.xml',  # SOP printable reports - MUST load before views (Nov 2025)
        'views/knowledge_sop_views.xml',  # Enhanced SOP and UAE/SIRA views (Nov 2025)
        'views/notification_preference_views.xml',
        'views/api_key_views.xml',
        'views/audit_log_views.xml',
        'views/analytics_dashboard_views.xml',
        'views/guardpro_analytics_dashboard_views.xml',
        'views/guardpro_tours_dashboard_views.xml',  # Tours Dashboard
        'views/guards_map_view.xml',
        'views/optimized_route_map.xml',
        
        # Reports (PDF)
        'reports/incident_report_template.xml',
        'reports/shift_report_template.xml',
        'reports/tour_log_report_template.xml',
        'reports/attendance_report_template.xml',
        'reports/daily_activity_report_template.xml',
        'reports/guard_activity_report_template.xml',
        'reports/visitor_management_report_template.xml',
        'reports/incident_statement_report_template.xml',
        'reports/incident_lost_found_forms_report_template.xml',
        'reports/incident_community_violation_report_template.xml',
        'reports/incident_fm_uae_report_template.xml',
        'reports/incident_additional_categories_report_template.xml',
        'reports/package_management_report_template.xml',
        'reports/lost_found_report_template.xml',
        'reports/key_management_report_template.xml',
        'reports/compliance_audit_report_template.xml',
        'reports/sla_management_report_template.xml',
        'reports/guard_performance_report_template.xml',
        'reports/guard_credential_report_template.xml',
        'reports/guard_task_report_template.xml',
        'reports/resident_complaint_report_template.xml',
        'reports/equipment_report_template.xml',
        'reports/equipment_handover_report_template.xml',
        'reports/guard_background_check_report_template.xml',
        'reports/guard_drug_test_report_template.xml',
        'reports/guard_vaccination_report_template.xml',
        'reports/client_feedback_report_template.xml',
        'reports/emergency_broadcast_report_template.xml',
        'reports/emergency_procedure_report_template.xml',
        'reports/shift_swap_request_report_template.xml',
        'reports/security_tour_route_report_template.xml',
        'reports/analytics_dashboard_report.xml',
        'reports/tours_dashboard_report.xml',
        'reports/incident_fire_emergency_report.xml',
        'reports/incident_door_lock_report.xml',
        # Phase 2 PDF Reports - New templates (Nov 2025)
        'reports/incident_investigation_report_template.xml',  # Incident investigation comprehensive report
        'reports/training_certificate_template.xml',  # Training course completion certificates
        'reports/geofence_alert_report_template.xml',  # Geofence violation documentation
        'reports/shift_swap_approval_form_template.xml',  # Shift swap approval formal documentation
        'reports/guard_attendance_summary_template.xml',  # Guard attendance summary for payroll
        'reports/site_security_summary_template.xml',  # Site security status and statistics
        'reports/checkpoint_scan_compliance_template.xml',  # Checkpoint scan compliance verification
        'reports/monthly_performance_dashboard_template.xml',  # Monthly performance dashboard
        'reports/emergency_drill_report_template.xml',  # Emergency drill documentation
        'reports/sla_performance_report_template.xml',  # Detailed SLA performance metrics
        'reports/equipment_maintenance_history_template.xml',  # Equipment maintenance history
        'reports/credential_compliance_summary_template.xml',  # Credential compliance summary
        'reports/visitor_access_log_template.xml',  # Visitor access audit trail
        'reports/lost_found_inventory_template.xml',  # Lost & found inventory status
        'reports/package_delivery_summary_template.xml',  # Package delivery statistics
        
        # Portal Views
        'views/guard_portal_views.xml',
        
        # Wizards
        'views/shift_assignment_wizard_views.xml',
        'views/shift_conflict_wizard_views.xml',
        'views/guard_user_wizard_views.xml',
        'views/route_optimizer_views.xml',
        'views/map_data_export_views.xml',
        'views/bulk_operations_wizard_views.xml',
        'views/gdpr_wizard_views.xml',
        'views/emergency_broadcast_wizard_views.xml',
        'wizard/guard_task_create_wizard_views.xml',
        'wizard/package_collect_wizard_views.xml',
        'wizard/key_issue_wizard_views.xml',
        'wizard/compliance_audit_create_wizard_views.xml',
        'views/tour_manual_generation_wizard_views.xml',
        'wizard/email_template_tester_views.xml',
        # OPTIONAL: Requires maintenance module
        # 'wizard/guard_equipment_assignment_wizard_views.xml',
        
        # Quick Wins
        'views/favorites_views.xml',
        
        # Configuration Settings
        'views/res_config_settings_views.xml',
        'views/documentation_templates.xml',

        # Location Hierarchy Views (MUST load before menus that reference actions)
        'views/location_hierarchy_views.xml',

        # CCTV actions (menus reference guardpro.action_cctv_monitoring / action_cctv_camera)
        'views/cctv_camera_views.xml',

        # Biometric actions (menus reference action_guard_biometric_*)
        'views/guard_biometric_views.xml',

        # Menus (data/ — Odoo 18 validates views/*.xml with a schema that rejects menuitem)
        'data/guardpro_menus.xml',

        # Portal Enhancement Templates
        'views/portal_enhanced_templates.xml',
        'views/portal_feedback_templates.xml',
        
        # Site Geofence Map Template
        'views/site_geofence_map.xml',
        
        # Homepage Template
        'views/guardpro_homepage_template.xml',
        'views/berkeley_homepage_template.xml',  # GuardLink branded homepage
        'views/privacy_policy_template.xml',  # Public Privacy Policy (Play / App Store)
        # PWA Templates (Legacy - DISABLED - files removed to avoid 404 errors)
        # 'views/pwa_templates.xml',  # References deleted static/pwa/ files
        # 'views/pwa_optimized_templates.xml',  # References deleted static/pwa/ files
        # 'views/pwa_pages.xml',  # References deleted static/pwa/ files
        # Note: Old PWA backed up to backup_old_pwa_js/pwa_directory_backup.tar.gz
        
        # Mobile Templates (Odoo-native, minimal JS)
        # Note: mobile_dashboard.xml and mobile_app_layout.xml removed - duplicates of mobile_simple_templates.xml
        'views/mobile_layout.xml',  # Lightweight mobile layout (skips frontend_lazy JS)
        'views/mobile_simple_templates.xml',  # Main mobile interface templates
        'views/mobile_views.xml',  # Mobile-optimized backend views (kanban, forms)
    ],
    'external_dependencies': {
        'python': [
            'markdown',  # Documentation rendering
            'cryptography>=41.0.0',  # Biometric encryption (Fernet, PBKDF2)
            'requests>=2.28.0',  # webhooks, API calls
            'pytesseract',  # Optional: Emirates ID camera OCR (requires tesseract-ocr system package)
        ],
    },
    'assets': {
        'web.assets_backend': [
            'guardpro/static/src/scss/guardpro.scss',
            'guardpro/static/src/scss/dashboard.scss',
            'guardpro/static/src/scss/guardpro_analytics_dashboard.scss',
            'guardpro/static/src/scss/guardpro_tours_dashboard.scss',
            'guardpro/static/src/scss/security_tour_checkpoints.scss',
            'guardpro/static/src/scss/tour_log_observations.scss',
            'guardpro/static/src/scss/incident_report_form.scss',
            'guardpro/static/src/js/security_tour_checkpoint_dropdown.js',
            'guardpro/static/src/css/guard_map.css',
            'guardpro/static/src/css/emergency_broadcast_popup.css',
            'guardpro/static/src/css/analytics_dashboard_filters.css',
            'guardpro/static/src/css/push_to_talk.css',  # Push-to-Talk styles
            'guardpro/static/src/js/gps_tracker.js',
            'guardpro/static/src/js/guard_gps_auto_init.js',  # Auto-start GPS for guards
            'guardpro/static/src/js/incident_location_geofill.js',
            'guardpro/static/src/js/nfc_scanner.js',
            'guardpro/static/src/js/qr_scanner.js',
            'guardpro/static/src/js/geofence.js',
            'guardpro/static/src/js/shift_scheduler.js',
            'guardpro/static/src/js/dashboard_widgets.js',
            'guardpro/static/src/js/dashboard_stats.js',
            'guardpro/static/src/js/dashboard_refresh.js',
            'guardpro/static/src/js/guard_map.js',
            'guardpro/static/src/js/checkpoint_map_creator.js',
            'guardpro/static/src/js/emergency_broadcast_popup.js',
            'guardpro/static/src/js/guardpro_analytics_dashboard_simple.js',
            'guardpro/static/src/js/guardpro_analytics_dashboard.js',
            'guardpro/static/src/js/guardpro_tours_dashboard.js',
            'guardpro/static/src/js/push_to_talk.js',  # Push-to-Talk widget
            'guardpro/static/src/js/eid_reader_core_v7.js',  # Emirates ID toolkit integration (V5.1 - Final - Renamed)
            'guardpro/static/src/js/emirates_id_camera_scan.js',  # Emirates ID camera scan + server OCR
            'guardpro/static/src/xml/dashboard_templates.xml',
            'guardpro/static/src/xml/dashboard_refresh_template.xml',
            'guardpro/static/src/xml/checkpoint_map_creator.xml',
            'guardpro/static/src/xml/emergency_broadcast_popup.xml',
            'guardpro/static/src/xml/guardpro_analytics_dashboard_simple.xml',
            'guardpro/static/src/xml/guardpro_analytics_dashboard_templates.xml',
            'guardpro/static/src/xml/guardpro_tours_dashboard_templates.xml',
            'guardpro/static/src/xml/push_to_talk_templates.xml',  # Push-to-Talk templates
            ('include', 'web._assets_helpers'),
            ('include', 'web.chartjs_lib'),  # Use Odoo's built-in Chart.js instead of CDN
        ],
        # Portal CSS only on website frontend (JS moved to guardpro.assets_mobile*)
        'web.assets_frontend': [
            'guardpro/static/src/css/portal.css',
            'guardpro/static/src/css/mobile_dashboard.css',
            'guardpro/static/src/css/tour_scanner.css',
            'guardpro/static/src/js/guard_elearning_navigation.js',  # eLearning pages still use website layout
        ],
        # Core GuardLink mobile PWA scripts (loaded instead of web.assets_frontend_lazy)
        'guardpro.assets_mobile': [
            'guardpro/static/src/js/gps_tracker.js',
            'guardpro/static/src/js/guard_gps_mobile_init.js',
            'guardpro/static/src/js/mobile_navigation.js',
            'guardpro/static/src/js/mobile_incident_wizard.js',
            'guardpro/static/src/js/mobile_emergency_broadcast.js',
            'guardpro/static/src/js/mobile_patrol_reminder.js',
            'guardpro/static/src/js/mobile_task_assignment.js',
            'guardpro/static/src/js/mobile_outbox.js',
        ],
        'guardpro.assets_mobile_ptt': [
            'guardpro/static/src/css/push_to_talk.css',
            'guardpro/static/src/js/mobile_push_to_talk.js',
        ],
        'guardpro.assets_mobile_messages': [
            'guardpro/static/src/js/mobile_guard_messages.js',
        ],
        'guardpro.assets_mobile_eid': [
            'guardpro/static/src/js/mobile_emirates_id_camera_scan.js',
        ],
    },
    'demo': [
        'demo/client_demo_data.xml',
        'demo/guard_demo_data.xml',
        'demo/credential_demo_data.xml',
        'demo/checkpoint_demo_data.xml',
        'demo/security_tour_demo_data.xml',
        'demo/shift_demo_data.xml',
        'demo/incident_demo_data.xml',
        'demo/tour_log_demo_data.xml',
        'demo/checkpoint_scan_demo_data.xml',
        'demo/attendance_demo_data.xml',
        'demo/equipment_demo_data.xml',
        'demo/enhancement_demo_data.xml',
        # New Modules Demo Data (2024 Enhancement Suite)
        'demo/task_management_demo_data.xml',
        'demo/visitor_management_demo_data.xml',
        'demo/lost_found_demo_data.xml',
        'demo/package_management_demo_data.xml',
        'demo/key_management_demo_data.xml',
        'demo/compliance_audit_demo_data.xml',
        'demo/sla_management_demo_data.xml',
        'demo/performance_demo_data.xml',
    ],
    'images': [
        # Big Screenshot (first image ending with '_screenshot' - displays as large screenshot)
        'static/description/banner_screenshot.png',
        # Additional Feature Screenshots (for gallery/thumbnail display)
        'static/description/analyticsdashboard.png',
        'static/description/liveguardview.png',
        'static/description/locationhistor.png',
        'static/description/incidentreport.png',
        'static/description/complianceaudits.png',
        'static/description/dailyactivityreport.png',
        'static/description/geofencealerts.png',
        'static/description/training_management.png',
        'static/description/knowledgebase.png',
        # Note: icon.png is automatically detected at static/description/icon.png (not in images array)
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}

