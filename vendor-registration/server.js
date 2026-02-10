const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const cors = require('cors');
const PDFDocument = require('pdfkit');

const app = express();
const PORT = process.env.PORT || 3000;

// Basic Authentication credentials for uploads folder
const UPLOADS_USERNAME = 'procurement@berkeleyuae.com';
const UPLOADS_PASSWORD = 'Berk_2351086$';

// Basic Authentication middleware
function basicAuth(req, res, next) {
    console.log('[AUTH] Checking authentication for:', req.path);
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Basic ')) {
        console.log('[AUTH] No authorization header found');
        // If it's a browser request for an HTML page, redirect to login
        if (req.accepts('html') && !req.path.startsWith('/api/')) {
            return res.redirect('/login');
        }
        res.setHeader('WWW-Authenticate', 'Basic realm="Uploads Folder"');
        return res.status(401).json({ error: 'Authentication required' });
    }

    // Extract credentials from Authorization header
    const base64Credentials = authHeader.split(' ')[1];
    let credentials;
    try {
        credentials = Buffer.from(base64Credentials, 'base64').toString('utf-8');
    } catch (e) {
        return res.status(401).json({ error: 'Invalid authentication format' });
    }
    const [username, password] = credentials.split(':');

    // Verify credentials
    if (username === UPLOADS_USERNAME && password === UPLOADS_PASSWORD) {
        console.log('[AUTH] Authentication successful');
        return next();
    } else {
        console.log('[AUTH] Invalid credentials');
        if (req.accepts('html') && !req.path.startsWith('/api/')) {
            return res.redirect('/login');
        }
        res.setHeader('WWW-Authenticate', 'Basic realm="Uploads Folder"');
        return res.status(401).json({ error: 'Invalid credentials' });
    }
}

