# GuardPro E-Learning Data Files

This directory contains all e-learning course data for the GuardPro Security Management System - focused on security guard training and management.

## Files Overview

| File | Purpose | Status |
|------|---------|--------|
| `elearning_courses_data.xml` | Course definitions, tags, and metadata | ✅ Complete |
| `elearning_slides_fundamentals.xml` | Course 1: GuardPro Fundamentals (2 hrs) | ✅ Complete |
| `elearning_slides_guard_operations.xml` | Course 2: Guard Field Operations (3 hrs) | ✅ Complete |
| `elearning_slides_supervisor_ops.xml` | Course 3: Supervisor Operations (4 hrs) | ✅ Complete |
| `elearning_slides_basic_security.xml` | Course 4: Basic Security Training (3 hrs) | ✅ Complete |
| `elearning_slides_emergency_response.xml` | Course 5: Emergency Response & Procedures (2.5 hrs) | ✅ Complete |
| `elearning_slides_fire_safety.xml` | Course 6: Fire Safety & Prevention (2 hrs) | ✅ Complete |
| `elearning_slides_first_aid.xml` | Course 7: First Aid & CPR (3 hrs) | ✅ Complete |
| `elearning_slides_conflict_resolution.xml` | Course 8: Conflict Resolution & De-escalation (2 hrs) | ✅ Complete |
| `elearning_slides_customer_service.xml` | Course 9: Customer Service for Guards (1.5 hrs) | ✅ Complete |
| `elearning_slides_legal_compliance.xml` | Course 10: Legal & Compliance Training (2.5 hrs) | ✅ Complete |
| `elearning_slides_patrol_techniques.xml` | Course 11: Patrol & Observation Techniques (2 hrs) | ✅ Complete |
| `elearning_slides_report_writing.xml` | Course 12: Report Writing & Documentation (1.5 hrs) | ✅ Complete |
| `guard_training_courses_data.xml` | Additional guard training courses | ✅ Complete |
| **`elearning_slides_sira_compliance.xml`** | **🆕 SIRA Compliance & Dubai Regulations (4 hrs)** | ✅ **New** |
| **`elearning_slides_uae_culture.xml`** | **🆕 UAE Culture & Professional Conduct (3 hrs)** | ✅ **New** |
| **`elearning_slides_dubai_operations.xml`** | **🆕 Dubai Security Operations & Sites (4.5 hrs)** | ✅ **New** |
| **`elearning_slides_advanced_operations.xml`** | **🆕 Advanced Security Operations & Tech (5 hrs)** | ✅ **New** |

## Course Structure

Each slide XML file contains:
- **Slide/Module Definitions**: Content presentations (document, infographic)
- **Quiz Slides**: Knowledge checks and assessments
- **Questions**: Multiple choice questions for each quiz
- **Answers**: Correct and incorrect answer options
- **Metadata**: Completion times, sequences, descriptions

## Data Load Order

These files are loaded in the following order (as defined in `__manifest__.py`):

1. `elearning_courses_data.xml` - Creates the 12 courses
2. `elearning_slides_fundamentals.xml` - Populates Course 1
3. `elearning_slides_guard_operations.xml` - Populates Course 2
4. `elearning_slides_supervisor_ops.xml` - Populates Course 3
5. `elearning_slides_basic_security.xml` - Populates Course 4
6. `elearning_slides_emergency_response.xml` - Populates Course 5
7. `elearning_slides_fire_safety.xml` - Populates Course 6
8. `elearning_slides_first_aid.xml` - Populates Course 7
9. `elearning_slides_conflict_resolution.xml` - Populates Course 8
10. `elearning_slides_customer_service.xml` - Populates Course 9
11. `elearning_slides_legal_compliance.xml` - Populates Course 10
12. `elearning_slides_patrol_techniques.xml` - Populates Course 11
13. `elearning_slides_report_writing.xml` - Populates Course 12

## Content Summary

### Total Training Package
- **Courses**: 16 (12 general + 4 Dubai-specific)
- **Modules**: 52+ modules across all courses
- **Quizzes**: 52+ assessments
- **Total Duration**: 45.5 hours
- **Questions**: 170+ across all courses

### Dubai-Specific Training (NEW! 🆕)
- **SIRA Compliance Courses**: 4 courses
- **Dubai Operations Focus**: Site-specific procedures for Dubai
- **UAE Cultural Training**: Arabic language, customs, etiquette
- **Advanced Technology**: CCTV, access control, biometrics
- **Total Dubai Content**: 16.5 hours

### Course Breakdown

**Course 1: GuardPro Fundamentals (GP-101)**
- Target: All users
- Duration: 2 hours
- Mandatory: ✅ Yes
- Pass Required: 80%
- Focus: System basics and navigation

