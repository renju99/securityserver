# GuardLink Views

## Overview

GuardLink's user interface is built using Odoo's view system, providing comprehensive and intuitive interfaces for all security management operations. The views are designed with modern UX principles, responsive design, and accessibility in mind.

## View Architecture

### View Types and Structure

```
Views/
├── Tree Views (List Views)
│   ├── guard_views.xml
│   ├── shift_views.xml
│   └── incident_views.xml
├── Form Views
│   ├── guard_form.xml
│   ├── shift_form.xml
│   └── incident_form.xml
├── Kanban Views
│   ├── shift_kanban.xml
│   └── task_kanban.xml
├── Calendar Views
│   └── shift_calendar.xml
├── Graph Views
│   └── performance_graphs.xml
├── Pivot Views
│   └── analytics_pivot.xml
└── Dashboard Views
    └── main_dashboard.xml
```

## Core Views

### Guard Profile Views

#### 1. Guard List View (Tree View)

```xml
<!-- Guard Profile Tree View -->
<record id="view_guard_profile_tree" model="ir.ui.view">
    <field name="name">guard.profile.tree</field>
    <field name="model">guard.profile</field>
    <field name="arch" type="xml">
        <tree string="Guards" decoration-info="employment_status == 'active'" 
              decoration-muted="employment_status == 'inactive'"
              decoration-danger="employment_status == 'terminated'"
              default_order="name"
              multi_edit="1">
            
            <!-- Basic Information -->
            <field name="name" string="Guard Name"/>
            <field name="employee_id" string="Employee ID"/>
            <field name="email" string="Email"/>
            <field name="phone" string="Phone"/>
            
            <!-- Employment Information -->
            <field name="employment_status" string="Status" widget="badge" 
                   decoration-success="employment_status == 'active'"
                   decoration-warning="employment_status == 'inactive'"
                   decoration-danger="employment_status == 'terminated'"/>
            <field name="hire_date" string="Hire Date"/>
            
            <!-- Performance Metrics -->
            <field name="performance_score" string="Performance" widget="progressbar"/>
            <field name="attendance_rate" string="Attendance" widget="progressbar"/>
            <field name="incident_count" string="Incidents"/>
            
            <!-- Site Assignments -->
            <field name="site_ids" string="Sites" widget="many2many_tags" 
                   options="{'color_field': 'color', 'no_create': True}"/>
            
            <!-- System Fields -->
            <field name="active" invisible="1"/>
            <field name="create_uid" string="Created By" readonly="1"/>
            <field name="create_date" string="Created On" readonly="1"/>
            <field name="write_uid" string="Last Updated By" readonly="1"/>
            <field name="write_date" string="Last Updated On" readonly="1"/>
            
        </tree>
    </field>
</record>
```

#### 2. Guard Form View