// Enable CORS for all origins including file:// protocol
app.use(cors({
    origin: function (origin, callback) {
        // Allow requests with no origin (like mobile apps, Postman, or file://)
        if (!origin || origin.startsWith('file://') || origin.startsWith('null')) {
            return callback(null, true);
        }
        // Allow all origins for development
        callback(null, true);
    },
    credentials: true,
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Create vendors directory if it doesn't exist
// Files will be stored in /app/uploads (Docker - mounted from /var/www/attachments) or D:\Vendors (Windows)
// Check if running in Docker container, otherwise use D:\Vendors
const uploadsDir = fs.existsSync('/app/uploads') ? '/app/uploads' : (fs.existsSync('/app/vendors') ? '/app/vendors' : 'D:\\Vendors');
if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir, { recursive: true });
    console.log(`Created vendors directory: ${uploadsDir}`);
}
console.log(`Vendor files will be stored in: ${uploadsDir}`);

// Function to sanitize company name for folder name
function sanitizeFolderName(companyName) {
    return companyName
        .trim()
        .replace(/[<>:"/\\|?*]/g, '') // Remove invalid characters
        .replace(/\s+/g, '_') // Replace spaces with underscores
        .substring(0, 100); // Limit length
}

// Function to get or create company folder for each submission
// Folder name format: CompanyName_SubmissionID (e.g., ABC_Company_SUB-1234567890-abc123)
function getCompanyFolder(companyName, submissionId) {
    const sanitizedName = sanitizeFolderName(companyName);
    // Create unique folder per submission using company name and submission ID
    const folderPath = path.join(uploadsDir, `${sanitizedName}_${submissionId}`);

    // Create the folder if it doesn't exist
    if (!fs.existsSync(folderPath)) {
        fs.mkdirSync(folderPath, { recursive: true });
    }

    return folderPath;
}

// Function to generate PDF report from submission data
function generatePDFReport(submission, companyFolder) {
    return new Promise((resolve, reject) => {
        try {
            const pdfFileName = `Vendor_Registration_${submission.submissionId}.pdf`;
            const pdfPath = path.join(companyFolder, pdfFileName);
            const doc = new PDFDocument({ margin: 50 });
            const stream = fs.createWriteStream(pdfPath);

            doc.pipe(stream);

            // Header
            doc.fontSize(20).font('Helvetica-Bold').text('Vendor Registration Form', { align: 'center' });
            doc.moveDown();
            doc.fontSize(12).font('Helvetica').text(`Submission ID: ${submission.submissionId}`, { align: 'center' });
            doc.text(`Date: ${new Date(submission.timestamp).toLocaleString()}`, { align: 'center' });
            doc.moveDown(2);

            // Helper function to add section
            const addSection = (title, data) => {
                doc.fontSize(14).font('Helvetica-Bold').text(title, { underline: true });
                doc.moveDown(0.5);
                doc.fontSize(10).font('Helvetica');

                Object.keys(data).forEach(key => {
                    if (data[key] !== undefined && data[key] !== null && data[key] !== '') {
                        const label = key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();
                        let value = data[key];

                        if (typeof value === 'boolean') {
                            value = value ? 'Yes' : 'No';
                        } else if (Array.isArray(value)) {
                            value = value.length > 0 ? value.join(', ') : 'None';
                        }

                        doc.text(`${label}: ${value}`, { indent: 20 });
                    }
                });
                doc.moveDown(1);
            };

            // Section 1: Vendor Name & Address
            addSection('Section 1: Vendor Name & Address', {
                'Company Name': submission.companyName,
                'Telephone': submission.telephone,
                'P.O. Box': submission.poBox,
                'Country': submission.country,
                'Emirates': submission.emirates,
                'Head Office Address': submission.headOfficeAddress,
                'Serving Emirates': submission.servingEmirates,
                'Help Desk Email': submission.helpDeskEmail,
                'Help Desk Contact': submission.helpDeskContact,
                'Website': submission.website
            });

            // Section 2: Company Details
            addSection('Section 2: Company Details', {
                'Trade License Number': submission.tradeLicenseNumber,
                'Trade License Issue Date': submission.tradeLicenseIssueDate,
                'Trade License Validity': submission.tradeLicenseValidity,
                'Issuing Authority': submission.issuingAuthority,
                'VAT Certificate': submission.vatCertificate
            });

            // Section 3: Owner / Partners
            addSection('Section 3: Owner / Partners', {
                'Owner Name': submission.ownerName,
                'Partner Name': submission.partnerName
            });

            // Section 4: Bank Accounts
            addSection('Section 4: Bank Accounts', {
                'Account Name': submission.accountName,
                'Bank Name': submission.bankName,
                'Bank Branch': submission.bankBranch,
                'Account Number': submission.accountNumber,
                'IBAN Number': submission.ibanNumber,
                'Account Currency': submission.accountCurrency
            });

            // Section 5: References
            addSection('Section 5: References', {
                'Reference 1': submission.reference01,
                'Reference 2': submission.reference02,
                'Reference 3': submission.reference03,
                'Reference 4': submission.reference04,
                'Reference 5': submission.reference05
            });

            // Section 6: Key Contacts
            const contacts = [];
            for (let i = 1; i <= 5; i++) {
                const name = submission[`contact0${i}Name`];
                const email = submission[`contact0${i}Email`];
                const phone = submission[`contact0${i}Phone`];
                if (name || email || phone) {
                    contacts.push(`Contact ${i}: ${name || 'N/A'} | ${email || 'N/A'} | ${phone || 'N/A'}`);
                }
            }
            if (contacts.length > 0) {
                doc.fontSize(14).font('Helvetica-Bold').text('Section 6: Key Contacts', { underline: true });
                doc.moveDown(0.5);
                doc.fontSize(10).font('Helvetica');
                contacts.forEach(contact => {
                    doc.text(contact, { indent: 20 });
                });
                doc.moveDown(1);
            }

            // Section 7: Documents
            addSection('Section 7: Documents', {
                'Trade License': submission.docTradeLicense ? 'Yes' : 'No',
                'Owner Passport': submission.docOwnerPassport ? 'Yes' : 'No',
                'Bank Statement': submission.docBankStatement ? 'Yes' : 'No',
                'VAT Certificate': submission.docVatCertificate ? 'Yes' : 'No',
                'Company Profile': submission.docCompanyProfile ? 'Yes' : 'No',
                'Financial Statement': submission.docFinancialStatement ? 'Yes' : 'No'
            });

            // Section 8: Insurances
            addSection('Section 8: Insurances', {
                'Public Liability': submission.publicLiability,
                'Employer Liability': submission.employerLiability,
                'Workman Compensation': submission.workmanCompensation,
                'Contractors Risk Insurance': submission.contractorsRiskInsurance
            });

            // Section 9: ESG & QHSE Requirements
            addSection('Section 9: ESG & QHSE Requirements', {
                'IMS Certification': submission.imsCertification,
                'EcoVadis Assessment': submission.ecovadisAssessment,
                'Hazard Identification': submission.hazardIdentification,
                'Quality Policy': submission.qualityPolicy,
                'Health & Safety Policy': submission.healthSafetyPolicy,
                'Environment Policy': submission.environmentPolicy,
                'Energy Policy': submission.energyPolicy,
                'Labor Standards': submission.laborStandards,
                'Commitment Disclosure': submission.commitmentDisclosure,
                'Supplier Code': submission.supplierCode,
                'Training Policy': submission.trainingPolicy,
                'Risk Assessment': submission.riskAssessment,
                'Employees Rights': submission.employeesRights,
                'Overtime Voluntary': submission.overtimeVoluntary,
                'Weekly Working Hours': submission.weeklyWorkingHours,
                'Youngest Employment Age': submission.youngestEmploymentAge
            });

            // Section 10: Payment Terms
            addSection('Section 10: Payment Terms', {
                'Credit Period': submission.creditPeriod,
                'Credit Other': submission.creditOtherText
            });

            // Section 11: Nature of Business
            addSection('Section 11: Nature of Business', {
                'Materials Supply': submission.materialsSupply,
                'AMC Services': submission.amcServices,
                'Manpower Supply': submission.manpowerSupply,
                'Other Services': submission.otherServices
            });

            // Section 12: Disclaimer and Declaration
            addSection('Section 12: Disclaimer and Declaration', {
                'Authorized Person Name': submission.authorizedPersonName,
                'Authorized Person Contact': submission.authorizedPersonContact,
                'Authorized Person Email': submission.authorizedPersonEmail
            });

            // Uploaded Files
            if (submission.files && Object.keys(submission.files).length > 0) {
                doc.fontSize(14).font('Helvetica-Bold').text('Uploaded Files', { underline: true });
                doc.moveDown(0.5);
                doc.fontSize(10).font('Helvetica');
                Object.keys(submission.files).forEach(fileField => {
                    const file = submission.files[fileField];
                    const fieldLabel = fileField.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();
                    doc.text(`${fieldLabel}: ${file.originalName} (${(file.size / 1024).toFixed(2)} KB)`, { indent: 20 });
                });
                doc.moveDown(1);
            }

            // Footer
            doc.moveDown(2);
            doc.fontSize(8).font('Helvetica').text(`Generated on ${new Date().toLocaleString()}`, { align: 'center' });

            doc.end();

            stream.on('finish', () => {
                console.log(`PDF report generated: ${pdfPath}`);
                resolve(pdfPath);
            });

            stream.on('error', (error) => {
                console.error('Error generating PDF:', error);
                reject(error);
            });

        } catch (error) {
            console.error('Error in PDF generation:', error);
            reject(error);
        }
    });
}

// Configure multer for file uploads - temporarily save to vendors dir
// We'll move files to company folders after processing
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, uploadsDir);
    },
    filename: function (req, file, cb) {
        // Generate unique filename with timestamp
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        const ext = path.extname(file.originalname);
        const name = path.basename(file.originalname, ext);
        cb(null, name + '-' + uniqueSuffix + ext);
    }
});