**Course 2: Security Guard Field Operations (GP-201)**
- Target: Security guards
- Duration: 3 hours
- Mandatory: ✅ Yes
- Pass Required: 80%
- Focus: Mobile app, incidents, tours, emergencies

**Course 3: Supervisor Operations Management (GP-301)**
- Target: Supervisors
- Duration: 4 hours
- Mandatory: ❌ No
- Pass Required: 85%
- Focus: Leadership, shift management, investigations

**Course 4: Basic Security Training (GP-401)**
- Target: All security guards
- Duration: 3 hours
- Mandatory: ✅ Yes
- Pass Required: 80%
- Focus: Security fundamentals, access control, professionalism

**Course 5: Emergency Response & Procedures (GP-501)**
- Target: All security guards
- Duration: 2.5 hours
- Mandatory: ✅ Yes
- Pass Required: 85%
- Focus: Emergency protocols, evacuations, medical emergencies

**Course 6: Fire Safety & Prevention (GP-601)**
- Target: All security guards
- Duration: 2 hours
- Mandatory: ✅ Yes
- Pass Required: 85%
- Focus: Fire safety, detection, extinguisher use

**Course 7: First Aid & CPR (GP-701)**
- Target: All security guards
- Duration: 3 hours
- Mandatory: ✅ Yes
- Pass Required: 85%
- Validity: 24 months (requires renewal)
- Focus: First aid, CPR, medical emergencies

**Course 8: Conflict Resolution & De-escalation (GP-801)**
- Target: All security guards
- Duration: 2 hours
- Mandatory: ✅ Yes
- Pass Required: 80%
- Focus: De-escalation techniques, conflict management

**Course 9: Customer Service for Security Guards (GP-901)**
- Target: Security guards
- Duration: 1.5 hours
- Mandatory: ❌ No
- Pass Required: 75%
- Focus: Professional customer service, communication

**Course 10: Legal & Compliance Training (GP-1001)**
- Target: All security guards
- Duration: 2.5 hours
- Mandatory: ✅ Yes
- Pass Required: 85%
- Focus: Legal authority, rights, liability, documentation

**Course 11: Patrol & Observation Techniques (GP-1101)**
- Target: All security guards
- Duration: 2 hours
- Mandatory: ✅ Yes
- Pass Required: 80%
- Focus: Patrol methods, observation skills, suspicious activity

**Course 12: Report Writing & Documentation (GP-1201)**
- Target: All security guards
- Duration: 1.5 hours
- Mandatory: ✅ Yes
- Pass Required: 80%
- Focus: Professional report writing, incident documentation

### 🆕 Dubai & SIRA Specific Courses

**Course 13: SIRA Compliance & Dubai Security Regulations (SIRA-101)**
- Target: All Dubai-based security guards
- Duration: 4 hours
- Mandatory: ✅ Yes (Dubai operations)
- Pass Required: 90%
- Validity: 12 months
- Focus: SIRA licensing, UAE laws, professional standards, Dubai emergency services

**Course 14: UAE Culture & Professional Conduct (UAE-101)**
- Target: All Dubai-based security personnel
- Duration: 3 hours
- Mandatory: ✅ Yes (Dubai operations)
- Pass Required: 85%
- Validity: 24 months
- Focus: UAE culture, Islamic practices, Arabic language basics, multicultural service

**Course 15: Dubai Security Operations & Site-Specific Procedures (DXB-201)**
- Target: All Dubai-based security guards
- Duration: 4.5 hours
- Mandatory: ✅ Yes (Dubai operations)
- Pass Required: 85%
- Validity: 12 months
- Focus: Mall security, residential communities, commercial buildings, events, climate

**Course 16: Advanced Security Operations & Technology (ADV-301)**
- Target: Experienced guards, supervisors, specialists
- Duration: 5 hours
- Mandatory: ❌ No (Advanced/Optional)
- Pass Required: 85%
- Validity: 24 months
- Focus: CCTV systems, access control, alarms, close protection, cybersecurity

## Training Categories

Courses are organized by category:
- **Basic Training**: Fundamental guard operations (Courses 1, 2, 4, 8, 11, 12)
- **Advanced Training**: Supervisory and management (Course 3)
- **Emergency Response**: Emergency procedures (Course 5)
- **Health & Safety**: Fire safety and first aid (Courses 6, 7)
- **Customer Service**: Professional interaction (Course 9)
- **Legal & Compliance**: Legal requirements (Course 10)
- **🆕 Dubai & SIRA**: Dubai-specific training (Courses 13, 14, 15)
- **🆕 Advanced Technology**: Specialized operations (Course 16)