```xml
<!-- Guard Profile Form View -->
<record id="view_guard_profile_form" model="ir.ui.view">
    <field name="name">guard.profile.form</field>
    <field name="model">guard.profile</field>
    <field name="arch" type="xml">
        <form string="Guard Profile" create="true" edit="true" delete="true">
            
            <!-- Header -->
            <header>
                <button name="action_assign_to_site" type="object" 
                        string="Assign to Site" class="btn-primary"
                        invisible="context.get('default_employment_status') == 'terminated'"/>
                <button name="action_update_performance" type="object" 
                        string="Update Performance" class="btn-secondary"/>
                <field name="employment_status" widget="statusbar" 
                       statusbar_visible="active,inactive,terminated"/>
            </header>
            
            <!-- Main Content -->
            <sheet>
                <div class="oe_title">
                    <h1>
                        <field name="name" placeholder="Enter guard's full name"/>
                    </h1>
                </div>
                
                <!-- Basic Information Tab -->
                <group>
                    <group string="Personal Information">
                        <field name="employee_id" string="Employee ID" required="1"/>
                        <field name="email" string="Email" widget="email"/>
                        <field name="phone" string="Phone" widget="phone"/>
                        <field name="mobile" string="Mobile" widget="phone"/>
                        <field name="date_of_birth" string="Date of Birth"/>
                        <field name="gender" string="Gender"/>
                        <field name="nationality" string="Nationality"/>
                    </group>
                    <group string="Employment Information">
                        <field name="hire_date" string="Hire Date" required="1"/>
                        <field name="employment_status" string="Employment Status"/>
                        <field name="user_id" string="System User" 
                               domain="[('groups_id', 'in', ref('guardpro.group_guardpro_guard'))]"/>
                        <field name="active" string="Active"/>
                    </group>
                </group>
                
                <!-- Address Information -->
                <group string="Address Information">
                    <field name="address" string="Address" nolabel="1" 
                           widget="text" placeholder="Enter complete address"/>
                </group>
                
                <!-- Skills and Certifications -->
                <notebook>
                    <page string="Skills &amp; Certifications">
                        <group>
                            <group string="Skills">
                                <field name="skills_ids" widget="many2many_tags" 
                                       options="{'no_create': True}"/>
                            </group>
                            <group string="Certifications">
                                <field name="certifications_ids" widget="one2many">
                                    <tree editable="bottom">
                                        <field name="name" string="Certification"/>
                                        <field name="issuing_authority" string="Issuing Authority"/>
                                        <field name="issue_date" string="Issue Date"/>
                                        <field name="expiry_date" string="Expiry Date"/>
                                        <field name="status" string="Status" widget="badge"/>
                                    </tree>
                                </field>
                            </group>
                        </group>
                    </page>
                    
                    <!-- Site Assignments -->
                    <page string="Site Assignments">
                        <field name="site_ids" widget="many2many_tags" 
                               options="{'color_field': 'color'}"/>
                    </page>
                    
                    <!-- Performance Metrics -->
                    <page string="Performance">
                        <group>
                            <group string="Performance Scores">
                                <field name="performance_score" string="Performance Score" 
                                       widget="progressbar" readonly="1"/>
                                <field name="attendance_rate" string="Attendance Rate" 
                                       widget="progressbar" readonly="1"/>
                                <field name="incident_count" string="Incident Count" readonly="1"/>
                            </group>
                            <group string="Recent Activity">
                                <field name="message_ids" widget="mail_thread" 
                                       options="{'message_post': True}"/>
                            </group>
                        </group>
                    </page>
                </notebook>
            </sheet>
            
            <!-- Chatter -->
            <div class="oe_chatter">
                <field name="message_follower_ids" widget="mail_followers"/>
                <field name="activity_ids" widget="mail_activity"/>
                <field name="message_ids" widget="mail_thread"/>
            </div>
        </form>
    </field>
</record>
```

#### 3. Guard Kanban View

```xml
<!-- Guard Profile Kanban View -->
<record id="view_guard_profile_kanban" model="ir.ui.view">
    <field name="name">guard.profile.kanban</field>
    <field name="model">guard.profile</field>
    <field name="arch" type="xml">
        <kanban string="Guards" class="o_kanban_mobile">
            <field name="name"/>
            <field name="employee_id"/>
            <field name="employment_status"/>
            <field name="performance_score"/>
            <field name="site_ids"/>
            <field name="image_128" widget="image"/>
            <templates>
                <t t-name="kanban-box">
                    <div class="oe_kanban_card oe_kanban_global_click">
                        <div class="oe_kanban_content">
                            <!-- Header -->
                            <div class="o_kanban_record_top">
                                <div class="o_kanban_record_headings">
                                    <strong class="o_kanban_record_title">
                                        <field name="name"/>
                                    </strong>
                                    <div class="o_kanban_record_subtitle">
                                        <field name="employee_id"/>
                                    </div>
                                </div>
                                <div class="o_kanban_record_top_right">
                                    <field name="employment_status" widget="badge"/>
                                </div>
                            </div>
                            
                            <!-- Avatar -->
                            <div class="o_kanban_record_body">
                                <div class="o_kanban_record_left">
                                    <div class="oe_kanban_avatar">
                                        <img t-att-src="kanban_image('guard.profile', 'image_128', record.id.raw_value)" 
                                             alt="Guard Avatar" class="oe_kanban_avatar_img"/>
                                    </div>
                                </div>
                                
                                <!-- Performance Metrics -->
                                <div class="o_kanban_record_right">
                                    <div class="o_kanban_record_details">
                                        <div class="o_kanban_record_detail">
                                            <span class="o_kanban_record_detail_label">Performance:</span>
                                            <field name="performance_score" widget="progressbar"/>
                                        </div>
                                        <div class="o_kanban_record_detail">
                                            <span class="o_kanban_record_detail_label">Sites:</span>
                                            <field name="site_ids" widget="many2many_tags"/>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Actions -->
                            <div class="o_kanban_record_bottom">
                                <div class="oe_kanban_bottom_left">
                                    <button name="action_assign_to_site" type="object" 
                                            class="btn btn-sm btn-primary" 
                                            string="Assign Site"/>
                                </div>
                                <div class="oe_kanban_bottom_right">
                                    <button name="action_view_shifts" type="object" 
                                            class="btn btn-sm btn-secondary" 
                                            string="View Shifts"/>
                                </div>
                            </div>
                        </div>
                    </div>
                </t>
            </templates>
        </kanban>
    </field>
</record>
```

