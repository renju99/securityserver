const fs = require('fs');
const path = require('path');

const walkSync = (dir, filelist = []) => {
    fs.readdirSync(dir).forEach(file => {
        const filePath = path.join(dir, file);
        if (!fs.statSync(filePath).isDirectory()) {
            if (filePath.match(/\.(css|tsx|ts|jsx|js)$/) && !filePath.includes('node_modules')) {
                filelist.push(filePath);
            }
        } else {
            filelist = walkSync(filePath, filelist);
        }
    });
    return filelist;
};

const files = walkSync('src');
let changed = 0;

for (const file of files) {
    let content = fs.readFileSync(file, 'utf8');
    const orig = content;

    content = content.replace(/99,\s*71,\s*254/g, '92, 66, 188');
    content = content.replace(/#6347FE/gi, '#5c42bc');
    content = content.replace(/#4B17EE/gi, '#4a3596');
    content = content.replace(/#8567FF/gi, '#7d68c9');
    content = content.replace(/#EEF0FF/gi, '#edebfa');

    if (orig !== content) {
        fs.writeFileSync(file, content);
        console.log(`Updated colors in ${file}`);
        changed++;
    }
}
console.log(`Replaced colors in ${changed} files.`);