## Mandatory Training

**New guards must complete (9 courses):**
1. GuardPro Fundamentals ✅
2. Security Guard Field Operations ✅
3. Basic Security Training ✅
4. Emergency Response & Procedures ✅
5. Fire Safety & Prevention ✅
6. First Aid & CPR ✅
7. Conflict Resolution & De-escalation ✅
8. Legal & Compliance Training ✅
9. Patrol & Observation Techniques ✅
10. Report Writing & Documentation ✅

**Total mandatory training: 24 hours**

**Optional training:**
- Customer Service for Security Guards
- Supervisor Operations Management (for supervisors only)

---

### 🆕 Dubai-Based Guards Additional Requirements

**In addition to the above, Dubai-based guards must complete:**
1. SIRA Compliance & Dubai Security Regulations ✅ (4 hours)
2. UAE Culture & Professional Conduct ✅ (3 hours)
3. Dubai Security Operations & Site-Specific Procedures ✅ (4.5 hours)

**Total Dubai-specific mandatory: 11.5 hours**  
**Grand Total for Dubai Guards: 35.5 hours**

**Optional Advanced Training:**
- Advanced Security Operations & Technology (5 hours)

## Deployment

To deploy these courses:

```bash
cd /home/ranjith/odoo
./odoo-bin -c odoo.conf -d your_database_name -u guardpro --stop-after-init
```

## Modification Guidelines

When editing these files:

1. **Maintain XML Structure**: Follow Odoo's slide.slide model structure
2. **Unique IDs**: Each record must have a unique `id` attribute
3. **Sequences**: Keep sequence numbers ordered (10, 11, 20, 21, etc.)
4. **HTML Encoding**: Use `&lt;` for `<`, `&gt;` for `>`, `&amp;` for `&`
5. **References**: Use `ref="model_id"` for relationships
6. **Completion Time**: In decimal hours (e.g., 0.25 = 15 minutes)

## Content Types

### Slide Categories
- **document**: Text-based learning content
- **infographic**: Visual content and summaries
- **quiz**: Knowledge assessments

### Quiz Structure
```xml
<record id="quiz_id" model="slide.slide">
  <field name="slide_category">quiz</field>
  <!-- Quiz definition -->
</record>

<record id="question_id" model="slide.question">
  <field name="slide_id" ref="quiz_id"/>
  <!-- Question definition -->
</record>

<record id="answer_id" model="slide.answer">
  <field name="question_id" ref="question_id"/>
  <field name="is_correct">True/False</field>
  <!-- Answer definition -->
</record>
```

## Dependencies

These data files require:
- Odoo 18 Community Edition
- `website_slides` module (eLearning)
- GuardPro module base installation

## Maintenance

**Last Updated**: November 3, 2025  
**Version**: 3.0 🆕 **Dubai Edition**  
**Status**: Production Ready  
**Focus**: Guard Training & Management + Dubai/SIRA Compliance  
**Maintained By**: GuardPro Development Team

### Recent Updates (v3.0 - November 3, 2025)
- ✅ Added SIRA Compliance & Dubai Security Regulations course
- ✅ Added UAE Culture & Professional Conduct course  
- ✅ Added Dubai Security Operations & Site-Specific Procedures course
- ✅ Added Advanced Security Operations & Technology course
- ✅ 16.5 hours of new Dubai-specific content
- ✅ 50+ Arabic phrases for security personnel
- ✅ Dubai emergency services protocols
- ✅ CCTV, access control, and alarm systems training
- ✅ Close protection and VIP security modules

## Notes

- All content marked with `noupdate="1"` will not be updated on module upgrade
- To force content update, use `noupdate="0"` or delete records from database first
- Content is in English; translations can be added via Odoo's translation system
- Quiz questions can be extended by adding more question/answer records
- All non-relevant courses (System Admin, Manager Advanced, Client Portal) have been removed

## Course Certificates

All mandatory courses issue certificates valid for 12 months (except First Aid - 24 months).
Guards must renew certifications before expiry to maintain compliance.

## Future Enhancements

Completed in v3.0:
- [✅] Dubai-specific training content
- [✅] SIRA compliance courses
- [✅] UAE culture and Arabic language training
- [✅] Advanced technology training (CCTV, access control, alarms)
- [✅] Close protection and VIP security training

Planned additions:
- [ ] Video content for each course
- [ ] Downloadable PDF resources
- [ ] Interactive scenarios and simulations
- [ ] Arabic language translations for all courses
- [ ] Additional specialized courses (K9 handling, Maritime security, Aviation security)
- [ ] Mobile-optimized content delivery
- [ ] Virtual Reality (VR) training modules
- [ ] Practical field assessment integration
