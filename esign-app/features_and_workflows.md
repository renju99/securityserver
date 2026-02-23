# eSign Application - Features & Workflows Documentation

## 1. Executive Summary
The **eSign Application** is a comprehensive, enterprise-grade document generation and electronic signature platform. Built to digitize, streamline, and secure internal approval processed, it allows employees to request, review, and digitally sign documents utilizing dynamic multi-stage approval workflows.

## 2. Core Features

### 2.1. Authentication and Role-Based Access Control
*   **Single Sign-On (SSO):** Integration with Microsoft Entra ID allows users to securely log in using their organizational Microsoft accounts.
*   **Role-Based Access Control (RBAC):** Users are assigned specific roles (e.g., Admin, User) and scopes (global, departmental, or self-only) which dictate their ability to manage master data, configure templates, or view organization-wide document requests.
*   **Profile Management:** Employees can manage their job titles and save default/secure digital signatures and initials within their profiles for quick application to future requests.

### 2.2. Master Data Management
*   **Department Configuration:** Admins can structure the organizational hierarchy securely by defining departments.
*   **Document Types:** Centralized lists of standard institutional forms (e.g., Capex, Leave Requests, Travel Authorizations).

### 2.3. Document Template Management
The system supports two distinct methods for creating document templates:
*   **PDF Templates:** Admin users can import pre-formatted PDF files and overlay drag-and-drop form fields natively onto the document specifying exactly where text data, dates, and different types of signatures should map during the signing process.
*   **Dynamic Visual Templates:** Administrators can construct dynamic JSON-based layout templates offering high flexibility in sequence structure and document block generation.

### 2.4. Flexible Approval Workflow Engine
*   **Custom Departmental Workflows:** For any specific Department and Document Type, administrators can establish dynamic chains of command mapping out necessary sequence of "Approvers" and "Signers."
*   **Strict Sequential Chain:** Approvals are strictly enforced in sequence, ensuring that Step 2 cannot sign prior to Step 1's authorization.

### 2.5. Request Lifecycle Management
*   **Draft Generation:** Users can pre-fill document information and generate PDF previews simulating the finalized structure prior to formal submission.
*   **Real-time PDF Building:** The application dynamically generates new PDFs by integrating template rules, the requester's form data, and the sequence of workflow participants before locking the document.
*   **Embedded Electronic Signatures:** Utilizing the robust backend processing, mathematical coordinates dictating signature placeholders receive authentic user signatures—which are permanently embedded as verifiable image assets onto the final locked PDF file.

### 2.6. Email Notifications & Communication
*   **Automated Triggers:** Once a document finishes a step (e.g., submission, signing, final completion), customized context-aware notifications containing secure viewing links are dispatched to the next individual in the workflow hierarchy.
*   **Dedicated SMTP Engine:** The application is highly resilient, built with dedicated integrations to enterprise SMTP relays (like SendGrid), configurable entirely through the intuitive Admin UI. Includes deep email logging for traceability.

### 2.7. Archiving and Storage
*   **Azure Blob Storage Integration:** Finalized PDFs, document drafts, and base templates are cryptographically linked to secure Azure Blob Storage containers utilizing fine-grained Shared Access Signatures (SAS) ensuring data resilience and security.
*   **Safe Document Archiving:** Approved documents can be cleanly archived reducing user dashboard clutter but preserving legal and auditing trails over time.

---

## 3. Key System Workflows

### Workflow 1: Admin Configuration (One-Time Setup)
1.  **System Entry:** Admin logs into the portal using Microsoft SSO.
2.  **Organization Mapping:** Admin defines the **Departments** and **Document Types** in "Master Data".
3.  **Template Creation:** Admin uploads fillable PDFs or builds Visual documents; they dynamically map data fields and drag signature placement boxes to their required coordinates onto the digital paper.
4.  **Workflow Mapping:** Admin assigns a sequential approval list based on roles (e.g., 1. Manager -> 2. HR -> 3. VP) tied exclusively to that specified Template Type.
5.  **SMTP Setup:** Admin connects standard email distribution servers.

### Workflow 2: Request Submission (Standard User)
1.  **Initiation:** An employee visits the portal and selects "New Request".
2.  **Selection:** Chooses their specific "Department" and the desired "Document Type".
3.  **Data Input:** They fill in the dynamic web-form attributes related exclusively to that document type.
4.  **Preview (Draft State):** The system dynamically binds that data securely, outputting a watermarked visualization of the expected PDF.
5.  **Submission:** The employee submits. The backend permanently locks the initial document structure state and alerts the first Approver in the sequential chain.

### Workflow 3: Sequential Document Approval
1.  **Notification:** The designated Approver receives an automated Email outlining the request alongside a secure access link.
2.  **Review:** Approver loads the eSign portal. The system verifies their Identity & Role matches the required approval step for that document ID.
3.  **Signing:** The approver opts to use their Saved Profile Signature or draws a new one utilizing the digital signature pad.
4.  **PDF Manipulation:** The backend intercepts the signature, injects it precisely over the required visual coordinate mapped previously, locks the metadata, and updates Azure Cloud storage.
5.  **Chain Advancement:** Upon successful signing, the portal advances to Approval Step `N+1` automatically pinging the next authority, or, if no steps remain, it marks the document "Approved" and notifies the originator.

## 4. Technical Architecture Stack
*   **Frontend User Interface:** Modern, highly responsive React/Next.js infrastructure leveraging TailwindCSS for styling and React-PDF for high fidelity in-browser document rendering. Native touch-support mapped for the signature drawing logic.
*   **Backend Server Logic:** High-concurrency Python server running FastAPI. Includes deep integrations to **SQLAlchemy/SQLite** (Data Layer), **PyMuPDF/Fitz** (Raw Document PDF manipulation core), and **Azure Storage** (File Storage).

---
*Authorized for internal review and management capability assessments.*
