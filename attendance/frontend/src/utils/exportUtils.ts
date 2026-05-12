// Export utilities for data export functionality
import ExcelJS from 'exceljs';

function padField(value: unknown, width: number) {
    const s = String(value ?? '').replace(/\r|\n/g, ' ');
    if (s.length >= width) return s.slice(0, width);
    return s.padEnd(width, ' ');
}

/** Fixed-width payroll-style lines (matches server payroll_v1 profile). */
export const exportToFixedWidthPayroll = (data: Record<string, string>[], filename = 'payroll_export.txt') => {
    if (!data?.length) {
        console.warn('No data to export');
        return;
    }
    const spec: [string, number][] = [
        ['Staff ID', 12],
        ['Name', 28],
        ['Department', 18],
        ['Site', 16],
        ['Date', 10],
        ['Check In', 19],
        ['Check Out', 19],
        ['Day note', 24],
    ];
    const header = spec.map(([label, w]) => padField(label, w)).join('') + '\r\n';
    const body = data
        .map((r) =>
            [
                padField(r['Staff ID'], 12),
                padField(r.Name, 28),
                padField(r.Department, 18),
                padField(r.Site, 16),
                padField(r.Date, 10),
                padField(r['Check In'], 19),
                padField(r['Check Out'], 19),
                padField(r['Day note'], 24),
            ].join('')
        )
        .join('\r\n');
    const blob = new Blob([header + body + '\r\n'], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = filename;
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
};

export async function exportToXlsx(
    data: Record<string, unknown>[],
    filename = 'export.xlsx',
    sheetName = 'Attendance'
): Promise<void> {
    if (!data?.length) {
        console.warn('No data to export');
        return;
    }
    const workbook = new ExcelJS.Workbook();
    const ws = workbook.addWorksheet(sheetName.slice(0, 31));
    const headers = Object.keys(data[0] as object);
    ws.addRow(headers);
    for (const row of data) {
        ws.addRow(headers.map((h) => row[h]));
    }
    const buf = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buf], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = filename;
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

export const exportToCSV = (data: any[], filename = 'export.csv') => {
    if (!data || data.length === 0) {
        console.warn('No data to export');
        return;
    }

    // Get headers from first object
    const headers = Object.keys(data[0]);

    // Create CSV content
    const csvContent = [
        // Header row
        headers.join(','),
        // Data rows
        ...data.map(row =>
            headers.map(header => {
                const value = row[header];
                // Handle values with commas, quotes, or newlines
                if (value === null || value === undefined) return '';
                const stringValue = String(value);
                if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
                    return `"${stringValue.replace(/"/g, '""')}"`;
                }
                return stringValue;
            }).join(',')
        )
    ].join('\n');

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

export const exportToJSON = (data: any, filename = 'export.json') => {
    if (!data) {
        console.warn('No data to export');
        return;
    }

    const jsonContent = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

export const formatDataForExport = (users: any[]) => {
    return users.map(user => ({
        'Staff ID': user.staff_id,
        'Email': user.email || 'N/A',
        'Role': user.role_name,
        'Site': user.site_name || 'Global',
        'Department': user.department_name,
        'Created': user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'
    }));
};

export const formatSitesForExport = (sites: any[]) => {
    return sites.map(site => ({
        'Site Name': site.name,
        'Location': site.location || 'N/A',
        'Created': site.created_at ? new Date(site.created_at).toLocaleDateString() : 'N/A'
    }));
};
