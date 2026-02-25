'use client';

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';

const API_BASE_URL = '/api';
import Link from 'next/link';
import SignatureCanvas from 'react-signature-canvas';
import { PublicClientApplication } from '@azure/msal-browser';
import PdfFiller from '../components/PdfFiller';

// Modular Components
import WorkflowStepper from '../components/Shared/WorkflowStepper';
import RequestTable from '../components/Dashboard/RequestTable';
import RequestDetailModal from '../components/Requests/RequestDetailModal';
import AuditLogViewer from '../components/Admin/AuditLogViewer';

// Shared Types
import {
  User,
  DocumentRequest,
  WorkflowConfig,
  PdfTemplateResponse,
  EmailConfig,
  EmailLog,
  DynamicTemplate,
  MasterData
} from '../types';

// MSAL Configuration
const msalConfig = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || '00000000-0000-0000-0000-000000000000', // Placeholder
    authority: `https://login.microsoftonline.com/${process.env.NEXT_PUBLIC_AZURE_TENANT_ID || 'common'}`,
    redirectUri: typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000',
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
};

const msalInstance = new PublicClientApplication(msalConfig);

// Define types for our data structure


const CAPEX_SECTIONS = [
  {
    title: "Header Information",
    fields: ['requesting_division', 'branch', 'request_date']
  },
  {
    title: "Item Details",
    fields: [
      'item_1_description', 'item_1_amount', 'item_1_date_required', 'is_item_1_budgeted_yes_no',
      'item_2_description', 'item_2_amount', 'item_2_date_required', 'is_item_2_budgeted_yes_no',
      'item_3_description', 'item_3_amount', 'item_3_date_required', 'is_item_3_budgeted_yes_no',
      'item_4_description', 'item_4_amount', 'item_4_date_required', 'is_item_4_budgeted_yes_no',
      'item_5_description', 'item_5_amount', 'item_5_date_required', 'is_item_5_budgeted_yes_no',
    ]
  },
  {
    title: "Justification",
    fields: ['staff_name', 'justification']
  }
];

