import fs from 'fs';

let content = fs.readFileSync('src/HRDashboard.tsx', 'utf-8');

// Replace these state typings
const targets = [
    'currentUser',
    'currentBiometricDevice',
    'confirmDialog',
    'currentSite',
    'loginData'
];

for (const target of targets) {
    content = content.replace(new RegExp(`const \\[(.*${target}.*)\\] = useState\\(`, 'g'), `const [$1] = useState<any>(`);
}

fs.writeFileSync('src/HRDashboard.tsx', content);
