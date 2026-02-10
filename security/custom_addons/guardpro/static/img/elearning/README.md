# GuardPro eLearning Images

This directory contains screenshots and images used in the GuardPro eLearning courses.

## Available Images

| File | Description | Used In |
|------|-------------|---------|
| `01_login_page.png` | GuardPro login screen | Fundamentals - Module 2: System Navigation |
| `02_main_dashboard.png` | Main application dashboard | Fundamentals - Module 2: System Navigation |
| `03_app_menu.png` | Application menu showing all modules | Fundamentals - Module 2: System Navigation |
| `04_guardpro_operations_dashboard.png` | GuardPro Operations Dashboard with live metrics | Fundamentals - Module 4: Dashboard Overview |
| `05_operations_menu.png` | Operations dropdown menu | Fundamentals - Module 5: Basic Operations |
| `06_incidents_emergency_menu.png` | Incidents & Emergency submenu | N/A (Available for future use) |
| `07_guard_management_tab.png` | Guard Management dashboard tab | Supervisor Ops - Module 2: Shift Management |
| `08_site_coverage_tab.png` | Site Coverage analytics view | Manager Advanced - Module 2: Analytics and Reporting |
| `09_incident_management_tab.png` | Incident Management dashboard | Supervisor Ops - Module 3: Incident Investigation |
| `10_tours_patrols_tab.png` | Tours & Patrols dashboard | Guard Operations - Module 4: Security Tours |
| `11_shifts_calendar_view.png` | Weekly shifts calendar view | Guard Operations - Module 2: Shift Check-In/Check-Out |
| `12_incident_reports_kanban.png` | Incident Reports kanban board | Guard Operations - Module 3: Incident Reporting |

## Image Guidelines

### Usage in XML Files

Images are referenced in the elearning slide XML files using the following format:

```xml
<field name="description">
    &lt;h3&gt;Dashboard Overview&lt;/h3&gt;
    &lt;img src="/guardpro/static/img/elearning/04_guardpro_operations_dashboard.png" 
         alt="GuardPro Operations Dashboard" 
         style="max-width: 100%; height: auto; margin: 15px 0; border: 1px solid #ddd; border-radius: 4px;"/&gt;
</field>
```

### Best Practices

1. **Alt Text**: Always include descriptive alt text for accessibility
2. **Responsive**: Use `max-width: 100%` and `height: auto` for responsive images
3. **Spacing**: Add margin (e.g., `margin: 15px 0`) for visual breathing room
4. **Border**: Use subtle borders to separate images from content
5. **File Naming**: Use descriptive, sequential numbering (e.g., `01_`, `02_`)

## Courses Using Images

### 1. GuardPro Fundamentals (GP-101)
- Module 2: System Navigation (3 images)
- Module 4: Dashboard Overview (1 image)
- Module 5: Basic Operations (1 image)

### 2. Security Guard Field Operations (GP-201)
- Module 2: Shift Check-In/Check-Out (1 image)
- Module 3: Incident Reporting (1 image)
- Module 4: Security Tours and Checkpoints (1 image)

### 3. Supervisor Operations Management (GP-301)
- Module 2: Shift Management (1 image)
- Module 3: Incident Investigation (1 image)

### 4. Security Manager Advanced (GP-401)
- Module 2: Analytics and Reporting (1 image)

### 5. System Administration (GP-501)
- TBD - Add images as course content develops

### 6. Client Portal Access (GP-601)
- TBD - Add images as course content develops

## Adding New Images

When adding new screenshots:

1. **Capture**: Take full-page screenshots at 1920x1080 or higher
2. **Save**: Use PNG format for clarity
3. **Name**: Follow naming convention: `##_descriptive_name.png`
4. **Document**: Update this README with image details
5. **Reference**: Add to appropriate slide XML files

## Maintenance

- Review images quarterly to ensure they match current UI
- Update screenshots when major UI changes are deployed
- Remove unused images to keep directory clean
- Optimize image sizes if load times become an issue

---

**Last Updated**: October 13, 2025  
**Total Images**: 12  
**Courses with Images**: 4 of 6  