const upload = multer({
    storage: storage,
    limits: {
        fileSize: 5 * 1024 * 1024 // 5MB limit per file
    },
    fileFilter: function (req, file, cb) {
        // Allow specific file types
        const allowedTypes = /jpeg|jpg|png|pdf|doc|docx|txt/;
        const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
        const mimetype = allowedTypes.test(file.mimetype);

        if (mimetype && extname) {
            return cb(null, true);
        } else {
            cb(new Error('Invalid file type. Only images, PDFs, and documents are allowed.'));
        }
    },
    // Allow any field name - we'll filter in the route handler
    onError: function (err, next) {
        console.error('Multer error:', err);
        next(err);
    }
});

// Handle multiple file uploads - all fields from the vendor registration form
const uploadFields = [
    { name: 'tradeLicense', maxCount: 1 },
    { name: 'ownerPassport', maxCount: 1 },
    { name: 'bankStatement', maxCount: 1 },
    { name: 'vatCertificate', maxCount: 1 },
    { name: 'companyProfile', maxCount: 1 },
    { name: 'financialStatement', maxCount: 1 },
    { name: 'workmanCompFile', maxCount: 1 },
    { name: 'publicLiabilityFile', maxCount: 1 },
    { name: 'contractorsRiskFile', maxCount: 1 },
    { name: 'employerLiabilityFile', maxCount: 1 },
    { name: 'imsCertFile', maxCount: 1 },
    { name: 'ecovadisFile', maxCount: 1 },
    { name: 'hazardIdFile', maxCount: 1 },
    { name: 'qualityPolicyFile', maxCount: 1 },
    { name: 'healthSafetyPolicyFile', maxCount: 1 },
    { name: 'environmentPolicyFile', maxCount: 1 },
    { name: 'energyPolicyFile', maxCount: 1 },
    { name: 'laborStandardsFile', maxCount: 1 },
    { name: 'commitmentFile', maxCount: 1 },
    { name: 'supplierCodeFile', maxCount: 1 },
    { name: 'trainingPolicyFile', maxCount: 1 },
    { name: 'riskAssessmentFile', maxCount: 1 }
];

// Error handling middleware for multer errors
const handleMulterError = (err, req, res, next) => {
    if (err) {
        console.error('Multer error:', err);
        if (err.code === 'LIMIT_FILE_SIZE') {
            return res.status(400).json({
                success: false,
                error: 'File size too large. Maximum size allowed is 5MB.'
            });
        }
        return res.status(400).json({
            success: false,
            error: err.message || 'File upload error occurred'
        });
    }
    next();
};