### Shift Management Views

#### 1. Shift Calendar View

```xml
<!-- Shift Calendar View -->
<record id="view_guard_shift_calendar" model="ir.ui.view">
    <field name="name">guard.shift.calendar</field>
    <field name="model">guard.shift</field>
    <field name="arch" type="xml">
        <calendar string="Shift Calendar" 
                  date_start="start_time" 
                  date_stop="end_time"
                  color="guard_id"
                  event_open_popup="true"
                  quick_add="true"
                  mode="month">
            
            <!-- Calendar Fields -->
            <field name="name"/>
            <field name="guard_id"/>
            <field name="site_id"/>
            <field name="status"/>
            <field name="start_time"/>
            <field name="end_time"/>
            
            <!-- Calendar Templates -->
            <templates>
                <div t-name="calendar-box">
                    <div class="fc-content">
                        <div class="fc-title">
                            <field name="guard_id"/>
                        </div>
                        <div class="fc-time">
                            <field name="start_time" widget="time"/>
                            -
                            <field name="end_time" widget="time"/>
                        </div>
                        <div class="fc-site">
                            <field name="site_id"/>
                        </div>
                        <div class="fc-status">
                            <field name="status" widget="badge"/>
                        </div>
                    </div>
                </div>
            </templates>
        </calendar>
    </field>
</record>
```

#### 2. Shift Form View

