/**
 * Build export file buffers (CSV, XLSX, fixed-width) from flattened attendance rows.
 */

const ExcelJS = require('exceljs');

function buildCsvString(rows) {
    if (!rows.length) return '';
    const headers = Object.keys(rows[0]);
    const lines = [
        headers.join(','),
        ...rows.map((row) =>
            headers
                .map((h) => {
                    const v = row[h];
                    if (v === null || v === undefined) return '';
                    const s = String(v);
                    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
                        return `"${s.replace(/"/g, '""')}"`;
                    }
                    return s;
                })
                .join(',')
        )
    ];
    return lines.join('\n');
}

/** @param {Record<string, string>[]} rows */
async function buildXlsxBuffer(rows) {
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Attendance', { views: [{ state: 'frozen', ySplit: 1 }] });
    if (!rows.length) {
        sheet.addRow(['No data']);
    } else {
        const headers = Object.keys(rows[0]);
        sheet.addRow(headers);
        sheet.getRow(1).font = { bold: true };
        rows.forEach((r) => {
            sheet.addRow(headers.map((h) => r[h] ?? ''));
        });
        headers.forEach((h, idx) => {
            const col = sheet.getColumn(idx + 1);
            col.width = Math.min(48, Math.max(12, String(h).length + 4));
        });
    }
    return Buffer.from(await workbook.xlsx.writeBuffer());
}

function padField(value, width) {
    const s = String(value ?? '').replace(/\r|\n/g, ' ');
    if (s.length >= width) return s.slice(0, width);
    return s.padEnd(width, ' ');
}

/**
 * Simple fixed-width payroll-style layout (ASCII, one row per punch).
 * @param {Record<string, string>[]} rows
 */
function buildFixedWidthPayrollV1(rows) {
    const spec = [
        ['Staff ID', 12],
        ['Name', 28],
        ['Department', 18],
        ['Site', 16],
        ['Date', 10],
        ['CheckIn', 19],
        ['CheckOut', 19],
        ['Note', 24]
    ];
    const headerLine = spec.map(([label, w]) => padField(label, w)).join('') + '\r\n';
    const body = rows
        .map((r) =>
            [
                padField(r['Staff ID'], 12),
                padField(r.Name, 28),
                padField(r.Department, 18),
                padField(r.Site, 16),
                padField(r.Date, 10),
                padField(r['Check In'], 19),
                padField(r['Check Out'], 19),
                padField(r['Day note'], 24)
            ].join('')
        )
        .join('\r\n');
    return Buffer.from(headerLine + body + (rows.length ? '\r\n' : ''), 'utf8');
}

async function buildExportBuffer(format, rows) {
    if (format === 'csv') {
        return { filenameExt: 'csv', contentType: 'text/csv; charset=utf-8', body: Buffer.from('\uFEFF' + buildCsvString(rows), 'utf8') };
    }
    if (format === 'xlsx') {
        const body = await buildXlsxBuffer(rows);
        return { filenameExt: 'xlsx', contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', body };
    }
    if (format === 'fixed_width') {
        return {
            filenameExt: 'txt',
            contentType: 'text/plain; charset=utf-8',
            body: buildFixedWidthPayrollV1(rows)
        };
    }
    return { filenameExt: 'csv', contentType: 'text/csv; charset=utf-8', body: Buffer.from('\uFEFF' + buildCsvString(rows), 'utf8') };
}

module.exports = {
    buildCsvString,
    buildXlsxBuffer,
    buildFixedWidthPayrollV1,
    buildExportBuffer,
};
