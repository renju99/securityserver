# 🚨 Sentry - Enterprise Security Operations Suite

<div align="center">

**Win premium guard contracts with an Odoo-native suite for mobile patrols, SLA automation, client portals, and analytics.**

[![Version](https://img.shields.io/badge/version-18.0.1.0.8-blue.svg)](https://github.com/renju99/custom_addons)
[![Odoo](https://img.shields.io/badge/odoo-18.0-green.svg)](https://www.odoo.com/)
[![License](https://img.shields.io/badge/license-LGPL--3-blue.svg)](LICENSE)

*Mobile-first security operations • Real-time GPS tracking • Automated compliance • Client portals • Analytics dashboards*

[📖 Documentation](INDEX.md) • [🚀 Quick Start](user-guide/01-introduction.md) • [📱 Mobile App](api/mobile-api.md) • [🔗 API](api/rest-api.md)

</div>

---

## 🎯 What is Sentry?

Sentry centralizes security guard field operations, compliance, and client reporting inside **Odoo 18 Community Edition**. The suite connects supervisors, control rooms, guards, and clients with real-time visibility, mobile-first workflows, and automated analytics.

Built for security companies, corporate security teams, and property managers who need enterprise-grade security operations without the complexity of traditional security software.

---

## ✨ Core Features

### 📱 Mobile-First Guard Experience
- **Progressive Web App** installable on iOS and Android with offline synchronization
- **GPS diagnostics**, location history, panic alerts, and live geofence monitoring
- **Patrol tour designer**, checkpoint map creator, optimized route planner, and bulk assignment wizards
- **Guard shift management** with swap approvals, availability planning, and attendance reconciliation

### 🏢 Control Room & Compliance
- **Incident lifecycle coverage**: reporting, investigation, escalation logs, SLA breach alerts, and client notifications
- **Visitor, contractor, package, key, and lost and found workflows** with automated reminders
- **Compliance audits, SOP knowledge base, emergency procedures, broadcast templates**, and audit-ready trails
- **Performance dashboards, analytics grids, KPI tracking**, and exportable PDF or Excel reports

### 🤖 Automation & Intelligence
- **18 scheduled actions** handling alerts, daily activity report generation, SLA calculations, credential renewals, and messaging
- **REST API endpoints, webhook framework, and portal enhancements** for external integrations
- **Odoo-native collaboration** with mail chatter, project tasks, HR employees, website slides eLearning, and portal

---

## 🏆 Latest Enhancements (v18.0.1.0.8)

### 🎯 2025 Enhancement Wave
- ✅ **Analytics Dashboards** - Real-time KPI tracking and performance metrics
- ✅ **Emergency Broadcast Suite** - Push notifications and emergency communication
- ✅ **Enhanced eLearning** - Comprehensive guard training modules
- ✅ **Security Audit Tooling** - Advanced compliance and audit automation
- ✅ **Biometric Integration** - Secure authentication and verification
- ✅ **CCTV Camera Management** - Live streaming and camera control
- ✅ **UAE/SIRA Compliance** - Dubai and SIRA standards integration

### 📊 Advanced Analytics
- **Live Guard View** with real-time GPS tracking
- **Performance Dashboards** with customizable KPIs
- **Incident Analytics** and trend analysis
- **SLA Performance Monitoring** with breach alerts
- **Client Feedback Analytics** and satisfaction tracking

---

## 👥 Who Uses Sentry?

### 🛡️ Security Companies
- **Guard management** and credential lifecycle
- **Shift scheduling** and conflict detection
- **Client billing** and contract management
- **Quality assurance** and performance monitoring
- **Multi-site operations** and centralized control

### 🏢 Corporate Security Teams
- **In-house guard teams** management
- **Facility security** operations
- **Compliance tracking** and reporting
- **Incident management** and investigation
- **Access control** and visitor management

### 🏠 Property Management
- **Residential security** for communities
- **Commercial building** security operations
- **Tenant services** and resident portals
- **Multi-site management** and reporting
- **Emergency response** coordination

---

## 🚀 Getting Started

<div align="center">

### ⚡ Quick Setup (30 minutes)

| Step | Task | Documentation |
|------|------|---------------|
| 1 | **Install Odoo 18** | [Installation Guide](user-guide/02-installation.md) |
| 2 | **Install Sentry Module** | [Configuration](user-guide/03-configuration.md) |
| 3 | **Add Security Guards** | [Guard Profiles](guards/profile_management.md) |
| 4 | **Configure Sites** | [Site Setup](sites/site_setup.md) |
| 5 | **Create First Shift** | [Shift Management](operations/shift_management.md) |

</div>

### 📱 Mobile Deployment
1. **Access the PWA** at `/guardpro/mobile` on any mobile device
2. **Install as app** from browser menu (Add to Home Screen)
3. **Login with guard credentials** and start operations
4. **Works offline** with automatic synchronization

---

## 📊 Feature Comparison

| Feature | Sentry | Traditional Software | Spreadsheets |
|---------|--------|---------------------|--------------|
| **Mobile App** | ✅ Native PWA | ❌ Expensive | ❌ None |
| **GPS Tracking** | ✅ Real-time | ⚠️ Limited | ❌ Manual |
| **Offline Mode** | ✅ Full sync | ❌ None | ❌ None |
| **Automation** | ✅ 18+ scheduled tasks | ⚠️ Basic | ❌ Manual |
| **Reporting** | ✅ 25+ PDF reports | ✅ Basic | ❌ Manual |
| **API Integration** | ✅ REST + Webhooks | ✅ Enterprise only | ❌ None |
| **Cost** | ✅ Odoo Community | ❌ $10k+/month | ❌ Time-intensive |
| **UAE Compliance** | ✅ SIRA Standards | ❌ Additional cost | ❌ Manual |

---

## 🛠️ Technical Specifications

### System Requirements
- **Odoo**: 18.0 Community Edition
- **Python**: 3.10 or higher
- **Database**: PostgreSQL 13+
- **Web Server**: Compatible with Odoo (nginx recommended)
- **Mobile**: iOS 12+, Android 8+ (PWA)

### Dependencies
```python
# Core Odoo modules
base, web, website, hr, project, contacts, mail, portal, auth_signup, website_slides

# Optional integrations
hr_attendance, maintenance
```

### External Dependencies
```python
markdown>=3.4.0        # Documentation rendering
cryptography>=41.0.0   # Biometric encryption
requests>=2.28.0       # API integrations
```

---

## 📚 Documentation & Resources

### 📖 Complete Documentation
- **[Full Documentation Index](INDEX.md)** - Complete guide
- **[User Guide](user-guide/)** - Step-by-step instructions
- **[API Reference](api/)** - Integration documentation
- **[Developer Guide](developer-guide/)** - Customization guide

### 🎥 Learning Resources
- **In-App Training** - Integrated eLearning modules
- **Video Tutorials** - Available in application
- **Knowledge Base** - Integrated help system
- **SOP Guides** - Printable standard procedures

### 💬 Support & Community
- **Email Support**: support@sentry.app
- **Phone Support**: 1-800-SENTRY
- **GitHub Issues**: [Report bugs](https://github.com/renju99/custom_addons/issues)
- **Documentation**: [Report issues](https://github.com/renju99/custom_addons/issues)

---

## 🔄 Version History

### v18.0.1.0.8 (January 2026)
- 🚀 **Analytics Dashboards** - Real-time performance monitoring
- 📢 **Emergency Broadcast** - Push notification system
- 🎓 **Enhanced eLearning** - Comprehensive training modules
- 🔒 **Biometric Security** - Advanced authentication
- 📹 **CCTV Integration** - Camera management and streaming
- 🇦🇪 **UAE Compliance** - SIRA standards implementation

### v18.0.1.0.6 (November 2025)
- 📋 **Knowledge Base** - SOP and emergency procedures
- 🏷️ **Enhanced Tagging** - Better organization and search
- 📄 **Advanced Reporting** - New PDF templates and exports

### v18.0.1.0.2 (October 2025)
- 🎯 **Performance Tracking** - KPI dashboards and analytics
- 📱 **Mobile Enhancements** - Improved PWA experience
- 🔄 **Sync Improvements** - Better offline synchronization

---

## 🏆 Success Stories

> *"Sentry transformed our security operations. We went from paper-based reporting to real-time mobile operations in just 2 weeks."*
> — **Ahmed Al-Mansoori**, Security Director, Dubai Properties

> *"The ROI was immediate. Reduced overtime by 30% and improved response times by 50%."*
> — **Sarah Johnson**, Operations Manager, SecureCorp UAE

> *"Perfect for UAE market requirements. SIRA compliance built-in."*
> — **Mohammed Al-Rashid**, Compliance Officer, Emirates Security

---

## 📞 Contact & Support

<div align="center">

**Ready to transform your security operations?**

[![Contact Us](https://img.shields.io/badge/Contact_Us-017e84?style=for-the-badge&logo=mail.ru&logoColor=white)](mailto:support@sentry.app)
[![Documentation](https://img.shields.io/badge/Documentation-017e84?style=for-the-badge&logo=read-the-docs&logoColor=white)](INDEX.md)
[![GitHub](https://img.shields.io/badge/GitHub-017e84?style=for-the-badge&logo=github&logoColor=white)](https://github.com/renju99/custom_addons)

**Sentry Support Team**  
📧 support@sentry.app  
📞 1-800-SENTRY  
🌐 https://sentry.proptechme.com/

</div>

---

<div align="center">

**Built with ❤️ for the security industry**  
*Empowering security professionals with enterprise-grade technology*

**Version 18.0.1.0.8** • **Last Updated: January 20, 2026** • **License: LGPL-3**

</div>