// Sidebar nav item helper
const NavItem = ({ tab, activeTab, setActiveTab, setIsSidebarOpen, label, icon }: {
  tab: string;
  activeTab: string;
  setActiveTab: (tab: any) => void;
  setIsSidebarOpen: (open: boolean) => void;
  label: string;
  icon: React.ReactNode
}) => (
  <button
    onClick={() => {
      setActiveTab(tab as any);
      setIsSidebarOpen(false); // Close sidebar on mobile after clicking
    }}
    className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-md transition-all ${activeTab === tab
      ? 'bg-indigo-50 text-indigo-700 border-l-4 border-indigo-600 pl-3'
      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 border-l-4 border-transparent pl-3'
      }`}
  >
    <span className="w-5 h-5 flex-shrink-0">{icon}</span>
    {label}
  </button>
);

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'template' | 'requests' | 'settings' | 'admin'>('requests');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Master data states
  const [departments, setDepartments] = useState<MasterData[]>([]);
  const [docTypes, setDocTypes] = useState<MasterData[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [adminSubTab, setAdminSubTab] = useState<'users' | 'master' | 'email' | 'logs'>('users');
  const [isUserDetailOpen, setIsUserDetailOpen] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [emailLogs, setEmailLogs] = useState<EmailLog[]>([]);

  // Email Config State
  const [emailConfig, setEmailConfig] = useState<EmailConfig>({
    id: 0, smtp_server: 'smtp.sendgrid.net', smtp_port: 587, username: 'apikey', from_email: '', from_name: '', encryption: 'tls',
    imap_server: '',
    imap_port: 993,
    imap_ssl: true
  });

  // Initialize MSAL
  useEffect(() => {
    msalInstance.initialize().catch(console.error);
  }, []);
  const [emailPassword, setEmailPassword] = useState(''); // Separate state for security
  const [imapPassword, setImapPassword] = useState('');
  const [testEmail, setTestEmail] = useState('');

  // Admin Form States
  const [newDeptName, setNewDeptName] = useState('');
  const [newDocTypeName, setNewDocTypeName] = useState('');
  const [newUser, setNewUser] = useState({
    email: '',
    full_name: '',
    job_position: '',
    password: '',
    role: 'User' as 'User' | 'Admin',
    access_scope: 'global' as 'global' | 'department' | 'own',
    permissions: { departments: [] as string[] }
  });
  const [editingUserId, setEditingUserId] = useState<number | null>(null);

  // States
  const [department, setDepartment] = useState<string>('');
  const [docType, setDocType] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>('');

  // Template State
  const [templates, setTemplates] = useState<string[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [generationStatus, setGenerationStatus] = useState<string>('');
  const [schema, setSchema] = useState<string[]>([]);

  // Requests State
  const [requests, setRequests] = useState<DocumentRequest[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<DocumentRequest | null>(null);
  const [selectedRequestIds, setSelectedRequestIds] = useState<number[]>([]);

  // Settings State
  const [workflowConfigs, setWorkflowConfigs] = useState<WorkflowConfig[]>([]);
  const [editWorkflow, setEditWorkflow] = useState<WorkflowConfig>({ department: 'IT', doc_type: 'SLA', approvers: [], signers: [] });
  // Common State
  const [sasUrl, setSasUrl] = useState<string>('');
  const [dynamicTemplates, setDynamicTemplates] = useState<DynamicTemplate[]>([]);
  const [pdfTemplates, setPdfTemplates] = useState<PdfTemplateResponse[]>([]);

  // Signature State
  const sigCanvas = useRef<any>(null);
  const [isSigningOpen, setIsSigningOpen] = useState(false);
  const [signingComment, setSigningComment] = useState("");
  const [signingApprovalId, setSigningApprovalId] = useState<number | null>(null);
  const [isSigning, setIsSigning] = useState(false);
  const [requestSubTab, setRequestSubTab] = useState<'pending' | 'signed'>('pending');
  const [useSavedSignature, setUseSavedSignature] = useState(false);
  const [shouldSaveSignature, setShouldSaveSignature] = useState(false);
  const [sigMethod, setSigMethod] = useState<'draw' | 'image'>('draw');
  const [sigType, setSigType] = useState<'full' | 'initial'>('full');
  const [uploadedSig, setUploadedSig] = useState<string | null>(null);
  const [pdfFileUrl, setPdfFileUrl] = useState<string | null>(null);
  const [supportingDocs, setSupportingDocs] = useState<{ name: string; url: string; size: number }[]>([]);
  const [isUploadingSupport, setIsUploadingSupport] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<{ name: string; url: string } | null>(null);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const hiddenPdfInputRef = useRef<HTMLInputElement>(null);

  // Derived current flow from configs + hardcoded default fallback
  const getCurrentFlow = () => {
    // 1. Check if there's a specialized PDF Template with placement configs for this Dept/Type
    const pdfTpl = pdfTemplates.find(p => p.department === department && p.doc_type === docType);
    if (pdfTpl && pdfTpl.form_fields && pdfTpl.form_fields.length > 0) {
      // Extract unique assignees from the fields, keeping order if possible
      const assignees: string[] = [];
      pdfTpl.form_fields.forEach(f => {
        if (f.assignee && !assignees.includes(f.assignee)) {
          assignees.push(f.assignee);
        }
      });
      if (assignees.length > 0) return { approvers: assignees, signers: [], source: 'PDF Template Fields' };
    }

    const found = workflowConfigs.find(w => w.department === department && w.doc_type === docType);
    if (found) return { approvers: found.approvers, signers: found.signers, source: 'Global Workflow' };
    // Fallback defaults
    return { approvers: ["Manager (Default)"], signers: [], source: 'Default' };
  };

  const currentFlow = department && docType ? getCurrentFlow() : null;

  const visibleDepartments = useMemo(() => {
    if (user?.role === 'Admin' || user?.access_scope === 'global') return departments;
    const allowedDepts = user?.permissions?.departments || [];
    if (allowedDepts.length === 0) return [];
    return departments.filter(d => allowedDepts.includes(d.name));
  }, [departments, user]);

  const visibleTemplates = useMemo(() => {
    if (!department) return [];

    // Filter templates grouped by their association
    return templates.filter(tName => {
      // Admins and Global users see everything in the selected department
      // But we still filter by the *selected* department.

      // 1. Check PDF Templates mapping
      const pdfTpl = pdfTemplates.find(p => p.name === tName);
      if (pdfTpl && pdfTpl.department) {
        return pdfTpl.department === department;
      }

      // 2. Check Dynamic Templates mapping
      const dynTpl = dynamicTemplates.find(d => d.name === tName);
      if (dynTpl && dynTpl.category) {
        return dynTpl.category === department;
      }

      // If it's a generic blob with no department mapping
      // Only Admins (or maybe global users) see unassociated templates?
      // Usually unassociated templates are "drafts" or system templates.
      return user?.role === 'Admin' || user?.access_scope === 'global';
    });
  }, [templates, pdfTemplates, dynamicTemplates, department, user]);

  useEffect(() => {
    if (selectedTemplate) {
      const pdfTpl = pdfTemplates.find(p => p.name === selectedTemplate);
      if (pdfTpl) {
        fetch(`/api/get-link/${encodeURIComponent(selectedTemplate)}`)
          .then(r => r.json())
          .then(data => setPdfFileUrl(data.url))
          .catch(e => console.error(e));
      } else {
        setPdfFileUrl(null);
      }
    } else {
      setPdfFileUrl(null);
    }
  }, [selectedTemplate, pdfTemplates]);

  useEffect(() => {
    const savedUser = localStorage.getItem('esign_user');
    if (savedUser) {
      try {
        const parsedUser = JSON.parse(savedUser);
        setUser(parsedUser);
      } catch (e) {
        console.error("Failed to parse saved user", e);
        localStorage.removeItem('esign_user');
      }
    }

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab && ['upload', 'template', 'requests', 'settings', 'admin'].includes(tab)) {
        setActiveTab(tab as any);
      }
    }
    setIsMounted(true);
  }, []);

  useEffect(() => {
    fetchMasterData();
    if (activeTab === 'template') {
      fetchTemplates();
      fetchWorkflows();
    } else if (activeTab === 'requests') {
      if (user) fetchRequests();
    } else if (activeTab === 'settings') {
      fetchWorkflows();
      fetchAdminData();
    } else if (activeTab === 'admin') {
      fetchAdminData();
    } else if (activeTab === 'upload') {
      fetchTemplates();
    }
  }, [activeTab, user]);

  const fetchMasterData = async () => {
    try {
      const deployDepts = await fetch('/api/departments');
      if (deployDepts.ok) setDepartments(await deployDepts.json());

      const deployTypes = await fetch('/api/document-types');
      if (deployTypes.ok) setDocTypes(await deployTypes.json());
    } catch (e) {
      console.error("Master data fetch error", e);
    }
  };

  const fetchAdminData = async () => {
    try {
      const res = await fetch('/api/users');
      if (res.ok) setUsers(await res.json());
      fetchMasterData();
      fetchEmailConfig();
    } catch (e) {
      console.error("Admin data fetch error", e);
    }
  };

  const fetchEmailLogs = async () => {
    try {
      const res = await fetch('/api/email-logs');
      if (res.ok) setEmailLogs(await res.json());
    } catch (e) {
      console.error("Failed to fetch logs", e);
    }
  };

  useEffect(() => {
    if (activeTab === 'admin' && adminSubTab === 'logs') {
      fetchEmailLogs();
    }
  }, [activeTab, adminSubTab]);

  // Update selectedRequest when requests list changes (e.g. after signing)
  useEffect(() => {
    if (selectedRequest) {
      const updated = requests.find(r => r.id === selectedRequest.id);
      if (updated) {
        setSelectedRequest(updated);
      }
    }
  }, [requests]);

  const fetchEmailConfig = async () => {
    try {
      const res = await fetch('/api/email-config');
      if (res.ok) {
        const data = await res.json();
        setEmailConfig(data);
        // Password is not returned, so we keep emailPassword empty until user types new one
      }
    } catch (e) {
      console.error("Email config fetch error", e);
    }
  };

  const handleSaveEmailConfig = async () => {
    try {
      const payload: any = { ...emailConfig };
      if (emailPassword) {
        payload.password = emailPassword;
      }
      if (imapPassword) {
        payload.imap_password = imapPassword;
      }

      const res = await fetch('/api/email-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const data = await res.json();
        setEmailConfig(data);
        setEmailPassword('');
        setImapPassword('');
        alert("Email configuration saved successfully!");
      } else {
        alert("Failed to save email configuration");
      }
    } catch (e) {
      console.error("Save email config error", e);
    }
  };

  const handleTestEmail = async () => {
    if (!testEmail) {
      alert("Please enter a target email address for testing.");
      return;
    }
    try {
      const res = await fetch('/api/email-config/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_email: testEmail })
      });

      if (res.ok) {
        alert("Test email sent successfully! Check your inbox.");
      } else {
        const err = await res.json();
        alert("Test failed: " + (err.detail || "Unknown error"));
      }
    } catch (e) {
      console.error("Test email error", e);
      alert("Test email failed to send.");
    }
  };

  const handleTestIncoming = async () => {
    try {
      const res = await fetch('/api/email-config/test-incoming', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (res.ok) {
        const data = await res.json();
        alert(data.message);
      } else {
        const err = await res.json();
        alert("Incoming Test failed: " + (err.detail || "Unknown error"));
      }
    } catch (e) {
      console.error("Test incoming error", e);
      alert("Test failed.");
    }
  };

  const handleLogin = async () => {
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
        localStorage.setItem('esign_user', JSON.stringify(userData));
      } else {
        alert("Login failed. Check credentials.");
      }
    } catch (e) {
      console.error("Login error", e);
    }
  };

  const handleMicrosoftLogin = async () => {
    // --- Microsoft Login (Real Implementation) ---
    try {
      if (!process.env.NEXT_PUBLIC_AZURE_CLIENT_ID) {
        alert("Azure Client ID is not configured. Please see README.");
        // Fallback for demo if no ID provided
        const mockUser: User = {
          id: 999,
          email: 'demo.user@microsoft.com',
          full_name: 'Demo Microsoft User',
          role: 'User',
          auth_provider: 'microsoft',
          permissions: { departments: ['IT', 'Finance'] }
        };
        setUser(mockUser);
        localStorage.setItem('esign_user', JSON.stringify(mockUser));
        return;
      }

      const loginResponse = await msalInstance.loginPopup({
        scopes: ["User.Read", "User.ReadBasic.All"]
      });

      if (loginResponse && loginResponse.accessToken) {
        // Send token to backend or verify locally
        // For simplicity, we'll trust the token claim for now or send to backend
        const account = loginResponse.account;
        if (!account) return;

        // Call backend to verify and create session/user
        const res = await fetch(`${API_BASE_URL}/auth/microsoft`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            access_token: loginResponse.accessToken,
            email: account.username,
            name: account.name || 'Microsoft User'
          })
        });

        if (res.ok) {
          const userData = await res.json();
          setUser(userData);
          localStorage.setItem('esign_user', JSON.stringify(userData));
        } else {
          alert('Failed to login with Microsoft');
        }
      }
    } catch (error) {
      console.error('Login failed:', error);
      alert('Microsoft Login failed. Check console.');
    }
  };

  const fetchWorkflows = async () => {
    try {
      const res = await fetch('/api/workflows');
      if (res.ok) {
        const data = await res.json();
        setWorkflowConfigs(data);
      }
    } catch (e) {
      console.error("Fetch workflows error", e);
    }
  };

  const fetchTemplates = async () => {
    try {
      const [blobRes, dynRes, pdfTplRes] = await Promise.all([
        fetch('/api/templates'),
        fetch('/api/dynamic-templates'),
        fetch('/api/pdf-templates')
      ]);

      let allTemplates: string[] = [];
      if (blobRes.ok) {
        const data = await blobRes.json();
        allTemplates = [...(data.templates || [])];
      }
      if (dynRes.ok) {
        const dynData = await dynRes.json();
        setDynamicTemplates(dynData);
        allTemplates = [...allTemplates, ...dynData.map((t: { name: string }) => t.name)];
      }
      if (pdfTplRes.ok) {
        setPdfTemplates(await pdfTplRes.json());
      }
      setTemplates(allTemplates);
    } catch (error) {
      console.error("Failed to fetch templates", error);
    }
  };

  const fetchRequests = async () => {
    if (!user?.email) return;
    try {
      const res = await fetch(`/api/requests?user_email=${encodeURIComponent(user.email)}`);
      if (res.ok) {
        setRequests(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleOpenRequestDetail = async (requestId: number) => {
    try {
      const res = await fetch(`/api/requests/${requestId}`);
      if (res.ok) {
        const fullReq = await res.json();
        setSelectedRequest(fullReq);
      }
    } catch (e) {
      console.error("Error fetching request detail", e);
    }
  };

  const isRequestVisible = (req: DocumentRequest, tab: 'pending' | 'signed') => {
    const isApproved = req.status === 'Approved';

    // Admin sees everything not archived, split by approved status
    if (user?.role === 'Admin') {
      return tab === 'pending' ? !isApproved : isApproved;
    }

    const userApproval = req.approvals?.find((a: any) =>
      a.role.toLowerCase() === user?.role?.toLowerCase() ||
      a.role.toLowerCase() === user?.email?.toLowerCase()
    );
    const isRequester = req.requester_email?.toLowerCase() === user?.email?.toLowerCase();

    // Visibility: Must be the one who created it OR be in the approval workflow
    if (!isRequester && !userApproval) return false;

    const hasUserSigned = userApproval?.status === 'Signed';

    if (tab === 'pending') {
      // Pending tab: Not fully approved AND user hasn't signed it yet
      return !isApproved && !hasUserSigned;
    } else {
      // Signed tab: Fully approved OR user has already signed it
      return isApproved || hasUserSigned;
    }
  };

  const getDisplayStatus = (req: DocumentRequest) => {
    if (req.status !== 'Pending Approval' || !req.approvals || req.approvals.length === 0) {
      return req.status;
    }
    const nextPending = [...req.approvals]
      .filter((a: any) => a.status === 'Pending')
      .sort((a: any, b: any) => a.step_number - b.step_number)[0];

    if (nextPending) {
      return `Pending - ${nextPending.role}`;
    }
    return req.status;
  };

  const fetchSchema = useCallback(async (tpl: string) => {
    // Check if it's a dynamic template first
    const dynamic = dynamicTemplates.find(dt => dt.name === tpl);
    if (dynamic) {
      // Map layout labels to field names (e.g. "Full Name" -> "full_name")
      const fields = dynamic.layout.map((b: { label: string }) => b.label.toLowerCase().replace(/ /g, '_').replace(/\?/g, ''));
      setSchema(fields);
      return;
    }

    try {
      const res = await fetch(`/api/template-schema/${tpl}`);
      if (res.ok) {
        const data = await res.json();
        // Filter out system variables (approvers)
        const fields = (data.placeholders || []).filter((p: string) => !p.startsWith('approver_'));

        if (tpl.toLowerCase().includes('capex')) {
          const orderedFields: string[] = [];
          CAPEX_SECTIONS.forEach(section => {
            section.fields.forEach((f: string) => {
              // FORCE include all defined Capex fields, don't rely on auto-detection which can fail on some PDFs
              orderedFields.push(f);
            });
          });
          // Add any remaining fields detected but not in sections
          fields.forEach((f: string) => {
            if (!orderedFields.includes(f)) orderedFields.push(f);
          });
          setSchema(orderedFields);
        } else {
          setSchema(fields);
        }
      }
    } catch (e) {
      console.error("Schema fetch error", e);
    }
  }, [dynamicTemplates]);

  useEffect(() => {
    if (selectedTemplate) {
      fetchSchema(selectedTemplate);
    } else {
      setSchema([]);
    }
  }, [selectedTemplate, fetchSchema]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
    }
  };

  const handleDeleteTemplate = async (filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      const res = await fetch(`/api/templates/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (res.ok) {
        alert("Template deleted successfully");
        fetchTemplates();
      } else {
        alert("Delete failed");
      }
    } catch (e) {
      console.error("Delete template error", e);
    }
  };

  const handleDeleteDynamicTemplate = async (id: number) => {
    if (!confirm(`Are you sure you want to delete this dynamic template?`)) return;
    try {
      const res = await fetch(`/api/dynamic-templates/${id}`, { method: 'DELETE' });
      if (res.ok) {
        alert("Dynamic template deleted successfully");
        fetchTemplates();
      } else {
        alert("Delete failed");
      }
    } catch (e) {
      console.error("Delete dynamic template error", e);
    }
  };

  const handleCreatePdfTemplate = () => {
    hiddenPdfInputRef.current?.click();
  };

  const handlePdfTemplateUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setUploadStatus(`Uploading ${selectedFile.name}...`);
      const formData = new FormData();
      formData.append('file', selectedFile);

      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          // Wait a tiny bit just to ensure backend flushed it, then navigate
          setTimeout(() => {
            window.location.href = `/pdf-builder?template=${encodeURIComponent(selectedFile.name)}`;
          }, 500);
        } else {
          alert('Upload failed.');
        }
      } catch (error) {
        console.error('Upload error:', error);
        alert('Error uploading file.');
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploadStatus('Uploading...');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        setUploadStatus('Upload successful!');
        fetchSasLink(file.name);
      } else {
        setUploadStatus('Upload failed.');
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadStatus('Error uploading file.');
    }
  };

  const handleSupportingDocUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    setIsUploadingSupport(true);
    const uploadedFiles: { name: string; url: string; size: number }[] = [];

    for (let i = 0; i < e.target.files.length; i++) {
      const fileToUpload = e.target.files[i];
      const formData = new FormData();
      formData.append('file', fileToUpload);

      try {
        const res = await fetch(`${API_BASE_URL}/upload?folder=supporting_docs&optimize=true`, {
          method: 'POST',
          body: formData,
        });
        if (res.ok) {
          const data = await res.json();
          uploadedFiles.push({
            name: data.filename,
            url: data.url,
            size: data.size
          });
        }
      } catch (err) {
        console.error("Support doc upload failed", err);
      }
    }
    setSupportingDocs(prev => [...prev, ...uploadedFiles]);
    setIsUploadingSupport(false);
    // Reset input
    e.target.value = '';
  };

  const handleSaveDraft = async () => {
    if (!selectedTemplate) {
      setGenerationStatus('Error: Please select a template first');
      return;
    }
    if (!department) {
      setGenerationStatus('Error: Department is required');
      return;
    }
    if (!docType) {
      setGenerationStatus('Error: Document Type is required');
      return;
    }

    setGenerationStatus('Initiating Save...');

    try {
      const draftPayload = {
        template_name: selectedTemplate,
        department,
        doc_type: docType,
        form_data: formData,
        requester_email: user?.email,
        requester_name: user?.full_name,
        supporting_documents: supportingDocs
      };

      const res = await fetch('/api/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftPayload)
      });

      if (res.ok) {
        setGenerationStatus('Success: Draft Saved!');
        setSupportingDocs([]); // Clear after save
        setTimeout(() => {
          setActiveTab('requests');
          fetchRequests();
        }, 1500);
      } else {
        const errorData = await res.json().catch(() => ({}));
        setGenerationStatus(`Save Failed: ${errorData.detail || res.statusText || 'Server Error'}`);
      }
    } catch (e: any) {
      console.error("Save Draft Error", e);
      setGenerationStatus(`Network Error: ${e.message || 'Check your connection'}`);
    }
  };

  const handleSubmit = async (requestId: number) => {
    // Submits an existing request (Draft -> Pending)
    try {
      const res = await fetch(`/api/requests/${requestId}/submit`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchRequests(); // refresh list
        alert("Request submitted for approval!");
      } else {
        alert("Submission failed");
      }
    } catch (e) {
      console.error("Submit error", e);
    }
  };

  const handleViewRequestDoc = async (req: any) => {
    try {
      const res = await fetch(`/api/requests/${req.id}/view-url?user_email=${encodeURIComponent(user?.email || "")}`);
      if (res.ok) {
        const data = await res.json();
        setPreviewDoc({ name: req.template_name || `Request #${req.id}`, url: data.url });
      } else {
        alert("Failed to generate secure view link.");
      }
    } catch (e) {
      alert("Error fetching secure document link.");
    }
  };

  const handleViewAttachment = async (reqId: number, name: string, url: string) => {
    try {
      // Find the blob path from the URL
      let blobPath = "";
      try {
        blobPath = url.split("esign-vault/")[1].split("?")[0];
      } catch (e) {
        blobPath = url; // fallback
      }

      const res = await fetch(`/api/requests/${reqId}/view-url?user_email=${encodeURIComponent(user?.email || "")}&blob_path=${encodeURIComponent(blobPath)}`);
      if (res.ok) {
        const data = await res.json();
        setPreviewDoc({ name, url: data.url });
      } else {
        alert("Failed to generate secure attachment link.");
      }
    } catch (e) {
      alert("Error fetching secure attachment link.");
    }
  };

  const handleOpenSignature = (approvalId: number) => {
    setSigningApprovalId(approvalId);
    setSigningComment("");
    setIsSigningOpen(true);
  };

  const submitSignature = async () => {
    if (!signingApprovalId) return;
    setIsSigning(true);

    try {
      let signatureData = "";
      if (!useSavedSignature) {
        if (sigMethod === 'draw') {
          if (!sigCanvas.current) return;
          signatureData = sigCanvas.current.getTrimmedCanvas().toDataURL('image/png');
        } else {
          // sigMethod === 'image'
          if (!uploadedSig) {
            alert("Please upload a signature image first");
            setIsSigning(false);
            return;
          }
          signatureData = uploadedSig;
        }

        // Adobe-style: Save for later if checked
        if (shouldSaveSignature) {
          await fetch('/api/users/save-signature', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: user?.email,
              signature_base64: signatureData,
              sig_type: sigType
            })
          });
          // Optimistically update local user to show they have a signature now
          if (user) {
            const updatedUser = { ...user };
            if (sigType === 'initial') updatedUser.saved_initials_url = 'refreshing...';
            else updatedUser.saved_signature_url = 'refreshing...';
            setUser(updatedUser);
          }
        }
      }

      const res = await fetch(`/api/approvals/${signingApprovalId}/sign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          signature_base64: useSavedSignature ? "" : signatureData,
          user_email: user?.email || "",
          use_saved: useSavedSignature,
          sig_type: sigType,
          comment: signingComment
        })
      });

      if (res.ok) {
        alert("Signed successfully!");
        setIsSigningOpen(false);
        setSigningApprovalId(null);
        setUseSavedSignature(false);
        setShouldSaveSignature(false);
        fetchRequests();
        // Force refresh user data to get the new signature URL if it was saved
        if (shouldSaveSignature) {
          const refreshUsers = await fetch('/api/users');
          if (refreshUsers.ok) {
            const allUsers = await refreshUsers.json();
            const me = allUsers.find((u: any) => u.email === user?.email);
            if (me) setUser(me);
          }
        }
      } else {
        const err = await res.json();
        alert("Signing failed: " + err.detail);
      }
    } catch (e) {
      console.error("Sign error", e);
      alert("Error submitting signature");
    } finally {
      setIsSigning(false);
    }
  };

  const handleSaveWorkflow = async () => {
    try {
      const res = await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editWorkflow)
      });
      if (res.ok) {
        alert("Workflow saved!");
        fetchWorkflows();
      } else {
        alert("Failed to save workflow");
      }
    } catch (e) {
      console.error("Save Workflows error", e);
    }
  };

  const fetchSasLink = async (filename: string) => {
    try {
      const res = await fetch(`/api/get-link/${filename}`);
      const data = await res.json();
      if (data.url) {
        setSasUrl(data.url);
      }
    } catch (error) {
      console.error('Error fetching SAS link:', error);
    }
  };

  useEffect(() => {
    if (isSigningOpen) {
      document.body.classList.add('signature-modal-open');
    } else {
      document.body.classList.remove('signature-modal-open');
    }
  }, [isSigningOpen]);

  if (!isMounted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center font-sans">
        <div className="text-center">
          <img src="/berkeley_logo.jpg" alt="Loading..." className="h-10 mx-auto mb-3 opacity-60" />
          <p className="text-xs text-gray-400 uppercase tracking-widest">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-gray-100 flex flex-col items-center justify-center font-sans">
        <div className="w-full max-w-sm">
          {/* Login Card */}
          <div className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
            {/* Card Header */}
            <div className="bg-gradient-to-r from-blue-800 to-indigo-700 px-8 py-6 text-center">
              <div className="inline-block bg-white rounded-md p-2 mb-3 shadow">
                <img src="/berkeley_logo.jpg" alt="Berkeley Logo" className="h-8 w-auto object-contain" />
              </div>
              <h1 className="text-white font-semibold text-lg">Berkeley Esign Portal</h1>
              <p className="text-indigo-200 text-xs mt-1">Enterprise Document Management</p>
            </div>

            {/* Card Body */}
            <div className="px-8 py-6 space-y-4">
              <button
                onClick={handleMicrosoftLogin}
                className="w-full flex items-center justify-center space-x-2 border border-gray-300 py-2 rounded-md hover:bg-gray-50 transition text-sm font-medium text-gray-700 shadow-sm"
              >
                <img src="/microsoft_logo.svg" className="w-4 h-4" alt="Microsoft" />
                <span>Sign in with Microsoft</span>
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200"></div></div>
                <div className="relative flex justify-center text-xs"><span className="px-2 bg-white text-gray-400">or</span></div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={loginEmail}
                    onChange={e => setLoginEmail(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                    placeholder="your@email.com"
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={e => setLoginPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                    placeholder="••••••••"
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  />
                </div>
                <button
                  onClick={handleLogin}
                  className="w-full bg-indigo-600 text-white py-2 rounded-md text-sm font-semibold hover:bg-indigo-700 transition shadow-sm"
                >
                  Sign In
                </button>
              </div>
            </div>
          </div>
          <p className="text-center text-xs text-gray-400 mt-4">Default Admin: admin@esign.com / admin123</p>
        </div>
      </main>
    )
  }



  return (
    <div className="min-h-screen bg-gray-100 font-sans">
      {/* ── TOP HEADER BAR ── */}
      <header className="fixed top-0 left-0 right-0 z-40 h-14 bg-gradient-to-r from-blue-800 to-indigo-700 flex items-center justify-between px-4 shadow-md">
        {/* Left: Hamburger (Mobile) + Logo + Portal Name */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="md:hidden text-white p-1 hover:bg-white/10 rounded-md transition-colors"
          >
            {isSidebarOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
            )}
          </button>
          <div className="hidden sm:flex items-center gap-3">
            <div className="bg-white rounded p-1 shadow-sm flex items-center justify-center">
              <img src="/berkeley_logo.jpg" alt="Berkeley" className="h-7 w-auto object-contain" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm leading-none">Berkeley Esign Portal</p>
              <p className="text-indigo-200 text-[10px] leading-none mt-0.5">Document Management</p>
            </div>
          </div>
          {/* Mobile Logo Only */}
          <div className="sm:hidden bg-white rounded p-1 shadow-sm flex items-center justify-center">
            <img src="/berkeley_logo.jpg" alt="Berkeley" className="h-6 w-auto object-contain" />
          </div>
        </div>

        {/* Right: User pill + signout */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-white text-sm font-semibold leading-none">{user.full_name}</p>
            <p className="text-indigo-200 text-[10px] leading-none mt-0.5 uppercase tracking-wider">{user.role}</p>
          </div>
          <button
            onClick={() => { setUser(null); localStorage.removeItem('esign_user'); }}
            className="flex items-center gap-1.5 bg-white/10 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded transition-all"
            title="Sign Out"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            Sign Out
          </button>
        </div>
      </header>

      <div className="flex pt-14">
        {/* ── MOBILE OVERLAY ── */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-20 md:hidden animate-in fade-in duration-200"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* ── LEFT SIDEBAR ── */}
        <aside className={`fixed top-14 bottom-0 left-0 w-56 bg-white border-r border-gray-200 flex flex-col z-30 transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
          {/* Org label */}
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">Navigation</p>
          </div>

          {/* Nav items */}
          <nav className="flex-1 py-2 px-2 space-y-0.5 overflow-y-auto">
            <NavItem tab="requests" activeTab={activeTab} setActiveTab={setActiveTab} setIsSidebarOpen={setIsSidebarOpen} label="My Requests" icon={
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            } />
            <NavItem tab="template" activeTab={activeTab} setActiveTab={setActiveTab} setIsSidebarOpen={setIsSidebarOpen} label="New Request" icon={
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
            } />
            {user.role === 'Admin' && (
              <>
                <div className="pt-3 pb-1 px-3">
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">Administration</p>
                </div>
                <NavItem tab="upload" activeTab={activeTab} setActiveTab={setActiveTab} setIsSidebarOpen={setIsSidebarOpen} label="Templates" icon={
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414A1 1 0 0120 8.414V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" /></svg>
                } />
                <NavItem tab="settings" activeTab={activeTab} setActiveTab={setActiveTab} setIsSidebarOpen={setIsSidebarOpen} label="Workflows" icon={
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
                } />
                <NavItem tab="admin" activeTab={activeTab} setActiveTab={setActiveTab} setIsSidebarOpen={setIsSidebarOpen} label="Admin" icon={
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                } />
              </>
            )}
          </nav>

          {/* Bottom version */}
          <div className="border-t border-gray-100 px-4 py-3">
            <p className="text-[10px] text-gray-400">Berkeley Esign v1.0</p>
          </div>
        </aside>

        {/* ── MAIN CONTENT AREA ── */}
        <main className="flex-1 ml-0 md:ml-56 overflow-auto min-h-[calc(100vh-56px)]">
          <div className="px-4 md:px-8 py-4 md:py-6">
            {activeTab === 'requests' && (
              <div className="space-y-6 animate-in fade-in duration-300">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-4 w-full sm:w-auto">
                    <h2 className="text-xl font-semibold text-gray-800">My Requests</h2>
                    <div className="flex bg-gray-100 p-1 rounded-lg w-full sm:w-auto">
                      <button
                        onClick={() => setRequestSubTab('pending')}
                        className={`flex-1 sm:flex-none px-4 py-1.5 rounded text-xs font-semibold transition-all ${requestSubTab === 'pending' ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                          }`}
                      >
                        Pending ({requests.filter(req => isRequestVisible(req, 'pending')).length})
                      </button>
                      <button
                        onClick={() => setRequestSubTab('signed')}
                        className={`flex-1 sm:flex-none px-4 py-1.5 rounded text-xs font-semibold transition-all ${requestSubTab === 'signed' ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                          }`}
                      >
                        Signed ({requests.filter(req => isRequestVisible(req, 'signed')).length})
                      </button>
                    </div>
                  </div>
                  <button onClick={fetchRequests} className="flex items-center text-indigo-600 text-sm hover:underline">
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                    Refresh
                  </button>
                </div>

                {/* Bulk Actions */}
                {selectedRequestIds.length > 0 && user?.role === 'Admin' && (
                  <div className="bg-indigo-50 border border-indigo-100 p-4 rounded-xl flex justify-between items-center mb-6 animate-in fade-in slide-in-from-top-2">
                    <span className="font-bold text-indigo-900">{selectedRequestIds.length} requests selected</span>
                    <div className="flex space-x-3">
                      <button
                        onClick={() => setSelectedRequestIds([])}
                        className="px-4 py-2 text-indigo-600 hover:bg-indigo-100 rounded-lg font-bold text-sm transition-all"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={async () => {
                          if (confirm(`Archive ${selectedRequestIds.length} requests?`)) {
                            try {
                              const res = await fetch(`/api/requests/archive`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  request_ids: selectedRequestIds,
                                  user_email: user.email
                                })
                              });
                              if (res.ok) {
                                setSelectedRequestIds([]);
                                fetchRequests();
                              } else {
                                alert('Failed to archive requests');
                              }
                            } catch (e) {
                              console.error(e);
                              alert('Error archiving requests');
                            }
                          }
                        }}
                        className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-black text-sm uppercase tracking-widest shadow-lg hover:bg-indigo-700 transition-all"
                      >
                        Archive Selected
                      </button>
                    </div>
                  </div>
                )}

                <RequestTable
                  requests={requests}
                  requestSubTab={requestSubTab}
                  isRequestVisible={isRequestVisible}
                  selectedRequestIds={selectedRequestIds}
                  setSelectedRequestIds={setSelectedRequestIds}
                  handleOpenRequestDetail={handleOpenRequestDetail}
                  handleSubmit={handleSubmit}
                  handleViewRequestDoc={handleViewRequestDoc}
                  getDisplayStatus={getDisplayStatus}
                  userRole={user?.role}
                />
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="space-y-6 animate-in fade-in duration-300">
                <div className="border-b border-gray-200 pb-4">
                  <h2 className="text-xl font-semibold text-gray-800">Workflow Configuration</h2>
                  <p className="text-sm text-gray-500 mt-1">Manage approval chains for each department and document type</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">Edit Workflow</h3>
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">Department</label>
                          <select
                            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 transition-all"
                            value={editWorkflow.department}
                            onChange={e => setEditWorkflow({ ...editWorkflow, department: e.target.value })}
                          >
                            <option value="">Select Dept</option>
                            {departments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">Doc Type</label>
                          <select
                            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 transition-all"
                            value={editWorkflow.doc_type}
                            onChange={e => setEditWorkflow({ ...editWorkflow, doc_type: e.target.value })}
                          >
                            <option value="">Select Type</option>
                            {docTypes.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                          </select>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <label className="block text-xs font-medium text-gray-500">Signers Sequence</label>
                          <button
                            onClick={() => {
                              const newApprovers = [...editWorkflow.approvers, ""];
                              setEditWorkflow({ ...editWorkflow, approvers: newApprovers });
                            }}
                            className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                          >
                            + Add Step
                          </button>
                        </div>

                        {editWorkflow.approvers.map((approver, idx) => (
                          <div key={idx} className="flex gap-2 items-center">
                            <div className="bg-indigo-100 text-indigo-700 w-6 h-6 rounded-full flex items-center justify-center font-semibold text-xs shrink-0">
                              {idx + 1}
                            </div>
                            <select
                              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 transition-all text-sm"
                              value={approver}
                              onChange={e => {
                                const newApprovers = [...editWorkflow.approvers];
                                newApprovers[idx] = e.target.value;
                                setEditWorkflow({ ...editWorkflow, approvers: newApprovers });
                              }}
                            >
                              <option value="">Select User / Role</option>
                              <optgroup label="System Users">
                                {users.map(u => (
                                  <option key={u.id} value={u.email}>{u.full_name} ({u.role})</option>
                                ))}
                              </optgroup>
                              <optgroup label="Generic Roles (Legacy)">
                                <option value="Manager">Manager</option>
                                <option value="HR">HR</option>
                                <option value="CFO">CFO</option>
                                <option value="CEO">CEO</option>
                              </optgroup>
                            </select>
                            <button
                              onClick={() => {
                                const newApprovers = editWorkflow.approvers.filter((_, i) => i !== idx);
                                setEditWorkflow({ ...editWorkflow, approvers: newApprovers });
                              }}
                              className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                            </button>
                          </div>
                        ))}

                        {editWorkflow.approvers.length === 0 && (
                          <div className="text-center py-6 bg-white border-2 border-dashed border-gray-200 rounded-xl text-gray-400 text-sm italic">
                            No signers added yet. Click "+ Add Step" to begin.
                          </div>
                        )}
                      </div>

                      <button
                        onClick={handleSaveWorkflow}
                        className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 transition shadow-sm"
                      >
                        Save Configuration
                      </button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Existing Workflows</h3>
                    {workflowConfigs.length === 0 ? (
                      <div className="text-gray-400 text-sm italic text-center py-8 bg-gray-50 rounded-lg border border-dashed border-gray-200">No custom workflows defined yet.</div>
                    ) : (
                      <div className="space-y-2">
                        {workflowConfigs.map(wf => (
                          <div key={wf.id} className="px-4 py-3 bg-white border border-gray-200 rounded-md flex justify-between items-center hover:border-indigo-300 transition-colors">
                            <div>
                              <span className="font-medium text-gray-800 text-sm">{wf.department} <span className="text-gray-300 mx-1">/</span> {wf.doc_type}</span>
                              <div className="text-xs text-gray-400 mt-0.5">
                                {[...wf.approvers, ...wf.signers].filter(Boolean).join(' → ')}
                              </div>
                            </div>
                            <button
                              onClick={() => setEditWorkflow(wf)}
                              className="text-indigo-600 hover:bg-indigo-50 text-xs font-medium px-3 py-1 rounded border border-indigo-200 transition-colors"
                            >
                              Edit
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'upload' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in fade-in duration-300">
                {/* Upload Logic (Existing) */}
                <div className="space-y-6 bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                  <div className="border-b border-gray-100 pb-4">
                    <h2 className="text-lg font-semibold text-gray-800">Upload PDF Template</h2>
                    <p className="text-sm text-gray-500 mt-0.5">Upload a PDF to use the <strong>Drag-and-Drop</strong> signature builder, or a DOCX for legacy templates.</p>
                  </div>
                  {/* Dept Selectors */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Department</label>
                      <select
                        value={department}
                        onChange={(e) => setDepartment(e.target.value)}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                      >
                        <option value="">Select Dept</option>
                        {departments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Document Type</label>
                      <select
                        value={docType}
                        onChange={(e) => setDocType(e.target.value)}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all disabled:opacity-50"
                        disabled={!department}
                      >
                        <option value="">Select Type</option>
                        {docTypes.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                      </select>
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-5">
                    <label className="block text-xs font-medium text-gray-500 mb-2">Select PDF Document</label>
                    <div className="space-y-3">
                      <input
                        type="file"
                        onChange={handleFileChange}
                        accept=".docx,.pdf"
                        className="block w-full text-sm text-slate-500 file:mr-4 file:py-1.5 file:px-4 file:rounded file:border-0 file:text-xs file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 transition-all"
                      />
                      <button
                        onClick={handleUpload}
                        disabled={!file}
                        className="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-sm"
                      >
                        Process & Upload Document
                      </button>
                    </div>
                    {uploadStatus && (
                      <div className="mt-6 p-4 bg-green-50 rounded-xl border border-green-100">
                        <p className="text-green-700 font-bold mb-2">✓ {uploadStatus}</p>
                        {sasUrl && (
                          <a href={sasUrl} target="_blank" className="text-indigo-600 font-black underline text-base hover:text-indigo-800">
                            Review Uploaded Asset →
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Template Management Section */}
                <div className="space-y-8">
                  <div className="bg-white p-6 rounded-lg border border-gray-100 shadow-sm overflow-hidden relative">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-50 rounded-full -mr-16 -mt-16 pointer-events-none opacity-50"></div>
                    <div className="flex justify-between items-center border-b border-gray-100 pb-4 mb-6 relative z-10">
                      <h2 className="text-xl font-semibold text-gray-800">Manage Existing Templates</h2>
                      <div className="flex gap-2">
                        <input
                          type="file"
                          ref={hiddenPdfInputRef}
                          className="hidden"
                          accept=".pdf"
                          onChange={handlePdfTemplateUpload}
                        />
                        <button
                          onClick={handleCreatePdfTemplate}
                          className="px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-bold hover:bg-indigo-600 hover:text-white transition-all shadow-sm border border-indigo-100 cursor-pointer"
                        >
                          + Upload PDF Template
                        </button>
                      </div>
                    </div>
                    <div className="space-y-4 relative z-10">
                      {templates.length === 0 && dynamicTemplates.length === 0 ? (
                        <div className="text-center py-12 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                          <p className="text-gray-400 font-bold uppercase tracking-widest text-xs">No active templates found</p>
                        </div>
                      ) : (
                        [...templates, ...dynamicTemplates.map(dt => dt.name)].map((tplName) => {
                          const dynTemplate = dynamicTemplates.find(dt => dt.name === tplName);
                          const isDynamic = !!dynTemplate;

                          return (
                            <div key={tplName} className="flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-md group hover:border-indigo-300 transition-all">
                              <div className="flex items-center space-x-3">
                                <div className={`w-8 h-8 rounded flex items-center justify-center ${isDynamic ? 'bg-purple-100 text-purple-600' : 'bg-blue-100 text-blue-600'}`}>
                                  {isDynamic ? (
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                  ) : (
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                  )}
                                </div>
                                <div className="flex-1">
                                  <p className="font-medium text-gray-800 text-sm truncate max-w-[220px]">{tplName}</p>
                                  <div className="flex items-center mt-0.5">
                                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${isDynamic ? 'bg-purple-50 text-purple-500' : 'bg-blue-50 text-blue-500'}`}>
                                      {isDynamic ? 'Dynamic' : (tplName.toLowerCase().endsWith('.pdf') ? 'PDF' : 'Docx')}
                                    </span>
                                  </div>
                                </div>
                              </div>
                              <div className="flex space-x-1 opacity-0 group-hover:opacity-100 transition-all">
                                {isDynamic && (
                                  <Link
                                    href={`/builder?id=${dynTemplate.id}`}
                                    className="p-1.5 bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-600 hover:text-white transition-all"
                                    title="Open in Builder"
                                  >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                                  </Link>
                                )}
                                {!isDynamic && (
                                  <button
                                    className="p-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-600 hover:text-white transition-all"
                                    title="Replace Template"
                                    onClick={() => {
                                      alert("To modify this template, please use the upload form above with the same department and document type.");
                                    }}
                                  >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                                  </button>
                                )}
                                {!isDynamic && tplName.toLowerCase().endsWith('.pdf') && (
                                  <Link
                                    href={`/pdf-builder?template=${encodeURIComponent(tplName)}`}
                                    className="p-1.5 bg-indigo-50 text-indigo-600 rounded-md hover:bg-indigo-600 hover:text-white transition-all shadow-sm flex items-center gap-1 px-2 border border-indigo-100"
                                    title="Configure Drag-and-Drop Signatures"
                                  >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                                    <span className="text-[10px] font-bold uppercase tracking-tighter">Configure</span>
                                  </Link>
                                )}
                                <button
                                  onClick={() => isDynamic ? handleDeleteDynamicTemplate(dynTemplate.id) : handleDeleteTemplate(tplName)}
                                  className="p-1.5 bg-red-50 text-red-600 rounded hover:bg-red-600 hover:text-white transition-all"
                                  title="Delete Permanently"
                                >
                                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                </button>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>

                <div className="bg-indigo-900 rounded-2xl p-8 border border-white/10 shadow-2xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -mr-16 -mt-16 pointer-events-none"></div>
                  <h2 className="text-2xl font-black text-white mb-8 border-b border-white/10 pb-4">Approval Chain</h2>
                  {!currentFlow ? (
                    <div className="h-full flex flex-col items-center justify-center text-white/40 text-center py-10">
                      <svg className="w-16 h-16 mb-4 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                      <p className="text-lg font-medium">Select Department and Document Type to visualize the secure workflow.</p>
                    </div>
                  ) : (
                    <div className="space-y-8">
                      <div>
                        <h3 className="text-sm font-black text-indigo-300 uppercase tracking-widest mb-6">Security Sequence</h3>
                        <div className="space-y-4">
                          {[...currentFlow.approvers, ...currentFlow.signers].filter(Boolean).map((signer, idx) => (
                            <div key={idx} className="flex items-center p-5 bg-white/5 rounded-2xl border border-white/10 hover:bg-white/10 transition-all group">
                              <span className="w-10 h-10 rounded-xl bg-indigo-500 text-white flex items-center justify-center text-lg font-black mr-5 shadow-lg group-hover:scale-110 transition-transform">{idx + 1}</span>
                              <span className="text-white text-xl font-bold tracking-tight">{signer}</span>
                            </div>
                          ))}
                          {[...currentFlow.approvers, ...currentFlow.signers].length === 0 && (
                            <p className="text-lg text-white/40 italic text-center py-10 bg-white/5 rounded-2xl">No signers configured for this flow.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'template' && (
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 animate-in fade-in duration-300">
                {/* Template Logic */}
                <div className="lg:col-span-3 space-y-6">
                  <div className="flex justify-between items-center border-b border-gray-200 pb-4">
                    <h2 className="text-xl font-semibold text-gray-800">New Request</h2>
                    <span className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded border border-gray-200 font-medium uppercase tracking-wider">
                      {department && docType ? `${department} • ${docType}` : 'Default Workflow (IT-PO)'}
                    </span>
                  </div>

                  {/* Workflow Selector for Template Mode too */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Department</label>
                      <select
                        value={department}
                        onChange={(e) => {
                          setDepartment(e.target.value);
                          setSelectedTemplate('');
                          setDocType('');
                        }}
                        className="w-full px-3 py-2 text-sm bg-white text-gray-900 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 transition-all appearance-none cursor-pointer"
                        style={{ color: '#000000', backgroundColor: '#ffffff' }}
                      >
                        <option value="">Select Department</option>
                        {visibleDepartments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Document Type</label>
                      <select
                        value={docType}
                        onChange={(e) => setDocType(e.target.value)}
                        className="w-full px-3 py-2 text-sm bg-white text-gray-900 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 transition-all appearance-none cursor-pointer"
                        style={{ color: '#000000', backgroundColor: '#ffffff' }}
                        disabled={!department}
                      >
                        <option value="">Select Type</option>
                        {docTypes.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                      </select>
                    </div>
                  </div>

                  {!department ? (
                    <div className="p-4 bg-indigo-50 text-indigo-700 rounded-lg text-sm italic font-medium">
                      Please select a department above to see available templates.
                    </div>
                  ) : visibleTemplates.length === 0 ? (
                    <div className="p-4 bg-yellow-50 text-yellow-800 rounded-lg text-sm">
                      No templates found for {department}.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide">Choose Your Template</label>
                      <select
                        value={selectedTemplate}
                        onChange={(e) => setSelectedTemplate(e.target.value)}
                        className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 transition-all appearance-none cursor-pointer"
                        style={{ color: '#111827', backgroundColor: '#ffffff' }}
                      >
                        <option value="">-- Choose a Template --</option>
                        {visibleTemplates.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                  )}

                  {/* Dynamic Form Generation or PDF Filler */}
                  <div className="grid grid-cols-12 gap-x-4 gap-y-3 auto-rows-min">
                    {pdfFileUrl ? (
                      <div className="col-span-12">
                        <PdfFiller
                          fileUrl={pdfFileUrl}
                          fields={(pdfTemplates.find(p => p.name === selectedTemplate)?.form_fields as any) || []}
                          formData={formData}
                          onFormDataChange={(key, value) => setFormData((prev: any) => ({ ...prev, [key]: value }))}
                          currentUser={user}
                        />
                      </div>
                    ) : (
                      schema.map((field) => {
                        const isCapex = selectedTemplate?.toLowerCase().includes('capex');
                        const isItemField = field.startsWith('item_') || field.startsWith('is_item_');
                        const section = CAPEX_SECTIONS.find(s => s.fields.includes(field));
                        const isFirstFieldInSection = section && section.fields[0] === field;

                        // If it's a Capex Item Field, we only render it if it's the FIRST field in the "Item Details" section (to trigger the grid)
                        // Otherwise we return null to avoid duplicate flat fields
                        if (isCapex && isItemField) {
                          if (section?.title === "Item Details") {
                            if (!isFirstFieldInSection) return null;
                          } else if (!section) {
                            return null;
                          }
                        }

                        // Logic for responsive widths
                        let containerClass = "col-span-12"; // Default
                        const dynamicTpl = dynamicTemplates.find(dt => dt.name === selectedTemplate);
                        if (dynamicTpl) {
                          const layoutBlock = dynamicTpl.layout.find(lb => lb.label.toLowerCase().replace(/ /g, '_').replace(/\?/g, '') === field);
                          if (layoutBlock && layoutBlock.width) {
                            containerClass = `col-span-${layoutBlock.width}`;
                          }
                        } else if (isCapex) {
                          containerClass = (section?.title === "Item Details" && isFirstFieldInSection) ||
                            (field.length > 20 || field === 'justification' || (section && isCapex))
                            ? "col-span-12" : "col-span-6";
                        } else if (field.length > 20 || field === 'justification') {
                          containerClass = "col-span-12";
                        } else {
                          containerClass = "col-span-12 sm:col-span-6";
                        }

                        return (
                          <div key={field} className={containerClass} style={dynamicTpl ? { gridColumn: `span ${dynamicTemplates.find(dt => dt.name === selectedTemplate)?.layout.find(lb => lb.label.toLowerCase().replace(/ /g, '_').replace(/\?/g, '') === field)?.width || 12} / span ${dynamicTemplates.find(dt => dt.name === selectedTemplate)?.layout.find(lb => lb.label.toLowerCase().replace(/ /g, '_').replace(/\?/g, '') === field)?.width || 12}` } : {}}>
                            {section && isCapex && isFirstFieldInSection && (
                              <div className="pt-6 pb-2 border-b border-gray-100 mb-4">
                                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">{section.title}</h3>
                              </div>
                            )}

                            {section?.title === "Item Details" && isCapex && isFirstFieldInSection ? (
                              <div className="overflow-x-auto mb-10 shadow-xl rounded-2xl border-4 border-indigo-50">
                                <table className="w-full text-left border-collapse bg-white">
                                  <thead>
                                    <tr className="bg-indigo-600 text-white text-xs uppercase tracking-widest font-black">
                                      <th className="p-4 border-b border-indigo-700 text-center w-12">#</th>
                                      <th className="p-4 border-b border-indigo-700">Item Name</th>
                                      <th className="p-4 border-b border-indigo-700">Budgeted</th>
                                      <th className="p-4 border-b border-indigo-700 text-center">Date Required</th>
                                      <th className="p-4 border-b border-indigo-700 text-right">Estimated Cost</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {[1, 2, 3, 4, 5].map(i => (
                                      <tr key={i} className="hover:bg-indigo-50/30 transition-colors border-b border-gray-100">
                                        <td className="p-3 text-center text-sm font-black text-gray-300">{i}</td>
                                        <td className="p-3">
                                          <input
                                            className="w-full bg-white p-3 text-base font-bold text-gray-900 rounded-lg border border-transparent focus:border-indigo-300 focus:shadow-sm focus:outline-none transition-all"
                                            style={{ color: '#000000', backgroundColor: '#ffffff' }}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            value={(formData as any)[`item_${i}_description`] || ''}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            onChange={e => setFormData({ ...formData, [`item_${i}_description`]: e.target.value })}
                                            placeholder="Enter item description..."
                                          />
                                        </td>
                                        <td className="p-3">
                                          <select
                                            className="w-full bg-white p-3 text-sm font-black text-center rounded-lg border border-transparent focus:border-indigo-300 focus:shadow-sm focus:outline-none transition-all appearance-none cursor-pointer"
                                            style={{ color: '#000000', backgroundColor: '#ffffff' }}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            value={(formData as any)[`is_item_${i}_budgeted_yes_no`] || ''}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            onChange={e => setFormData({ ...formData, [`is_item_${i}_budgeted_yes_no`]: e.target.value })}
                                          >
                                            <option value="">-</option>
                                            <option value="YES">YES</option>
                                            <option value="NO">NO</option>
                                          </select>
                                        </td>
                                        <td className="p-3">
                                          <input
                                            type="date"
                                            className="w-full bg-white p-3 text-sm font-bold text-center rounded-lg border border-transparent focus:border-indigo-300 focus:shadow-sm focus:outline-none transition-all cursor-pointer"
                                            style={{ color: '#000000', backgroundColor: '#ffffff' }}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            value={(formData as any)[`item_${i}_date_required`] || ''}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            onChange={e => setFormData({ ...formData, [`item_${i}_date_required`]: e.target.value })}
                                          />
                                        </td>
                                        <td className="p-3">
                                          <div className="relative">
                                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300 font-bold ml-1">AED</span>
                                            <input
                                              className="w-full bg-white pl-12 p-3 text-base text-right font-black text-indigo-700 rounded-lg border border-transparent focus:border-indigo-300 focus:shadow-sm focus:outline-none transition-all font-mono"
                                              style={{ color: '#4338ca', backgroundColor: '#ffffff' }}
                                              // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                              value={(formData as any)[`item_${i}_amount`] || ''}
                                              // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                              onChange={e => setFormData({ ...formData, [`item_${i}_amount`]: e.target.value })}
                                              placeholder="0.00"
                                            />
                                          </div>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <div className="w-full">
                                <label className="block text-xs font-medium text-gray-500 mb-1">{field.replace(/_/g, ' ')}</label>
                                {(field.toLowerCase().endsWith('yes_no') || field.toLowerCase().startsWith('is_')) ? (
                                  <select
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    value={(formData as any)[field] || ''}
                                    onChange={e => setFormData({ ...formData, [field]: e.target.value })}
                                    className="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-900 focus:border-indigo-500 focus:outline-none transition-colors appearance-none cursor-pointer"
                                    style={{ color: '#111827', backgroundColor: '#ffffff' }}
                                  >
                                    <option value="">Select...</option>
                                    <option value="YES">Yes</option>
                                    <option value="NO">No</option>
                                  </select>
                                ) : field === 'justification' ? (
                                  <textarea
                                    rows={3}
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    value={(formData as any)[field] || ''}
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    onChange={e => setFormData({ ...formData, [field]: e.target.value })}
                                    className="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-900 focus:border-indigo-500 focus:outline-none transition-colors"
                                    style={{ color: '#111827', backgroundColor: '#ffffff' }}
                                    placeholder={`Enter ${field.replace(/_/g, ' ')}`}
                                  />
                                ) : (
                                  <input
                                    type={field.toLowerCase().includes('date') ? 'date' : 'text'}
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    value={(formData as any)[field] || ''}
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    onChange={e => setFormData({ ...formData, [field]: e.target.value })}
                                    className="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-900 focus:border-indigo-500 focus:outline-none transition-colors"
                                    style={{ color: '#111827', backgroundColor: '#ffffff' }}
                                    placeholder={`Enter ${field.replace(/_/g, ' ')}`}
                                  />
                                )}
                              </div>
                            )}
                          </div>
                        );
                      }))}
                    {schema.length === 0 && selectedTemplate && !pdfFileUrl && (
                      <div className="col-span-12 text-center text-sm text-gray-400 py-4 italic">
                        Loading fields or no placeholders found...
                      </div>
                    )}
                  </div>

                  {/* Supporting Documents Section */}
                  <div className="pt-8 border-t border-gray-100 space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Supporting Documents</h3>
                      {isUploadingSupport && (
                        <div className="flex items-center text-xs text-indigo-600 animate-pulse font-bold">
                          <svg className="animate-spin -ml-1 mr-2 h-3 w-3 text-indigo-600" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          Optimizing & Uploading...
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {supportingDocs.map((doc, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-xl shadow-sm group hover:border-indigo-300 transition-all">
                          <div className="flex items-center space-x-3 overflow-hidden">
                            <div className="p-2 bg-indigo-50 text-indigo-600 rounded">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.707 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
                            </div>
                            <div className="overflow-hidden">
                              <p className="text-sm font-bold text-gray-800 truncate" title={doc.name}>{doc.name}</p>
                              <p className="text-[10px] text-gray-400">{(doc.size / 1024).toFixed(1)} KB</p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-1">
                            <button
                              onClick={() => setPreviewDoc({ name: doc.name, url: doc.url })}
                              className="p-1.5 text-gray-400 hover:text-indigo-600 transition-colors"
                              title="Preview"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                            </button>
                            <button
                              onClick={() => setSupportingDocs(supportingDocs.filter((_, i) => i !== idx))}
                              className="p-1.5 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                          </div>
                        </div>
                      ))}

                      <label className="flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-200 rounded-xl hover:border-indigo-400 hover:bg-indigo-50/30 transition-all cursor-pointer group h-[60px]">
                        <div className="flex items-center space-x-2">
                          <svg className="w-5 h-5 text-gray-400 group-hover:text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
                          <span className="text-xs font-bold text-gray-500 group-hover:text-indigo-700">Add Support Docs</span>
                        </div>
                        <input
                          type="file"
                          multiple
                          className="hidden"
                          onChange={handleSupportingDocUpload}
                          accept=".pdf,.jpg,.jpeg,.png"
                        />
                      </label>
                    </div>
                  </div>

                  <div className="pt-4 flex space-x-4">
                    <button
                      onClick={handleSaveDraft}
                      disabled={!selectedTemplate}
                      className="px-5 py-2 bg-gray-100 text-gray-600 rounded-md hover:bg-gray-200 disabled:opacity-50 transition-all font-medium text-sm shadow-sm border border-gray-200"
                    >
                      Save Draft
                    </button>
                  </div>
                  {generationStatus && (
                    <p className={`mt-2 text-sm ${generationStatus.includes('Saved') ? 'text-green-600' : 'text-gray-500'}`}>
                      {generationStatus}
                    </p>
                  )}
                </div>

                {/* Right Layout for Template Mode (Preview) */}
                {/* Right Layout for Template Mode (Preview) */}
                <div className="md:col-span-1 bg-gray-50 rounded-lg p-4 border border-gray-100 flex flex-col justify-between min-h-[400px]">
                  <div className="w-full">
                    <h3 className="text-gray-500 font-medium mb-4 text-center">Workflow Preview</h3>
                    <div className="bg-white p-4 rounded-lg shadow-sm border mb-6">
                      <div className="flex justify-between items-center mb-2">
                        <h4 className="text-xs font-bold text-blue-600 uppercase">Signers Sequence</h4>
                        {currentFlow?.source && (
                          <span className="text-[9px] bg-blue-50 text-blue-500 px-1.5 py-0.5 rounded font-bold">{currentFlow.source}</span>
                        )}
                      </div>
                      {currentFlow ? (
                        <ul className="space-y-2">
                          {[...currentFlow.approvers, ...currentFlow.signers].filter(Boolean).map((signer, idx) => (
                            <li key={idx} className="flex items-center text-sm">
                              <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold mr-2">{idx + 1}</span>
                              <span className="text-gray-700">{signer}</span>
                            </li>
                          ))}
                          {[...currentFlow.approvers, ...currentFlow.signers].length === 0 && <p className="text-xs text-gray-400">No signers configured.</p>}
                        </ul>
                      ) : (
                        <div className="text-center py-4 text-gray-400 text-sm">Select Dept & Type to see workflow.</div>
                      )}
                    </div>
                  </div>

                  <div className="text-center w-full border-t pt-4">
                    <h3 className="text-gray-400 font-semibold mb-2 text-[10px] uppercase tracking-wider">Instructions</h3>
                    <p className="text-[10px] text-gray-400 leading-relaxed">
                      1. Select Template & Workflow.<br />
                      2. Fill in the form.<br />
                      3. Save Draft and then Submit.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'admin' && user.role === 'Admin' && (
              <div className="space-y-6 animate-in fade-in duration-500">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-200 pb-4 gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-gray-800">Site Administration</h2>
                    <p className="text-sm text-gray-500 mt-0.5">Global governance and system health</p>
                  </div>
                  <div className="flex flex-wrap gap-1 bg-gray-100 p-1 rounded-lg">
                    <button
                      onClick={() => setAdminSubTab('users')}
                      className={`px-4 py-1.5 rounded text-xs font-semibold transition-all ${adminSubTab === 'users' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      Access Control
                    </button>
                    <button
                      onClick={() => setAdminSubTab('master')}
                      className={`px-4 py-1.5 rounded text-xs font-semibold transition-all ${adminSubTab === 'master' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      Master Data
                    </button>
                    <button
                      onClick={() => setAdminSubTab('email')}
                      className={`px-4 py-1.5 rounded text-xs font-semibold transition-all ${adminSubTab === 'email' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      Email Config
                    </button>
                    <button
                      onClick={() => setAdminSubTab('logs')}
                      className={`px-4 py-1.5 rounded text-xs font-semibold transition-all ${adminSubTab === 'logs' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      Logs
                    </button>
                  </div>
                  <a
                    href="/builder"
                    className="bg-indigo-600 text-white px-5 py-2 rounded-md text-sm font-semibold hover:bg-indigo-700 transition-all flex items-center shadow-sm"
                  >
                    <span className="mr-2">✨</span> Template Builder
                  </a>
                </div>

                {adminSubTab === 'master' && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Master Data Management */}
                    <div className="space-y-8">
                      <div className="bg-white p-8 rounded-3xl border border-gray-100 shadow-sm">
                        <h3 className="text-xl font-black text-gray-900 mb-6 flex items-center">
                          <span className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center mr-3 text-sm">🏢</span>
                          Manage Departments
                        </h3>
                        <div className="flex space-x-3 mb-6">
                          <input
                            className="flex-1 p-4 border-2 border-gray-100 rounded-xl text-lg font-bold focus:border-indigo-500 focus:ring-0 transition-all"
                            placeholder="e.g. Finance"
                            value={newDeptName}
                            onChange={e => setNewDeptName(e.target.value)}
                          />
                          <button
                            onClick={async () => {
                              if (!newDeptName) return;
                              const res = await fetch('/api/departments', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ name: newDeptName })
                              });
                              if (res.ok) { fetchMasterData(); setNewDeptName(''); }
                            }}
                            className="bg-indigo-600 text-white px-6 py-2 rounded-xl text-sm font-bold hover:bg-indigo-700 transition-all shadow-md active:scale-95"
                          >
                            Add
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-3">
                          {departments.length === 0 && <p className="text-gray-400 text-base italic">No departments registered yet.</p>}
                          {departments.map(d => (
                            <div key={d.id} className="flex items-center bg-gray-50 text-gray-900 rounded-xl text-base font-black border border-gray-100 pl-4 pr-1 py-1 shadow-sm hover:border-indigo-200 transition-all group">
                              <span className="mr-2">{d.name}</span>
                              <button
                                onClick={async () => {
                                  if (confirm(`Delete ${d.name}?`)) {
                                    await fetch(`/api/departments/${d.id}`, { method: 'DELETE' });
                                    fetchMasterData();
                                  }
                                }}
                                className="w-8 h-8 flex items-center justify-center rounded-lg group-hover:bg-red-50 text-gray-300 group-hover:text-red-500 transition-all"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="bg-white p-8 rounded-3xl border border-gray-100 shadow-sm">
                        <h3 className="text-xl font-black text-gray-900 mb-6 flex items-center">
                          <span className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center mr-3 text-sm">📄</span>
                          Document Types
                        </h3>
                        <div className="flex space-x-3 mb-6">
                          <input
                            className="flex-1 p-4 border-2 border-gray-100 rounded-xl text-lg font-bold focus:border-indigo-500 focus:ring-0 transition-all"
                            placeholder="e.g. Invoice"
                            value={newDocTypeName}
                            onChange={e => setNewDocTypeName(e.target.value)}
                          />
                          <button
                            onClick={async () => {
                              if (!newDocTypeName) return;
                              const res = await fetch('/api/document-types', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ name: newDocTypeName })
                              });
                              if (res.ok) { fetchMasterData(); setNewDocTypeName(''); }
                            }}
                            className="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition-all shadow-sm"
                          >
                            Add
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-3">
                          {docTypes.length === 0 && <p className="text-gray-400 text-base italic">No document types registered yet.</p>}
                          {docTypes.map(t => (
                            <div key={t.id} className="flex items-center bg-gray-50 text-gray-900 rounded-xl text-base font-black border border-gray-100 pl-4 pr-1 py-1 shadow-sm hover:border-indigo-200 transition-all group">
                              <span className="mr-2">{t.name}</span>
                              <button
                                onClick={async () => {
                                  if (confirm(`Delete ${t.name}?`)) {
                                    await fetch(`/api/document-types/${t.id}`, { method: 'DELETE' });
                                    fetchMasterData();
                                  }
                                }}
                                className="w-8 h-8 flex items-center justify-center rounded-lg group-hover:bg-red-50 text-gray-300 group-hover:text-red-500 transition-all"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {adminSubTab === 'users' && (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 w-full space-y-6">
                    {/* Access Control Header */}
                    <div className="flex justify-between items-center mb-4">
                      <div className="flex items-center space-x-4">
                        <div className="relative">
                          <input
                            type="text"
                            placeholder="Search users..."
                            className="pl-10 pr-4 py-2 bg-gray-100 border-none rounded-xl text-sm font-bold focus:ring-2 focus:ring-indigo-500 w-64 transition-all"
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                          />
                          <svg className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                          </svg>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setEditingUserId(null);
                          setNewUser({ email: '', full_name: '', job_position: '', password: '', role: 'User', access_scope: 'global', permissions: { departments: [] as string[] } });
                          setIsUserDetailOpen(true);
                        }}
                        className="bg-indigo-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition-all shadow-sm flex items-center gap-1.5"
                      >
                        <span className="text-base font-light">+</span> New User
                      </button>
                    </div>

                    {/* User List View */}
                    <div className="bg-white rounded-3xl border border-gray-100 shadow-xl overflow-hidden">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="bg-gray-50/50 border-b border-gray-100">
                            <th className="px-6 py-4 text-xs font-black text-gray-400 uppercase tracking-widest">Name</th>
                            <th className="px-6 py-4 text-xs font-black text-gray-400 uppercase tracking-widest">Login</th>
                            <th className="px-6 py-4 text-xs font-black text-gray-400 uppercase tracking-widest">Provider</th>
                            <th className="px-6 py-4 text-xs font-black text-gray-400 uppercase tracking-widest text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                          {users.filter(u =>
                            u.full_name.toLowerCase().includes(userSearch.toLowerCase()) ||
                            u.email.toLowerCase().includes(userSearch.toLowerCase())
                          ).map(u => (
                            <tr key={u.id} className="hover:bg-gray-50/80 transition-all group cursor-pointer" onClick={() => {
                              setEditingUserId(u.id);
                              setNewUser({
                                email: u.email,
                                full_name: u.full_name,
                                job_position: u.job_position || '',
                                password: '',
                                role: u.role,
                                access_scope: u.access_scope || 'global',
                                permissions: { departments: u.permissions?.departments || [] }
                              });
                              setIsUserDetailOpen(true);
                            }}>
                              <td className="px-5 py-3">
                                <div className="flex items-center space-x-3">
                                  <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-semibold text-sm">
                                    {u.full_name.charAt(0)}
                                  </div>
                                  <div>
                                    <p className="text-sm font-medium text-gray-800">{u.full_name}</p>
                                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${u.role === 'Admin' ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'}`}>
                                      {u.role}
                                    </span>
                                  </div>
                                </div>
                              </td>
                              <td className="px-5 py-3">
                                <p className="text-sm text-gray-500">{u.email}</p>
                              </td>
                              <td className="px-5 py-3">
                                <span className="text-[10px] font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                                  {u.auth_provider || 'local'}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-right">
                                <div className="flex items-center justify-end space-x-2">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setEditingUserId(u.id);
                                      setNewUser({
                                        email: u.email,
                                        full_name: u.full_name,
                                        job_position: u.job_position || '',
                                        password: '',
                                        role: u.role,
                                        access_scope: u.access_scope || 'global',
                                        permissions: { departments: u.permissions?.departments || [] }
                                      });
                                      setIsUserDetailOpen(true);
                                    }}
                                    className="p-2 text-gray-400 hover:text-indigo-600 hover:bg-white rounded-lg transition-all active:scale-95"
                                  >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                  </button>
                                  {user.id !== u.id && (
                                    <button
                                      onClick={async (e) => {
                                        e.stopPropagation();
                                        if (confirm(`Delete user ${u.email}?`)) {
                                          await fetch(`/api/users/${u.id}`, { method: 'DELETE' });
                                          fetchAdminData();
                                        }
                                      }}
                                      className="p-2 text-gray-400 hover:text-red-500 hover:bg-white rounded-lg transition-all active:scale-95"
                                    >
                                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* User Detail View (Overlay-style like Odoo) */}
                    {isUserDetailOpen && (
                      <div className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm z-[60] flex items-center justify-end animate-in fade-in duration-300">
                        <div className="w-full max-w-2xl h-full bg-white shadow-2xl flex flex-col animate-in slide-in-from-right-full duration-500">
                          {/* Detail Header */}
                          <div className="px-8 py-6 border-b flex justify-between items-center bg-gray-50/50">
                            <div className="flex items-center space-x-4">
                              <button
                                onClick={() => setIsUserDetailOpen(false)}
                                className="p-2 hover:bg-white rounded-xl transition-all text-gray-400 hover:text-gray-600"
                              >
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" /></svg>
                              </button>
                              <div>
                                <h3 className="text-xl font-black text-gray-900">{editingUserId ? 'Edit User' : 'New User'}</h3>
                                <p className="text-xs text-gray-400 font-bold uppercase tracking-widest">Advanced Settings</p>
                              </div>
                            </div>
                            <div className="flex space-x-3">
                              <button
                                onClick={async () => {
                                  const method = editingUserId ? 'PUT' : 'POST';
                                  const url = editingUserId ? `/api/users/${editingUserId}` : '/api/users';
                                  const res = await fetch(url, {
                                    method,
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(newUser)
                                  });
                                  if (res.ok) {
                                    fetchAdminData();
                                    setIsUserDetailOpen(false);
                                    setEditingUserId(null);
                                    setNewUser({ email: '', full_name: '', job_position: '', password: '', role: 'User', access_scope: 'global', permissions: { departments: [] } });
                                  }
                                }}
                                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 transition-all shadow-sm"
                              >
                                Save Changes
                              </button>
                            </div>
                          </div>

                          {/* Detail Content */}
                          <div className="flex-1 overflow-y-auto p-12 space-y-10">
                            <div className="flex items-center space-x-8">
                              <div className="w-24 h-24 rounded-3xl bg-indigo-600 flex items-center justify-center text-white text-4xl font-black shadow-xl">
                                {newUser.full_name?.charAt(0) || '?'}
                              </div>
                              <div className="flex-1 space-y-2">
                                <input
                                  className="text-4xl font-black text-gray-900 border-none p-0 focus:ring-0 w-full placeholder:text-gray-200"
                                  placeholder="Abdul Majid Qamar"
                                  value={newUser.full_name}
                                  onChange={e => setNewUser({ ...newUser, full_name: e.target.value })}
                                />
                                <p className="text-sm font-bold text-gray-400 uppercase tracking-widest">Public Identity</p>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 gap-8 pt-8 border-t border-gray-100">
                              <div className="space-y-6">
                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Account Details</h4>
                                <div className="grid grid-cols-1 gap-6">
                                  <div>
                                    <label className="block text-xs font-medium text-gray-500 mb-1">Email Address</label>
                                    <input
                                      className="w-full text-lg font-bold text-gray-700 border-b-2 border-gray-100 focus:border-indigo-600 p-0 py-2 transition-all border-none focus:ring-0 bg-transparent disabled:opacity-50"
                                      placeholder="abdulmajid@berkeleyuae.com"
                                      value={newUser.email}
                                      onChange={e => setNewUser({ ...newUser, email: e.target.value })}
                                      disabled={!!editingUserId}
                                    />
                                  </div>
                                  <div>
                                    <label className="block text-xs font-medium text-gray-500 mb-1">Job Position</label>
                                    <input
                                      className="w-full text-lg font-bold text-gray-700 border-b-2 border-gray-100 focus:border-indigo-600 p-0 py-2 transition-all border-none focus:ring-0 bg-transparent"
                                      placeholder="Senior Engineering Manager"
                                      value={newUser.job_position}
                                      onChange={e => setNewUser({ ...newUser, job_position: e.target.value })}
                                    />
                                  </div>
                                  <div className="grid grid-cols-2 gap-8">
                                    <div>
                                      <label className="block text-xs font-medium text-gray-500 mb-1">User Type</label>
                                      <div className="flex items-center space-x-6 py-2">
                                        <label className="flex items-center cursor-pointer group">
                                          <input
                                            type="radio"
                                            name="role"
                                            className="w-4 h-4 text-indigo-600 border-gray-300 focus:ring-indigo-500"
                                            checked={newUser.role === 'User'}
                                            onChange={() => setNewUser({ ...newUser, role: 'User' })}
                                          />
                                          <span className={`ml-2 text-sm font-bold group-hover:text-indigo-600 transition-colors ${newUser.role === 'User' ? 'text-indigo-600' : 'text-gray-500'}`}>Internal User</span>
                                        </label>
                                        <label className="flex items-center cursor-pointer group">
                                          <input
                                            type="radio"
                                            name="role"
                                            className="w-4 h-4 text-indigo-600 border-gray-300 focus:ring-indigo-500"
                                            checked={newUser.role === 'Admin'}
                                            onChange={() => setNewUser({ ...newUser, role: 'Admin' })}
                                          />
                                          <span className={`ml-2 text-sm font-bold group-hover:text-indigo-600 transition-colors ${newUser.role === 'Admin' ? 'text-indigo-600' : 'text-gray-500'}`}>Administrator</span>
                                        </label>
                                      </div>
                                    </div>
                                    <div>
                                      <label className="block text-xs font-medium text-gray-500 mb-1">Password</label>
                                      <input
                                        type="password"
                                        className="w-full text-lg font-bold text-gray-700 border-b-2 border-gray-100 focus:border-indigo-600 p-0 py-2 transition-all border-none focus:ring-0 bg-transparent placeholder:text-gray-200"
                                        placeholder="••••••••"
                                        value={newUser.password}
                                        onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                                      />
                                    </div>
                                  </div>
                                </div>

                                <div className="space-y-6 pt-8 border-t border-gray-100">
                                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Document Access Scope</h4>
                                  <div className="grid grid-cols-1 gap-4">
                                    {[
                                      { id: 'global', title: 'Global Access', desc: 'Can view all documents in the system.' },
                                      { id: 'department', title: 'Department Only', desc: 'Restricted to documents in assigned departments.' },
                                      { id: 'own', title: 'Own Documents Only', desc: 'Can only see documents they created.' }
                                    ].map((scope) => (
                                      <label key={scope.id} className={`flex items-start p-4 rounded-2xl border-2 cursor-pointer transition-all ${newUser.access_scope === scope.id ? 'bg-indigo-50 border-indigo-600' : 'bg-white border-gray-100 hover:border-indigo-200'}`}>
                                        <input
                                          type="radio"
                                          name="access_scope"
                                          className="mt-1 w-4 h-4 text-indigo-600 border-gray-300 focus:ring-indigo-500"
                                          checked={newUser.access_scope === scope.id}
                                          onChange={() => setNewUser({ ...newUser, access_scope: scope.id as any })}
                                        />
                                        <div className="ml-4">
                                          <p className={`text-sm font-black ${newUser.access_scope === scope.id ? 'text-indigo-900' : 'text-gray-900'}`}>{scope.title}</p>
                                          <p className="text-xs text-gray-500 font-bold">{scope.desc}</p>
                                        </div>
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              </div>


                              <div className="space-y-6 pt-8 border-t border-gray-100">
                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Access Rights</h4>
                                <div>
                                  <label className="block text-xs font-medium text-gray-500 mb-2">Allowed Departments</label>
                                  <div className="grid grid-cols-2 gap-3">
                                    {departments.map(dept => (
                                      <label key={dept.id} className={`flex items-center justify-between p-3 rounded-2xl border-2 transition-all cursor-pointer ${newUser.permissions?.departments?.includes(dept.name) ? 'bg-indigo-50 border-indigo-600 shadow-sm' : 'bg-white border-gray-100 hover:border-indigo-200'}`}>
                                        <span className={`text-sm font-bold ${newUser.permissions?.departments?.includes(dept.name) ? 'text-indigo-700' : 'text-gray-600'}`}>
                                          {dept.name}
                                        </span>
                                        <input
                                          type="checkbox"
                                          className="w-5 h-5 text-indigo-600 border-gray-300 rounded-lg focus:ring-indigo-500"
                                          checked={newUser.permissions?.departments?.includes(dept.name)}
                                          onChange={(e) => {
                                            const depts = e.target.checked
                                              ? [...(newUser.permissions?.departments || []), dept.name]
                                              : (newUser.permissions?.departments || []).filter(d => d !== dept.name);
                                            setNewUser({ ...newUser, permissions: { ...newUser.permissions, departments: depts } });
                                          }}
                                        />
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {adminSubTab === 'email' && (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="bg-white p-10 rounded-3xl border-2 border-indigo-50 shadow-xl relative">
                      <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-50/50 rounded-full -mr-32 -mt-32 pointer-events-none"></div>
                      <div className="flex items-center justify-between mb-10 relative z-10">
                        <div className="flex items-center space-x-4">
                          <div className="p-3 bg-indigo-600 rounded-2xl text-white shadow-lg">
                            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                          </div>
                          <div>
                            <h3 className="text-3xl font-black text-gray-900 tracking-tight">Email System</h3>
                            <p className="text-base text-gray-500 font-medium">Configure SendGrid SMTP for notifications</p>
                          </div>
                        </div>
                        <div className="flex space-x-2">
                          <span className="text-xs font-black uppercase tracking-widest bg-emerald-100 text-emerald-700 px-4 py-2 rounded-full border border-emerald-200">PROVIDER: SENDGRID</span>
                          <span className="text-xs font-black uppercase tracking-widest bg-gray-100 text-gray-400 px-4 py-2 rounded-full border border-gray-200">OUTGOING ONLY</span>
                        </div>
                      </div>

                      <div className="space-y-6 bg-gray-50/50 p-8 rounded-2xl border border-gray-100 relative z-10">
                        <h4 className="text-lg font-black text-indigo-700 uppercase tracking-widest mb-4">SMTP Configuration</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div className="col-span-2">
                            <label className="block text-sm font-black text-gray-400 mb-2 uppercase tracking-widest">SMTP Hostname</label>
                            <input
                              className="w-full p-4 text-lg font-bold bg-white border-2 border-gray-100 rounded-2xl focus:border-indigo-500 focus:ring-0 transition-all font-mono"
                              placeholder="smtp.sendgrid.net"
                              value={emailConfig.smtp_server}
                              onChange={e => setEmailConfig({ ...emailConfig, smtp_server: e.target.value })}
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-black text-gray-400 mb-2 uppercase tracking-widest">Port</label>
                            <input
                              type="number"
                              className="w-full p-4 text-lg font-bold bg-white border-2 border-gray-100 rounded-2xl focus:border-indigo-500 focus:ring-0 transition-all font-mono"
                              value={emailConfig.smtp_port}
                              onChange={e => setEmailConfig({ ...emailConfig, smtp_port: parseInt(e.target.value) || 0 })}
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-black text-gray-400 mb-2 uppercase tracking-widest">Encryption</label>
                            <select
                              className="w-full p-4 text-lg font-bold bg-white border-2 border-gray-100 rounded-2xl focus:border-indigo-500 focus:ring-0 transition-all"
                              value={emailConfig.encryption}
                              onChange={e => setEmailConfig({ ...emailConfig, encryption: e.target.value })}
                            >
                              <option value="none">None</option>
                              <option value="tls">TLS/STARTTLS (587)</option>
                              <option value="ssl">SSL (465)</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-black text-gray-400 mb-2 uppercase tracking-widest">Sender Email (From)</label>
                            <input
                              className="w-full p-4 text-lg font-bold bg-white border-2 border-gray-100 rounded-2xl focus:border-indigo-500 focus:ring-0 transition-all"
                              placeholder="notifications@yourdomain.com"
                              value={emailConfig.from_email}
                              onChange={e => setEmailConfig({ ...emailConfig, from_email: e.target.value })}
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-black text-gray-400 mb-2 uppercase tracking-widest">API User</label>
                            <input
                              className="w-full p-4 text-lg font-bold bg-white border-2 border-gray-100 rounded-2xl focus:border-indigo-500 focus:ring-0 transition-all"
                              value={emailConfig.username}
                              onChange={e => setEmailConfig({ ...emailConfig, username: e.target.value })}
                              placeholder="apikey"
                            />
                          </div>
                        </div>

                        <div className="pt-6 border-t border-gray-200 mt-6">
                          <div className="bg-indigo-600 p-6 rounded-2xl shadow-lg">
                            <h4 className="text-white text-sm font-black uppercase tracking-widest mb-4">Credentials</h4>
                            <div>
                              <label className="block text-xs font-black text-indigo-200 mb-2 uppercase tracking-widest">SendGrid API Key (Password)</label>
                              <input
                                type="password"
                                placeholder="SG.xxxxxxxxxxxxxxxxxxxxxxxx"
                                className="w-full p-4 text-lg font-bold bg-white/10 text-white border-2 border-white/20 rounded-2xl focus:bg-white focus:text-gray-900 transition-all placeholder:text-white/30"
                                value={emailPassword}
                                onChange={e => setEmailPassword(e.target.value)}
                              />
                            </div>
                          </div>
                        </div>

                        <div className="pt-6 flex flex-col md:flex-row items-center justify-between gap-4">
                          <div className="flex-1 w-full">
                            <label className="block text-xs font-black text-gray-400 mb-2 uppercase tracking-widest">Test Recipient</label>
                            <div className="flex space-x-2">
                              <input
                                placeholder="test@example.com"
                                className="flex-1 p-3 border-2 border-gray-100 rounded-xl text-sm font-bold focus:border-indigo-500 focus:ring-0 transition-all"
                                value={testEmail}
                                onChange={e => setTestEmail(e.target.value)}
                              />
                              <button
                                onClick={handleTestEmail}
                                className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded text-xs font-medium hover:bg-gray-200 transition-all"
                              >
                                Test
                              </button>
                            </div>
                          </div>
                          <button
                            onClick={handleSaveEmailConfig}
                            className="px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md shadow-sm hover:bg-indigo-700 transition-all"
                          >
                            Save Configuration
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {adminSubTab === "logs" && (
                  <AuditLogViewer fetchEmailLogs={fetchEmailLogs} emailLogs={emailLogs} />
                )}
              </div>
            )}

            {isSigningOpen && (
              <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-0 sm:p-4 backdrop-blur-md animate-in fade-in duration-300">
                <div className="bg-white w-[95%] sm:w-full h-auto max-h-[90vh] sm:max-w-lg rounded-3xl sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col transform transition-all animate-in zoom-in-95 duration-300">
                  <div className="bg-indigo-600 px-6 py-5 flex justify-between items-center text-white">
                    <h3 className="font-bold text-lg flex items-center">
                      <span className="mr-3 bg-white/20 p-2 rounded-lg">✍️</span>
                      Sign Document
                    </h3>
                    <button onClick={() => setIsSigningOpen(false)} className="text-white/80 hover:text-white transition-colors bg-white/10 hover:bg-white/20 rounded-full p-1">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                  <div className="flex-1 p-6 overflow-y-auto">
                    {/* Mode Selector (Full vs Initial) */}
                    <div className="flex bg-gray-100 p-1 rounded-xl mb-6 shadow-inner">
                      <button
                        onClick={() => {
                          setSigType('full');
                          setUseSavedSignature(false);
                        }}
                        className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all ${sigType === 'full' ? 'bg-white text-indigo-700 shadow-md' : 'text-gray-500 hover:text-gray-700'
                          }`}
                      >
                        Full Signature
                      </button>
                      <button
                        onClick={() => {
                          setSigType('initial');
                          setUseSavedSignature(false);
                        }}
                        className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all ${sigType === 'initial' ? 'bg-white text-indigo-700 shadow-md' : 'text-gray-500 hover:text-gray-700'
                          }`}
                      >
                        Initials
                      </button>
                    </div>

                    {/* Method Selector Tabs */}
                    {!useSavedSignature && (
                      <div className="flex border-b border-gray-100 mb-6">
                        <button
                          onClick={() => setSigMethod('draw')}
                          className={`flex-1 pb-3 text-sm font-bold transition-all flex items-center justify-center gap-2 ${sigMethod === 'draw' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-400'}`}
                        >
                          <span>✍️</span> Draw
                        </button>
                        <button
                          onClick={() => setSigMethod('image')}
                          className={`flex-1 pb-3 text-sm font-bold transition-all flex items-center justify-center gap-2 ${sigMethod === 'image' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-400'}`}
                        >
                          <span>🖼️</span> Image
                        </button>
                      </div>
                    )}

                    <div className="flex justify-between items-center mb-4">
                      <p className="text-sm text-gray-600 font-semibold uppercase tracking-wider">
                        {useSavedSignature ? `Saved ${sigType}` : (sigMethod === 'draw' ? `Draw ${sigType === 'full' ? 'signature' : 'initials'}` : `Upload ${sigType} image`)}
                      </p>
                      {((sigType === 'full' && user?.saved_signature_url) || (sigType === 'initial' && user?.saved_initials_url)) && (
                        <button
                          onClick={() => {
                            setUseSavedSignature(!useSavedSignature);
                            if (useSavedSignature) setSigMethod('draw');
                          }}
                          className="text-xs font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-3 py-1.5 rounded-lg border border-indigo-100 transition-all shadow-sm active:scale-95"
                        >
                          {useSavedSignature ? '✍️ New' : '📂 Use Saved'}
                        </button>
                      )}
                    </div>

                    {useSavedSignature ? (
                      <div className="border-2 border-indigo-100 rounded-2xl bg-indigo-50/20 flex items-center justify-center min-h-[220px] overflow-hidden">
                        <img
                          src={sigType === 'initial' ? user?.saved_initials_url : user?.saved_signature_url}
                          alt={`Saved ${sigType}`}
                          className="max-h-full max-w-full object-contain mix-blend-multiply transition-transform hover:scale-110 duration-500"
                        />
                      </div>
                    ) : sigMethod === 'draw' ? (
                      <div className="border-2 border-dashed border-gray-200 rounded-2xl bg-gray-50/50 hover:bg-white transition-all relative h-64 md:h-56 overflow-hidden active:border-indigo-400 group" style={{ touchAction: 'none' }}>
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20 group-hover:opacity-10 transition-opacity">
                          <p className="text-xl font-bold text-gray-400 uppercase tracking-[0.2em] transform -rotate-12 italic">Sign Here</p>
                        </div>
                        <SignatureCanvas
                          ref={sigCanvas}
                          canvasProps={{ className: 'w-full h-full cursor-crosshair relative z-10' }}
                          backgroundColor="rgba(0,0,0,0)"
                        />
                      </div>
                    ) : (
                      <div className="border-2 border-dashed border-gray-300 rounded-lg bg-gray-50 flex flex-col items-center justify-center h-48 transition-all hover:bg-white overflow-hidden p-4">
                        {uploadedSig ? (
                          <div className="relative w-full h-full flex items-center justify-center">
                            <img src={uploadedSig} alt="Uploaded preview" className="max-h-full max-w-full object-contain mix-blend-multiply" />
                            <button
                              onClick={() => setUploadedSig(null)}
                              className="absolute top-0 right-0 bg-red-100 text-red-600 p-1 rounded-full hover:bg-red-200 transition-colors"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                          </div>
                        ) : (
                          <label className="flex flex-col items-center cursor-pointer group">
                            <svg className="w-10 h-10 text-gray-300 group-hover:text-indigo-400 transition-colors mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                            <span className="text-xs text-gray-400 group-hover:text-indigo-600 font-medium">Click to upload image</span>
                            <input
                              type="file"
                              className="hidden"
                              accept="image/*"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                  const reader = new FileReader();
                                  reader.onload = (rv) => setUploadedSig(rv.target?.result as string);
                                  reader.readAsDataURL(file);
                                }
                              }}
                            />
                          </label>
                        )}
                      </div>
                    )}

                    <div className="flex justify-between mt-3 text-xs text-gray-400 font-medium">
                      <div>
                        {!useSavedSignature && sigMethod === 'draw' && (
                          <button onClick={() => sigCanvas.current?.clear()} className="hover:text-red-500 underline decoration-dotted">Clear</button>
                        )}
                      </div>
                      {!useSavedSignature && (
                        <label className="flex items-center space-x-2 cursor-pointer group hover:text-indigo-600 transition-colors">
                          <input
                            type="checkbox"
                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                            checked={shouldSaveSignature}
                            onChange={(e) => setShouldSaveSignature(e.target.checked)}
                          />
                          <span>Save {sigType} for future use</span>
                        </label>
                      )}
                    </div>

                    <div className="mt-6 border-t border-gray-100 pt-6">
                      <label className="block text-xs font-black text-gray-400 uppercase tracking-[0.2em] mb-2 px-1">
                        Signer Note (Optional)
                      </label>
                      <textarea
                        value={signingComment}
                        onChange={(e) => setSigningComment(e.target.value)}
                        placeholder="Add a comment or justification for your signature..."
                        className="w-full bg-gray-50 border-2 border-gray-100 rounded-xl p-4 text-sm font-medium text-gray-900 focus:bg-white focus:border-indigo-300 transition-all outline-none resize-none h-24 shadow-inner"
                      />
                    </div>
                  </div>
                  <div className="px-6 py-4 bg-gray-50 border-t flex justify-end space-x-3">
                    <button
                      onClick={() => setIsSigningOpen(false)}
                      className="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={submitSignature}
                      disabled={isSigning}
                      className={`px-6 py-2 rounded-lg text-sm font-bold shadow-sm transition-all transform active:scale-95 flex items-center ${isSigning ? 'bg-indigo-400 cursor-not-allowed text-white/50' : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                        }`}
                    >
                      {isSigning ? (
                        <>
                          <svg className="animate-spin -ml-1 mr-3 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          Signing...
                        </>
                      ) : 'Adopt & Sign'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {selectedRequest && (
              <RequestDetailModal
                request={selectedRequest}
                onClose={() => setSelectedRequest(null)}
                user={user}
                onRefresh={fetchRequests}
                onViewDoc={handleViewRequestDoc}
                onViewAttachment={handleViewAttachment}
              />
            )}

            {/* Document Preview Modal */}
            {previewDoc && (
              <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
                <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
                  <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-white">
                    <h2 className="text-lg font-bold text-slate-800 truncate pr-4">{previewDoc.name}</h2>
                    <div className="flex items-center space-x-2">
                      <a
                        href={previewDoc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
                        title="Open in New Tab"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                      </a>
                      <button
                        onClick={() => setPreviewDoc(null)}
                        className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                      >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  </div>
                  <div className="flex-1 bg-slate-100 overflow-auto flex items-center justify-center">
                    {(previewDoc.name.toLowerCase().endsWith('.pdf') || previewDoc.url.toLowerCase().includes('.pdf') || previewDoc.url.toLowerCase().includes('rsct=application%2fpdf')) ? (
                      <iframe
                        src={`${previewDoc.url}${previewDoc.url.includes('#') ? '' : '#toolbar=0'}`}
                        className="w-full h-full border-none"
                        title="PDF Preview"
                      />
                    ) : (
                      <img
                        src={previewDoc.url}
                        alt={previewDoc.name}
                        className="max-w-full max-h-full object-contain shadow-lg rounded-lg"
                        onError={(e) => {
                          // Fallback for cases where auto-detection might fail but it's actually an image
                          const target = e.target as HTMLImageElement;
                          if (target.src.includes('rsct=application%2fpdf')) {
                            console.warn("Image preview failed, might be a PDF mislabeled?");
                          }
                        }}
                      />
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