```xml
<!-- Shift Form View -->
<record id="view_guard_shift_form" model="ir.ui.view">
    <field name="name">guard.shift.form</field>
    <field name="model">guard.shift</field>
    <field name="arch" type="xml">
        <form string="Guard Shift" create="true" edit="true" delete="true">
            
            <!-- Header -->
            <header>
                <button name="action_check_in" type="object" 
                        string="Check In" class="btn-primary"
                        invisible="status != 'scheduled'"/>
                <button name="action_check_out" type="object" 
                        string="Check Out" class="btn-success"
                        invisible="status != 'in_progress'"/>
                <button name="action_cancel_shift" type="object" 
                        string="Cancel Shift" class="btn-danger"
                        invisible="status in ['completed', 'cancelled']"/>
                <field name="status" widget="statusbar" 
                       statusbar_visible="scheduled,in_progress,completed"/>
            </header>
            
            <!-- Main Content -->
            <sheet>
                <div class="oe_title">
                    <h1>
                        <field name="name" readonly="1"/>
                    </h1>
                </div>
                
                <!-- Basic Information -->
                <group>
                    <group string="Assignment Information">
                        <field name="shift_number" string="Shift Number" readonly="1"/>
                        <field name="guard_id" string="Guard" required="1"/>
                        <field name="site_id" string="Site" required="1"/>
                        <field name="client_id" string="Client" readonly="1"/>
                    </group>
                    <group string="Schedule Information">
                        <field name="scheduled_date" string="Scheduled Date" required="1"/>
                        <field name="start_time" string="Start Time" required="1"/>
                        <field name="end_time" string="End Time" required="1"/>
                        <field name="duration" string="Duration (hours)" readonly="1"/>
                    </group>
                </group>
                
                <!-- Check-in/Check-out Information -->
                <group string="Check-in/Check-out Information">
                    <group>
                        <field name="check_in_time" string="Check-in Time" readonly="1"/>
                        <field name="check_in_location" string="Check-in Location" readonly="1"/>
                        <field name="check_in_photo" string="Check-in Photo" widget="image" readonly="1"/>
                    </group>
                    <group>
                        <field name="check_out_time" string="Check-out Time" readonly="1"/>
                        <field name="check_out_location" string="Check-out Location" readonly="1"/>
                        <field name="check_out_photo" string="Check-out Photo" widget="image" readonly="1"/>
                    </group>
                </group>
                
                <!-- Performance Metrics -->
                <group string="Performance Metrics">
                    <group>
                        <field name="tasks_completed" string="Tasks Completed" readonly="1"/>
                        <field name="patrols_completed" string="Patrols Completed" readonly="1"/>
                    </group>
                    <group>
                        <field name="incidents_reported" string="Incidents Reported" readonly="1"/>
                    </group>
                </group>
                
                <!-- Related Records -->
                <notebook>
                    <page string="Tasks">
                        <field name="task_ids" widget="one2many">
                            <tree editable="bottom">
                                <field name="name" string="Task Name"/>
                                <field name="task_type" string="Type"/>
                                <field name="priority" string="Priority" widget="badge"/>
                                <field name="status" string="Status" widget="badge"/>
                                <field name="due_time" string="Due Time"/>
                            </tree>
                        </field>
                    </page>
                    
                    <page string="Patrols">
                        <field name="patrol_ids" widget="one2many">
                            <tree>
                                <field name="name" string="Patrol Name"/>
                                <field name="start_time" string="Start Time"/>
                                <field name="end_time" string="End Time"/>
                                <field name="status" string="Status" widget="badge"/>
                            </tree>
                        </field>
                    </page>
                    
                    <page string="Incidents">
                        <field name="incident_ids" widget="one2many">
                            <tree>
                                <field name="name" string="Incident"/>
                                <field name="incident_type" string="Type"/>
                                <field name="severity" string="Severity" widget="badge"/>
                                <field name="status" string="Status" widget="badge"/>
                            </tree>
                        </field>
                    </page>
                </notebook>
            </sheet>
            
            <!-- Chatter -->
            <div class="oe_chatter">
                <field name="message_follower_ids" widget="mail_followers"/>
                <field name="activity_ids" widget="mail_activity"/>
                <field name="message_ids" widget="mail_thread"/>
            </div>
        </form>
    </field>
</record>
```

### Incident Management Views

#### 1. Incident Form View