// API endpoint to handle form submissions
app.post('/api/submit', (req, res, next) => {
    upload.any()(req, res, (err) => {
        if (err) {
            console.error('Multer error:', err);
            return res.status(400).json({
                success: false,
                error: err.message || 'File upload error occurred'
            });
        }
        next();
    });
}, async (req, res) => {
    try {
        // Debug: Log request info immediately - BEFORE processing files
        console.log('=== Form submission received ===');
        console.log('req.files exists:', !!req.files);
        console.log('req.files type:', typeof req.files);
        console.log('req.files is array:', Array.isArray(req.files));
        if (req.files) {
            if (Array.isArray(req.files)) {
                console.log('req.files length:', req.files.length);
                if (req.files.length > 0) {
                    console.log('First file:', {
                        fieldname: req.files[0].fieldname,
                        originalname: req.files[0].originalname,
                        filename: req.files[0].filename,
                        path: req.files[0].path
                    });
                }
            } else {
                console.log('req.files keys:', Object.keys(req.files));
            }
        } else {
            console.log('WARNING: req.files is undefined or null!');
        }

        // Get all form fields from request body
        const formData = req.body;
        const files = req.files || [];
        console.log('files variable length:', files.length || 'N/A');
        console.log('files is array:', Array.isArray(files));

        // Basic validation - check for company name and email
        if (!formData.companyName || !formData.helpDeskEmail) {
            return res.status(400).json({
                success: false,
                error: 'Company name and help desk email are required fields.'
            });
        }

        // Email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (formData.helpDeskEmail && !emailRegex.test(formData.helpDeskEmail)) {
            return res.status(400).json({
                success: false,
                error: 'Invalid email address.'
            });
        }

        // Generate submission ID first
        const submissionId = `SUB-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        // Get or create company folder for this submission (folder name = company name + submission ID)
        const companyFolder = getCompanyFolder(formData.companyName, submissionId);
        const companyFolderName = path.basename(companyFolder);

        // Process uploaded files and move them to company folder
        // When using upload.any(), files is an array, not an object
        const uploadedFiles = {};
        const filesArray = Array.isArray(files) ? files : (files ? Object.values(files).flat() : []);

        console.log(`Files received: ${filesArray.length} files`);
        console.log(`Files type: ${Array.isArray(files) ? 'Array' : typeof files}`);
        console.log(`req.files:`, req.files ? (Array.isArray(req.files) ? `Array[${req.files.length}]` : `Object with keys: ${Object.keys(req.files).join(', ')}`) : 'undefined');

        if (filesArray.length > 0) {
            console.log('Processing files...');
            filesArray.forEach((file, index) => {
                console.log(`File ${index + 1}:`, {
                    fieldname: file.fieldname,
                    originalname: file.originalname,
                    filename: file.filename,
                    path: file.path,
                    size: file.size
                });
            });
        } else {
            console.log('No files found in filesArray');
        }

        // Process and move all uploaded files to the company folder
        // This includes all document files (tradeLicense, ownerPassport, etc.) 
        // and all insurance/ESG files (workmanCompFile, publicLiabilityFile, etc.)
        filesArray.forEach(file => {
            if (file && file.fieldname) {
                const fieldName = file.fieldname;
                const oldPath = file.path;

                // Preserve original filename but ensure it's safe for filesystem
                const safeOriginalName = path.basename(file.originalname || file.filename);
                const ext = path.extname(safeOriginalName);
                const baseName = path.basename(safeOriginalName, ext);
                const sanitizedBaseName = baseName.replace(/[<>:"/\\|?*]/g, '_').substring(0, 100);
                const finalFilename = `${sanitizedBaseName}${ext}`;
                const newPath = path.join(companyFolder, finalFilename);

                console.log(`Moving file ${fieldName} (${file.originalname}) from ${oldPath} to ${newPath}`);

                // Move file to company folder
                try {
                    if (!fs.existsSync(oldPath)) {
                        console.error(`Source file does not exist: ${oldPath}`);
                        return;
                    }

                    // Ensure the company folder exists (should already exist, but double-check)
                    if (!fs.existsSync(companyFolder)) {
                        fs.mkdirSync(companyFolder, { recursive: true });
                    }

                    // Move the file to the company folder
                    fs.renameSync(oldPath, newPath);
                    console.log(`Successfully moved file ${fieldName} (${file.originalname}) to company folder: ${newPath}`);

                    uploadedFiles[fieldName] = {
                        filename: finalFilename,
                        originalName: file.originalname,
                        size: file.size,
                        path: newPath,
                        relativePath: path.join(companyFolderName, finalFilename), // Store relative path
                        mimetype: file.mimetype
                    };
                } catch (error) {
                    console.error(`Error moving file ${fieldName} (${file.originalname}):`, error);
                    // Try to copy instead of move if rename fails
                    try {
                        fs.copyFileSync(oldPath, newPath);
                        console.log(`Copied file ${fieldName} to company folder: ${newPath}`);
                        // Delete original file after successful copy
                        fs.unlinkSync(oldPath);
                        uploadedFiles[fieldName] = {
                            filename: finalFilename,
                            originalName: file.originalname,
                            size: file.size,
                            path: newPath,
                            relativePath: path.join(companyFolderName, finalFilename),
                            mimetype: file.mimetype
                        };
                    } catch (copyError) {
                        console.error(`Failed to copy file ${fieldName}:`, copyError);
                        // If both move and copy fail, still record the file info but keep it in original location
                        uploadedFiles[fieldName] = {
                            filename: file.filename,
                            originalName: file.originalname,
                            size: file.size,
                            path: oldPath,
                            relativePath: file.filename,
                            mimetype: file.mimetype,
                            error: 'Failed to move file to company folder'
                        };
                    }
                }
            } else {
                console.log('Skipping invalid file:', file);
            }
        });

        console.log(`Processed ${Object.keys(uploadedFiles).length} files successfully`);

        // Log summary of files stored in company folder
        if (Object.keys(uploadedFiles).length > 0) {
            console.log(`All uploaded files have been stored in company folder: ${companyFolder}`);
            Object.keys(uploadedFiles).forEach(fieldName => {
                const file = uploadedFiles[fieldName];
                console.log(`  - ${fieldName}: ${file.originalName} -> ${file.relativePath}`);
            });
        }

        // Create submission data object with all form fields
        const submission = {
            timestamp: new Date().toISOString(),
            submissionId: submissionId,
            companyFolder: companyFolderName, // Store the company folder name
            // Section 1: Vendor Name & Address
            companyName: formData.companyName?.trim() || '',
            telephone: formData.telephone?.trim() || '',
            poBox: formData.poBox?.trim() || '',
            country: formData.country || '',
            emirates: formData.emirates || '',
            headOfficeAddress: formData.headOfficeAddress?.trim() || '',
            servingEmirates: Array.isArray(formData['servingEmirates[]'])
                ? formData['servingEmirates[]']
                : (formData['servingEmirates[]'] ? [formData['servingEmirates[]']] : []),
            helpDeskEmail: formData.helpDeskEmail?.trim() || '',
            helpDeskContact: formData.helpDeskContact?.trim() || '',
            website: formData.website?.trim() || '',
            // Section 2: Company Details
            tradeLicenseNumber: formData.tradeLicenseNumber?.trim() || '',
            tradeLicenseIssueDate: formData.tradeLicenseIssueDate || '',
            tradeLicenseValidity: formData.tradeLicenseValidity || '',
            issuingAuthority: formData.issuingAuthority?.trim() || '',
            vatCertificate: formData.vatCertificate?.trim() || '',
            // Section 3: Owner / Partners
            ownerName: formData.ownerName?.trim() || '',
            partnerName: formData.partnerName?.trim() || '',
            // Section 4: Bank Accounts
            accountName: formData.accountName?.trim() || '',
            bankName: formData.bankName?.trim() || '',
            bankBranch: formData.bankBranch?.trim() || '',
            accountNumber: formData.accountNumber?.trim() || '',
            ibanNumber: formData.ibanNumber?.trim() || '',
            accountCurrency: formData.accountCurrency || '',
            // Section 5: References
            reference01: formData.reference01?.trim() || '',
            reference02: formData.reference02?.trim() || '',
            reference03: formData.reference03?.trim() || '',
            reference04: formData.reference04?.trim() || '',
            reference05: formData.reference05?.trim() || '',
            // Section 6: Key Contacts
            contact01Name: formData.contact01Name?.trim() || '',
            contact01Email: formData.contact01Email?.trim() || '',
            contact01Phone: formData.contact01Phone?.trim() || '',
            contact02Name: formData.contact02Name?.trim() || '',
            contact02Email: formData.contact02Email?.trim() || '',
            contact02Phone: formData.contact02Phone?.trim() || '',
            contact03Name: formData.contact03Name?.trim() || '',
            contact03Email: formData.contact03Email?.trim() || '',
            contact03Phone: formData.contact03Phone?.trim() || '',
            contact04Name: formData.contact04Name?.trim() || '',
            contact04Email: formData.contact04Email?.trim() || '',
            contact04Phone: formData.contact04Phone?.trim() || '',
            contact05Name: formData.contact05Name?.trim() || '',
            contact05Email: formData.contact05Email?.trim() || '',
            contact05Phone: formData.contact05Phone?.trim() || '',
            // Section 7: Documents (checkboxes)
            docTradeLicense: formData.docTradeLicense === 'on' || formData.docTradeLicense === 'true',
            docOwnerPassport: formData.docOwnerPassport === 'on' || formData.docOwnerPassport === 'true',
            docBankStatement: formData.docBankStatement === 'on' || formData.docBankStatement === 'true',
            docVatCertificate: formData.docVatCertificate === 'on' || formData.docVatCertificate === 'true',
            docCompanyProfile: formData.docCompanyProfile === 'on' || formData.docCompanyProfile === 'true',
            docFinancialStatement: formData.docFinancialStatement === 'on' || formData.docFinancialStatement === 'true',
            // Section 8: Insurances
            publicLiability: formData.publicLiability || '',
            employerLiability: formData.employerLiability || '',
            workmanCompensation: formData.workmanCompensation || '',
            contractorsRiskInsurance: formData.contractorsRiskInsurance || '',
            // Section 9: ESG & QHSE Requirements
            imsCertification: formData.imsCertification || '',
            ecovadisAssessment: formData.ecovadisAssessment || '',
            hazardIdentification: formData.hazardIdentification || '',
            qualityPolicy: formData.qualityPolicy || '',
            healthSafetyPolicy: formData.healthSafetyPolicy || '',
            environmentPolicy: formData.environmentPolicy || '',
            energyPolicy: formData.energyPolicy || '',
            laborStandards: formData.laborStandards || '',
            commitmentDisclosure: formData.commitmentDisclosure || '',
            supplierCode: formData.supplierCode || '',
            trainingPolicy: formData.trainingPolicy || '',
            riskAssessment: formData.riskAssessment || '',
            employeesRights: Array.isArray(formData['employeesRights[]'])
                ? formData['employeesRights[]']
                : (formData['employeesRights[]'] ? [formData['employeesRights[]']] : []),
            overtimeVoluntary: formData.overtimeVoluntary || '',
            weeklyWorkingHours: formData.weeklyWorkingHours || '',
            youngestEmploymentAge: formData.youngestEmploymentAge || '',
            // Section 10: Payment Terms
            creditPeriod: formData.creditPeriod || '',
            creditOtherText: formData.creditOtherText?.trim() || '',
            // Section 11: Nature of Business
            materialsSupply: Array.isArray(formData['materialsSupply[]'])
                ? formData['materialsSupply[]']
                : (formData['materialsSupply[]'] ? [formData['materialsSupply[]']] : []),
            amcServices: Array.isArray(formData['amcServices[]'])
                ? formData['amcServices[]']
                : (formData['amcServices[]'] ? [formData['amcServices[]']] : []),
            manpowerSupply: Array.isArray(formData['manpowerSupply[]'])
                ? formData['manpowerSupply[]']
                : (formData['manpowerSupply[]'] ? [formData['manpowerSupply[]']] : []),
            otherServices: formData.otherServices?.trim() || '',
            // Section 12: Disclaimer and Declaration
            authorizedPersonName: formData.authorizedPersonName?.trim() || '',
            authorizedPersonContact: formData.authorizedPersonContact?.trim() || '',
            authorizedPersonEmail: formData.authorizedPersonEmail?.trim() || '',
            // Uploaded files
            files: uploadedFiles
        };

        // Save submission to JSON file (you can replace this with database)
        // Use data directory if it exists (for Docker volumes), otherwise use current directory
        const dataDir = fs.existsSync(path.join(__dirname, 'data'))
            ? path.join(__dirname, 'data')
            : __dirname;
        const submissionsFile = path.join(dataDir, 'submissions.json');
        let submissions = [];

        // Ensure data directory exists
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }

        // Read existing submissions
        if (fs.existsSync(submissionsFile)) {
            try {
                const data = fs.readFileSync(submissionsFile, 'utf8');
                submissions = JSON.parse(data);
            } catch (err) {
                console.error('Error reading submissions file:', err);
            }
        }

        // Add new submission
        submissions.push(submission);

        // Write back to file
        fs.writeFileSync(submissionsFile, JSON.stringify(submissions, null, 2));

        // Generate PDF report and save it in the company folder
        // All uploaded files (including workman compensation, insurance files, etc.) 
        // have already been moved to the company folder above
        try {
            const pdfPath = await generatePDFReport(submission, companyFolder);
            console.log(`PDF report generated and saved in company folder: ${pdfPath}`);
        } catch (pdfError) {
            console.error('Error generating PDF report:', pdfError);
            // Continue even if PDF generation fails
        }

        console.log('Vendor registration form submission received:', {
            companyName: submission.companyName,
            email: submission.helpDeskEmail,
            submissionId: submission.submissionId,
            filesCount: Object.keys(uploadedFiles).length,
            companyFolder: companyFolderName
        });

        // Return success response
        res.json({
            success: true,
            message: 'Registration submitted successfully! You will receive a confirmation email shortly.',
            submissionId: submission.submissionId,
            timestamp: submission.timestamp
        });

    } catch (error) {
        console.error('Error processing submission:', error);
        res.status(500).json({
            success: false,
            error: 'An error occurred while processing your submission. Please try again.'
        });
    }
});

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Serve the form as the default page
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'vendor-registration-form.html'));
});

// Serve the login page
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'login.html'));
});

// Serve the dashboard page
app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'dashboard.html'));
});

// API login endpoint
app.post('/api/login', (req, res) => {
    const { username, password } = req.body;

    if (username === UPLOADS_USERNAME && password === UPLOADS_PASSWORD) {
        res.json({ success: true, message: 'Authentication successful' });
    } else {
        res.status(401).json({ success: false, error: 'Invalid email or password' });
    }
});

// API endpoint to get all submissions
app.get('/api/submissions', basicAuth, (req, res) => {
    try {
        const dataDir = fs.existsSync(path.join(__dirname, 'data'))
            ? path.join(__dirname, 'data')
            : __dirname;
        const submissionsFile = path.join(dataDir, 'submissions.json');

        if (fs.existsSync(submissionsFile)) {
            const data = fs.readFileSync(submissionsFile, 'utf8');
            const submissions = JSON.parse(data);
            res.json(submissions);
        } else {
            res.json([]);
        }
    } catch (error) {
        console.error('Error reading submissions:', error);
        res.status(500).json({ error: 'Failed to retrieve submissions' });
    }
});

// Serve uploads browser interface (unprotected from server-side, checked by JS)
app.get('/uploads', (req, res) => {
    res.sendFile(path.join(__dirname, 'uploads-browser.html'));
});

// Handle /uploads/ with trailing slash
app.get('/uploads/', (req, res) => {
    res.sendFile(path.join(__dirname, 'uploads-browser.html'));
});

// Serve files directly from /uploads/{path} (protected with Basic Auth)
// This allows direct access to files like /uploads/CompanyName_SUB-xxx/file.pdf
// Use a middleware to catch all paths under /uploads/ that aren't exact matches
app.use('/uploads', basicAuth, (req, res, next) => {
    // Skip if it's exactly /uploads or /uploads/ (handled by routes above)
    if (req.path === '' || req.path === '/') {
        return next();
    }

    try {
        // Extract the path after /uploads/ (remove leading slash)
        const requestedPath = req.path.startsWith('/') ? req.path.substring(1) : req.path;
        if (!requestedPath) {
            return res.sendFile(path.join(__dirname, 'uploads-browser.html'));
        }

        const fullPath = path.join(uploadsDir, requestedPath);

        // Security: Ensure path is within uploads directory
        const normalizedPath = path.normalize(fullPath);
        const normalizedUploadsDir = path.normalize(uploadsDir);

        if (!normalizedPath.startsWith(normalizedUploadsDir)) {
            return res.status(403).json({ error: 'Access denied' });
        }

        if (!fs.existsSync(normalizedPath)) {
            return res.status(404).json({ error: 'File or directory not found' });
        }

        const stats = fs.statSync(normalizedPath);

        // If it's a directory, serve the browser interface
        if (stats.isDirectory()) {
            return res.sendFile(path.join(__dirname, 'uploads-browser.html'));
        }

        // If it's a file, serve it
        if (stats.isFile()) {
            // Set appropriate headers
            const filename = path.basename(normalizedPath);
            const ext = path.extname(filename).toLowerCase();

            // Determine content type
            const contentTypes = {
                '.pdf': 'application/pdf',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.txt': 'text/plain',
                '.zip': 'application/zip',
                '.rar': 'application/x-rar-compressed'
            };

            const contentType = contentTypes[ext] || 'application/octet-stream';
            res.setHeader('Content-Type', contentType);
            res.setHeader('Content-Length', stats.size);

            // For PDFs and images, display inline; for others, download
            if (['.pdf', '.jpg', '.jpeg', '.png', '.gif'].includes(ext)) {
                res.setHeader('Content-Disposition', `inline; filename="${filename}"`);
            } else {
                res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
            }

            // Stream the file
            const fileStream = fs.createReadStream(normalizedPath);
            fileStream.pipe(res);

            fileStream.on('error', (error) => {
                console.error('Error streaming file:', error);
                if (!res.headersSent) {
                    res.status(500).json({ error: 'Error reading file' });
                }
            });
            // Don't call next() - we're handling the response
            return;
        }

        // If we get here and haven't sent a response, call next()
        if (!res.headersSent) {
            next();
        }
    } catch (error) {
        console.error('Error serving file:', error);
        if (!res.headersSent) {
            res.status(500).json({ error: 'Failed to serve file: ' + error.message });
        }
    }
});

// API endpoint to list directories and files (protected with Basic Auth)
app.get('/api/uploads/list', basicAuth, (req, res) => {
    try {
        const requestedPath = req.query.path || '';
        const fullPath = requestedPath
            ? path.join(uploadsDir, requestedPath)
            : uploadsDir;

        // Security: Ensure path is within uploads directory
        const normalizedPath = path.normalize(fullPath);
        const normalizedUploadsDir = path.normalize(uploadsDir);

        if (!normalizedPath.startsWith(normalizedUploadsDir)) {
            return res.status(403).json({ error: 'Access denied' });
        }

        if (!fs.existsSync(normalizedPath)) {
            return res.status(404).json({ error: 'Directory not found' });
        }

        const stats = fs.statSync(normalizedPath);
        if (!stats.isDirectory()) {
            return res.status(400).json({ error: 'Path is not a directory' });
        }

        const items = [];
        const entries = fs.readdirSync(normalizedPath, { withFileTypes: true });

        entries.forEach(entry => {
            const entryPath = path.join(normalizedPath, entry.name);
            const entryStats = fs.statSync(entryPath);

            if (entry.isDirectory()) {
                // Count files in directory
                let fileCount = 0;
                try {
                    const dirContents = fs.readdirSync(entryPath);
                    fileCount = dirContents.filter(item => {
                        const itemPath = path.join(entryPath, item);
                        return fs.statSync(itemPath).isFile();
                    }).length;
                } catch (err) {
                    // Ignore errors counting files
                }

                items.push({
                    name: entry.name,
                    type: 'folder',
                    modified: entryStats.mtime.toISOString(),
                    fileCount: fileCount
                });
            } else if (entry.isFile()) {
                items.push({
                    name: entry.name,
                    type: 'file',
                    size: entryStats.size,
                    modified: entryStats.mtime.toISOString()
                });
            }
        });

        // Sort: folders first, then files, both alphabetically
        items.sort((a, b) => {
            if (a.type !== b.type) {
                return a.type === 'folder' ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        });

        // Calculate statistics
        const statsData = {
            total: items.length,
            folders: items.filter(item => item.type === 'folder').length,
            files: items.filter(item => item.type === 'file').length
        };

        res.json({ items, stats: statsData });
    } catch (error) {
        console.error('Error listing directory:', error);
        res.status(500).json({ error: 'Failed to list directory: ' + error.message });
    }
});

// API endpoint to download files (protected with Basic Auth)
app.get('/api/uploads/download', basicAuth, (req, res) => {
    try {
        const requestedPath = req.query.path;
        if (!requestedPath) {
            return res.status(400).json({ error: 'Path parameter is required' });
        }

        const fullPath = path.join(uploadsDir, requestedPath);

        // Security: Ensure path is within uploads directory
        const normalizedPath = path.normalize(fullPath);
        const normalizedUploadsDir = path.normalize(uploadsDir);

        if (!normalizedPath.startsWith(normalizedUploadsDir)) {
            return res.status(403).json({ error: 'Access denied' });
        }

        if (!fs.existsSync(normalizedPath)) {
            return res.status(404).json({ error: 'File not found' });
        }

        const stats = fs.statSync(normalizedPath);
        if (!stats.isFile()) {
            return res.status(400).json({ error: 'Path is not a file' });
        }

        // Set appropriate headers
        const filename = path.basename(normalizedPath);
        const ext = path.extname(filename).toLowerCase();

        // Determine content type
        const contentTypes = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed'
        };

        const contentType = contentTypes[ext] || 'application/octet-stream';
        res.setHeader('Content-Type', contentType);
        res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
        res.setHeader('Content-Length', stats.size);

        // Stream the file
        const fileStream = fs.createReadStream(normalizedPath);
        fileStream.pipe(res);

        fileStream.on('error', (error) => {
            console.error('Error streaming file:', error);
            if (!res.headersSent) {
                res.status(500).json({ error: 'Error reading file' });
            }
        });
    } catch (error) {
        console.error('Error downloading file:', error);
        if (!res.headersSent) {
            res.status(500).json({ error: 'Failed to download file: ' + error.message });
        }
    }
});

// Serve static files (for serving the HTML form) - placed at the end after all routes
app.use(express.static(path.join(__dirname)));

// Start server
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
    console.log(`Health check: http://localhost:${PORT}/api/health`);
    console.log(`Form endpoint: http://localhost:${PORT}/api/submit`);
    console.log(`Vendors directory: ${uploadsDir}`);
});

