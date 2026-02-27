const fs = require('fs');
const filepath = 'frontend/src/HRDashboard.jsx';
let content = fs.readFileSync(filepath, 'utf8');

const startStr = `) : activeTab === 'staff' ? (`
const endStr = `) : activeTab === 'analytics' ? (`

const startIndex = content.indexOf(startStr);
const endIndex = content.indexOf(endStr);

if (startIndex === -1 || endIndex === -1) {
    console.log("Could not find boundaries");
    process.exit(1);
}

const jsxRaw = content.substring(startIndex + startStr.length, endIndex).trim();

const props = `
    mgmtSearch, setMgmtSearch, isMgmtLoading, mgmtUsers, roles, sites,
    handleEditUser, onResetPasswordClick, onDeleteUserClick, mgmtPage, mgmtStats, setMgmtPage
`;

const componentContent = `
import React from 'react';

export default function StaffManager({ 
${props} 
}) {
    return (
        ${jsxRaw}
    );
}
`;

fs.writeFileSync('frontend/src/components/StaffManager.jsx', componentContent.trim());

const replacement = `
                    ) : activeTab === 'staff' ? (
                        <StaffManager 
                            mgmtSearch={mgmtSearch}
                            setMgmtSearch={setMgmtSearch}
                            isMgmtLoading={isMgmtLoading}
                            mgmtUsers={mgmtUsers}
                            roles={roles}
                            sites={sites}
                            handleEditUser={handleEditUser}
                            onResetPasswordClick={onResetPasswordClick}
                            onDeleteUserClick={onDeleteUserClick}
                            mgmtPage={mgmtPage}
                            mgmtStats={mgmtStats}
                            setMgmtPage={setMgmtPage}
                        />
                    `;

const newContent = content.substring(0, startIndex) + replacement + content.substring(endIndex);

let finalContent = newContent;
if (!finalContent.includes('import StaffManager from')) {
    finalContent = finalContent.replace("import React,", "import React,\nimport StaffManager from './components/StaffManager';");
}

fs.writeFileSync(filepath, finalContent);
console.log("Extracted StaffManager!");