```xml
<!-- Incident Form View -->
<record id="view_guard_incident_form" model="ir.ui.view">
    <field name="name">guard.incident.form</field>
    <field name="model">guard.incident</field>
    <field name="arch" type="xml">
        <form string="Security Incident" create="true" edit="true" delete="true">
            
            <!-- Header -->
            <header>
                <button name="action_assign_investigator" type="object" 
                        string="Assign Investigator" class="btn-primary"
                        invisible="status != 'reported'"/>
                <button name="action_resolve_incident" type="object" 
                        string="Resolve Incident" class="btn-success"
                        invisible="status != 'investigating'"/>
                <button name="action_escalate_incident" type="object" 
                        string="Escalate" class="btn-warning"
                        invisible="status in ['resolved', 'closed']"/>
                <field name="status" widget="statusbar" 
                       statusbar_visible="reported,investigating,resolved,closed"/>
            </header>
            
            <!-- Main Content -->
            <sheet>
                <div class="oe_title">
                    <h1>
                        <field name="name" placeholder="Enter incident title"/>
                    </h1>
                </div>
                
                <!-- Basic Information -->
                <group>
                    <group string="Incident Information">
                        <field name="incident_number" string="Incident Number" readonly="1"/>
                        <field name="incident_type" string="Incident Type" required="1"/>
                        <field name="severity" string="Severity" required="1"/>
                        <field name="site_id" string="Site" required="1"/>
                        <field name="client_id" string="Client" readonly="1"/>
                    </group>
                    <group string="Reporting Information">
                        <field name="reported_by" string="Reported By" required="1"/>
                        <field name="reported_at" string="Reported At" readonly="1"/>
                        <field name="incident_date" string="Incident Date" required="1"/>
                        <field name="incident_time" string="Incident Time" required="1"/>
                        <field name="assigned_to" string="Assigned To"/>
                    </group>
                </group>
                
                <!-- Incident Details -->
                <group string="Incident Details">
                    <field name="description" string="Description" required="1" 
                           widget="text" nolabel="1" placeholder="Enter detailed incident description"/>
                </group>
                
                <!-- Location and Environment -->
                <group>
                    <group string="Location Information">
                        <field name="location_details" string="Location Details"/>
                        <field name="weather_conditions" string="Weather Conditions"/>
                    </group>
                    <group string="Witnesses">
                        <field name="witnesses" string="Witnesses" widget="text"/>
                    </group>
                </group>
                
                <!-- Response and Resolution -->
                <group string="Response Information">
                    <group>
                        <field name="response_time" string="Response Time (minutes)" readonly="1"/>
                        <field name="resolution_time" string="Resolution Time (hours)" readonly="1"/>
                        <field name="actions_taken" string="Actions Taken" widget="text"/>
                    </group>
                    <group>
                        <field name="police_notified" string="Police Notified"/>
                        <field name="emergency_services_called" string="Emergency Services Called"/>
                        <field name="client_notified" string="Client Notified"/>
                    </group>
                </group>
                
                <!-- Resolution Information -->
                <group string="Resolution Information" invisible="status not in ['resolved', 'closed']">
                    <field name="resolution_notes" string="Resolution Notes" widget="text" nolabel="1"/>
                    <field name="follow_up_required" string="Follow-up Required"/>
                    <field name="follow_up_date" string="Follow-up Date" 
                           invisible="not follow_up_required"/>
                </group>
                
                <!-- Evidence and Documentation -->
                <notebook>
                    <page string="Photos">
                        <field name="photo_ids" widget="one2many">
                            <tree>
                                <field name="name" string="Photo Name"/>
                                <field name="photo" string="Photo" widget="image"/>
                                <field name="description" string="Description"/>
                                <field name="taken_at" string="Taken At"/>
                            </tree>
                        </field>
                    </page>
                    
                    <page string="Documents">
                        <field name="document_ids" widget="one2many">
                            <tree>
                                <field name="name" string="Document Name"/>
                                <field name="document" string="Document" widget="binary"/>
                                <field name="description" string="Description"/>
                                <field name="uploaded_at" string="Uploaded At"/>
                            </tree>
                        </field>
                    </page>
                    
                    <page string="Videos">
                        <field name="video_ids" widget="one2many">
                            <tree>
                                <field name="name" string="Video Name"/>
                                <field name="video" string="Video" widget="binary"/>
                                <field name="description" string="Description"/>
                                <field name="uploaded_at" string="Uploaded At"/>
                            </tree>
                        </field>
                    </page>
                </notebook>
            </sheet>
            
            <!-- Chatter -->
            <div class="oe_chatter">
                <field name="message_follower_ids" widget="mail_followers"/>
                <field name="activity_ids" widget="mail_activity"/>
                <field name="message_ids" widget="mail_thread"/>
            </div>
        </form>
    </field>
</record>
```

### Dashboard Views

#### 1. Main Dashboard View

```xml
<!-- Main Dashboard View -->
<record id="view_guard_dashboard" model="ir.ui.view">
    <field name="name">guard.dashboard</field>
    <field name="model">guard.dashboard</field>
    <field name="arch" type="xml">
        <dashboard string="GuardLink Dashboard">
            
            <!-- Key Metrics Row -->
            <view type="graph" string="Performance Metrics">
                <graph string="Performance Overview" type="bar">
                    <field name="active_guards" type="measure"/>
                    <field name="completed_shifts" type="measure"/>
                    <field name="reported_incidents" type="measure"/>
                    <field name="response_time" type="measure"/>
                </graph>
            </view>
            
            <!-- Recent Activity -->
            <view type="list" string="Recent Activity">
                <list string="Recent Activities" editable="false">
                    <field name="activity_type"/>
                    <field name="description"/>
                    <field name="timestamp"/>
                    <field name="status" widget="badge"/>
                </list>
            </view>
            
            <!-- Quick Actions -->
            <view type="kanban" string="Quick Actions">
                <kanban string="Quick Actions" class="o_kanban_mobile">
                    <field name="name"/>
                    <field name="action_type"/>
                    <field name="description"/>
                    <templates>
                        <t t-name="kanban-box">
                            <div class="oe_kanban_card oe_kanban_global_click">
                                <div class="oe_kanban_content">
                                    <div class="o_kanban_record_top">
                                        <div class="o_kanban_record_headings">
                                            <strong class="o_kanban_record_title">
                                                <field name="name"/>
                                            </strong>
                                            <div class="o_kanban_record_subtitle">
                                                <field name="description"/>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="o_kanban_record_bottom">
                                        <button name="action_execute" type="object" 
                                                class="btn btn-primary" 
                                                string="Execute"/>
                                    </div>
                                </div>
                            </div>
                        </t>
                    </templates>
                </kanban>
            </view>
            
        </dashboard>
    </field>
</record>
```

### Search Views

#### 1. Guard Search View

```xml
<!-- Guard Search View -->
<record id="view_guard_profile_search" model="ir.ui.view">
    <field name="name">guard.profile.search</field>
    <field name="model">guard.profile</field>
    <field name="arch" type="xml">
        <search string="Search Guards">
            
            <!-- Search Fields -->
            <field name="name" string="Guard Name"/>
            <field name="employee_id" string="Employee ID"/>
            <field name="email" string="Email"/>
            <field name="phone" string="Phone"/>
            <field name="site_ids" string="Site"/>
            <field name="skills_ids" string="Skill"/>
            
            <!-- Filters -->
            <filter string="Active Guards" name="active" 
                    domain="[('employment_status', '=', 'active')]"/>
            <filter string="Inactive Guards" name="inactive" 
                    domain="[('employment_status', '=', 'inactive')]"/>
            <filter string="High Performance" name="high_performance" 
                    domain="[('performance_score', '>=', 80)]"/>
            <filter string="Low Performance" name="low_performance" 
                    domain="[('performance_score', '&lt;', 60)]"/>
            
            <!-- Group By -->
            <group expand="0" string="Group By">
                <filter string="Employment Status" name="group_employment_status" 
                        context="{'group_by': 'employment_status'}"/>
                <filter string="Site" name="group_site" 
                        context="{'group_by': 'site_ids'}"/>
                <filter string="Performance Score" name="group_performance" 
                        context="{'group_by': 'performance_score'}"/>
            </group>
            
            <!-- Separator -->
            <separator/>
            
            <!-- Custom Filters -->
            <filter string="My Guards" name="my_guards" 
                    domain="[('user_id', '=', uid)]"/>
            <filter string="Guards with Incidents" name="with_incidents" 
                    domain="[('incident_count', '&gt;', 0)]"/>
            
        </search>
    </field>
</record>
```

### Mobile Views

#### 1. Mobile Guard Form View

```xml
<!-- Mobile Guard Form View -->
<record id="view_guard_profile_form_mobile" model="ir.ui.view">
    <field name="name">guard.profile.form.mobile</field>
    <field name="model">guard.profile</field>
    <field name="priority">1</field>
    <field name="arch" type="xml">
        <form string="Guard Profile" create="true" edit="true" delete="true">
            
            <!-- Mobile Header -->
            <header>
                <button name="action_check_in" type="object" 
                        string="Check In" class="btn-primary"
                        invisible="context.get('mobile_view') != 'checkin'"/>
                <button name="action_check_out" type="object" 
                        string="Check Out" class="btn-success"
                        invisible="context.get('mobile_view') != 'checkout'"/>
                <button name="action_report_incident" type="object" 
                        string="Report Incident" class="btn-warning"
                        invisible="context.get('mobile_view') != 'incident'"/>
            </header>
            
            <!-- Mobile Content -->
            <sheet>
                <!-- Basic Information -->
                <group>
                    <field name="name" string="Guard Name" readonly="1"/>
                    <field name="employee_id" string="Employee ID" readonly="1"/>
                    <field name="site_ids" string="Current Site" widget="many2many_tags"/>
                </group>
                
                <!-- Current Shift Information -->
                <group string="Current Shift" invisible="not context.get('current_shift')">
                    <field name="current_shift_id" string="Shift" readonly="1"/>
                    <field name="shift_start_time" string="Start Time" readonly="1"/>
                    <field name="shift_end_time" string="End Time" readonly="1"/>
                    <field name="shift_status" string="Status" widget="badge" readonly="1"/>
                </group>
                
                <!-- Quick Actions -->
                <group string="Quick Actions">
                    <button name="action_view_tasks" type="object" 
                            string="View Tasks" class="btn btn-block"/>
                    <button name="action_view_patrols" type="object" 
                            string="View Patrols" class="btn btn-block"/>
                    <button name="action_emergency" type="object" 
                            string="Emergency" class="btn btn-danger btn-block"/>
                </group>
                
            </sheet>
        </form>
    </field>
</record>
```

## View Best Practices

### Design Principles

1. **User Experience**
   - Design for intuitive navigation
   - Provide clear visual hierarchy
   - Use consistent styling and layout
   - Implement responsive design

2. **Accessibility**
   - Use proper ARIA labels
   - Ensure keyboard navigation
   - Provide alternative text for images
   - Use sufficient color contrast

3. **Performance**
   - Optimize view loading times
   - Use efficient field selection
   - Implement proper pagination
   - Minimize database queries

4. **Maintainability**
   - Use clear, descriptive view names
   - Implement consistent naming conventions
   - Document complex view logic
   - Use inheritance for common patterns

### View Inheritance

```xml
<!-- Base Form View -->
<record id="view_guard_base_form" model="ir.ui.view">
    <field name="name">guard.base.form</field>
    <field name="model">guard.base</field>
    <field name="arch" type="xml">
        <form string="Guard Base">
            <header>
                <field name="state" widget="statusbar"/>
            </header>
            <sheet>
                <div class="oe_title">
                    <h1>
                        <field name="name"/>
                    </h1>
                </div>
                <group>
                    <group>
                        <field name="create_uid" readonly="1"/>
                        <field name="create_date" readonly="1"/>
                    </group>
                    <group>
                        <field name="write_uid" readonly="1"/>
                        <field name="write_date" readonly="1"/>
                    </group>
                </group>
            </sheet>
        </form>
    </field>
</record>

<!-- Inherited View -->
<record id="view_guard_profile_form_inherit" model="ir.ui.view">
    <field name="name">guard.profile.form.inherit</field>
    <field name="model">guard.profile</field>
    <field name="inherit_id" ref="view_guard_base_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='name']" position="after">
            <field name="employee_id"/>
            <field name="email"/>
        </xpath>
        <xpath expr="//group[1]" position="inside">
            <field name="phone"/>
            <field name="mobile"/>
        </xpath>
    </field>
</record>
```

### Custom Widgets

```javascript
// Custom Progress Bar Widget
odoo.define('guardpro.ProgressBarWidget', function (require) {
    "use strict";
    
    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');
    
    var ProgressBarWidget = AbstractField.extend({
        template: 'guardpro.ProgressBarWidget',
        
        init: function () {
            this._super.apply(this, arguments);
        },
        
        _render: function () {
            this._super();
            var value = this.value || 0;
            var max = this.nodeOptions.max || 100;
            var percentage = Math.min((value / max) * 100, 100);
            
            this.$('.progress-bar').css('width', percentage + '%');
            this.$('.progress-text').text(value + '/' + max);
        }
    });
    
    fieldRegistry.add('progress_bar', ProgressBarWidget);
    return ProgressBarWidget;
});
```

### Responsive Design

```css
/* Mobile-first responsive design */
@media (max-width: 768px) {
    .o_form_view .o_form_sheet {
        padding: 10px;
    }
    
    .o_form_view .o_group {
        display: block;
    }
    
    .o_form_view .o_group .o_group_col_6 {
        width: 100%;
        margin-bottom: 10px;
    }
    
    .o_kanban_view .o_kanban_record {
        margin-bottom: 10px;
    }
    
    .o_list_view .o_list_table {
        font-size: 12px;
    }
}

@media (max-width: 480px) {
    .o_form_view .oe_title h1 {
        font-size: 18px;
    }
    
    .o_form_view .o_form_button {
        width: 100%;
        margin-bottom: 5px;
    }
    
    .o_kanban_view .o_kanban_record {
        padding: 10px;
    }
}
```

---

*GuardLink Views: Modern, Intuitive, and Responsive User Interfaces*