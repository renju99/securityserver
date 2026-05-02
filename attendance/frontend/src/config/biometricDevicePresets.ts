/**
 * Standard biometric / access-control terminal presets for HR configuration.
 * Field values are stored in `biometric_devices.config` (JSON); `type` matches vendor integration family.
 * Reachability: `biometric_devices.ip_address` accepts hostnames (DynDNS, No-IP, router DDNS) or numeric IPs.
 * UAE: defaults use Asia/Dubai; notes cover typical du / e& carrier NAT and VPN patterns (not legal advice).
 */

export type BiometricConfigFieldType = 'text' | 'number' | 'url' | 'password' | 'textarea' | 'select';

export interface BiometricConfigField {
    key: string;
    label: string;
    type: BiometricConfigFieldType;
    placeholder?: string;
    hint?: string;
    required?: boolean;
    options?: { value: string; label: string }[];
}

export interface BiometricDevicePreset {
    type: string;
    label: string;
    manufacturer: string;
    description: string;
    /** Shown under the form for UAE deployments */
    uaeNotes?: string;
    deviceKeyHint: string;
    /** Friendly label for the device key field in the UI */
    deviceKeyLabel?: string;
    defaultConfig: Record<string, string | number | boolean>;
    fields: BiometricConfigField[];
}

export const BIOMETRIC_DEVICE_PRESETS: BiometricDevicePreset[] = [
    {
        type: 'RA08',
        label: 'RA08 / AI-BOX (listener → HTTP ingest)',
        manufacturer: 'RA08',
        description:
            'Matches the bundled ra08-listener: it POSTs JSON to your API with Authorization: Bearer BIOMETRIC_INGEST_TOKEN. Set the same device key here as on the terminal.',
        uaeNotes:
            'For sites on 4G/5G routers (du, e&, Virgin), ensure the listener can reach api:3000 via your reverse proxy or VPN. Use a stable public hostname (your own domain or DynDNS) for the API — the RA08 side is usually outbound.',
        deviceKeyHint: 'Serial printed on device / RA08-…',
        deviceKeyLabel: 'Device key (matches listener payload)',
        defaultConfig: {
            ingest_path: '/api/biometrics/log',
            listener_service: 'ra08-listener (Docker)',
        },
        fields: [
            {
                key: 'listener_service',
                label: 'Edge service',
                type: 'text',
                placeholder: 'ra08-listener',
                hint: 'Container or host that receives pushes from the RA08 and forwards to the API.',
            },
            {
                key: 'ingest_path',
                label: 'Ingest URL path',
                type: 'text',
                placeholder: '/api/biometrics/log',
                hint: 'Must match BACKEND_URL path on the listener.',
            },
        ],
    },
    {
        type: 'ZKTeco_ADMS',
        label: 'ZKTeco — ADMS / iClock push (Horus, SpeedFace, etc.)',
        manufacturer: 'ZKTeco',
        description:
            'ZKTeco terminals in “push” or cloud mode call server URLs such as /iclock/getrequest and /iclock/cdata with serial SN. Horus E1-FP and similar models use the same family of settings when ADMS/push is enabled. This app stores only tab-text attendance (ATTLOG): photo / image push (e.g. ATTPHOTO) is acknowledged but not saved. These fields document what you enter on the device.',
        uaeNotes:
            'Push mode is outbound from the terminal to your portal — the device does not need a static public IP for ADMS. If you need inbound access (web UI on the device), use DynDNS on the router or site plus port-forward. On cellular SIMs (du / e&), inbound HTTP is often blocked — prefer push, HQ VPN, or a public HTTPS reverse proxy to /iclock/. Set device timezone to Asia/Dubai (UTC+4). This app serves iClock at https://YOUR-HOST/iclock/ (nginx proxies to the API).',
        deviceKeyHint: 'Must equal the device serial number (SN) — same value as query ?SN= on push requests.',
        deviceKeyLabel: 'Terminal serial number (SN)',
        defaultConfig: {
            public_iclock_base: 'https://attendance.example.com/iclock/',
            push_server_port: 8081,
            use_https: 'false',
            iclock_path_prefix: '/iclock/',
            terminal_timezone: 'Asia/Dubai',
            server_mode: 'ADMS',
        },
        fields: [
            {
                key: 'server_mode',
                label: 'Server mode on terminal',
                type: 'select',
                options: [
                    { value: 'ADMS', label: 'ADMS / Push' },
                    { value: 'CUSTOM', label: 'Custom server URL' },
                ],
            },
            {
                key: 'public_iclock_base',
                label: 'Public iClock base URL (this app)',
                type: 'url',
                placeholder: 'https://attendance.example.com/iclock/',
                hint: 'Enter the HTTPS base path terminals use (nginx /iclock/ → API). Device key in HR must match SN.',
            },
            {
                key: 'push_server_host',
                label: 'Push server host / URL (on device)',
                type: 'url',
                placeholder: 'https://attendance.example.com',
                hint: 'Use a stable hostname (your HR portal domain or DynDNS to that server). Path on device may be set separately depending on firmware.',
            },
            {
                key: 'push_server_port',
                label: 'Push server port',
                type: 'number',
                placeholder: '8081',
            },
            {
                key: 'use_https',
                label: 'HTTPS on terminal',
                type: 'select',
                options: [
                    { value: 'true', label: 'Yes' },
                    { value: 'false', label: 'No' },
                ],
            },
            {
                key: 'iclock_path_prefix',
                label: 'iClock path prefix',
                type: 'text',
                placeholder: '/iclock/',
                hint: 'Standard ZK push paths: /iclock/getrequest, /iclock/cdata, …',
            },
            {
                key: 'terminal_timezone',
                label: 'Terminal timezone',
                type: 'text',
                placeholder: 'Asia/Dubai',
            },
        ],
    },
    {
        type: 'ZKTeco_TCP',
        label: 'ZKTeco — direct TCP (pull / SDK)',
        manufacturer: 'ZKTeco',
        description:
            'Classic ZK terminal reachable by TCP (default port 4370) with proprietary protocol. The panel is often on a dynamic public IP — register a DynDNS hostname on the router or PC at the site and store that name here so pollers always resolve the current address. Requires a polling service or vendor SDK on your network — not handled by this web app.',
        uaeNotes:
            'Without a static IP, point your bridge at the device’s DynDNS hostname (and forwarded port), not a stale numeric IP. SIM sites may still need VPN or allow-lists.',
        deviceKeyHint: 'Serial / device ID used by your bridge software',
        deviceKeyLabel: 'Terminal ID in this app',
        defaultConfig: {
            tcp_port: 4370,
            connection_mode: 'client_poll',
        },
        fields: [
            {
                key: 'terminal_ip',
                label: 'Terminal hostname (DynDNS) or IP',
                type: 'text',
                placeholder: 'zk-gate.dyndns.org',
                hint: 'Use the FQDN your dynamic DNS client updates when the site has no static public IP.',
            },
            {
                key: 'tcp_port',
                label: 'TCP port',
                type: 'number',
                placeholder: '4370',
            },
            {
                key: 'comm_password',
                label: 'Comm / UDP password (if set on device)',
                type: 'password',
                placeholder: '0 or device password',
            },
            {
                key: 'connection_mode',
                label: 'Integration mode',
                type: 'select',
                options: [
                    { value: 'client_poll', label: 'Server polls device' },
                    { value: 'sdk', label: 'Vendor SDK on Windows/Linux' },
                ],
            },
        ],
    },
    {
        type: 'Suprema_BioStar2',
        label: 'Suprema — BioStar 2',
        manufacturer: 'Suprema',
        description:
            'BioStar 2 uses HTTPS local API (typical ports 443/51212/51213 depending on install). Devices often register to the BioStar server; integration is server-centric.',
        uaeNotes: 'Install TLS certificates before exposing API; for remote sites prefer device-initiated sessions or VPN.',
        deviceKeyHint: 'Door / reader ID or BioStar device ID you map to this terminal row',
        defaultConfig: {
            api_port: 51212,
            use_tls: 'true',
        },
        fields: [
            {
                key: 'bioserver_host',
                label: 'BioStar server host',
                type: 'text',
                placeholder: 'biostar.internal',
            },
            {
                key: 'api_port',
                label: 'API / server port',
                type: 'number',
                placeholder: '51212',
            },
            {
                key: 'use_tls',
                label: 'Use TLS',
                type: 'select',
                options: [
                    { value: 'true', label: 'Yes' },
                    { value: 'false', label: 'No' },
                ],
            },
            {
                key: 'api_username',
                label: 'API user (if used)',
                type: 'text',
            },
            {
                key: 'api_password',
                label: 'API password',
                type: 'password',
            },
        ],
    },
    {
        type: 'Anviz_CrossChex',
        label: 'Anviz — CrossChex / device bridge',
        manufacturer: 'Anviz',
        description:
            'Anviz ecosystems often use CrossChex on a PC to collect devices; integration is typically via that bridge (TCP/UDP or export).',
        deviceKeyHint: 'CrossChex terminal ID or MAC-based id',
        defaultConfig: { bridge_port: 8910 },
        fields: [
            {
                key: 'bridge_host',
                label: 'Bridge / CrossChex host',
                type: 'text',
                placeholder: 'crosschex.dyndns.org or 192.168.1.50',
            },
            {
                key: 'bridge_port',
                label: 'Bridge port',
                type: 'number',
                placeholder: '8910',
            },
        ],
    },
    {
        type: 'Hikvision_ISAPI',
        label: 'Hikvision — terminal (ISAPI)',
        manufacturer: 'Hikvision',
        description:
            'Access control / attendance terminals often expose ISAPI over HTTPS. Store the endpoint you use for events or attendance export.',
        deviceKeyHint: 'Device serial or ISAPI device ID',
        defaultConfig: { isapi_port: 443 },
        fields: [
            {
                key: 'device_ip',
                label: 'Device hostname (DynDNS) or IP',
                type: 'text',
                placeholder: 'reader-site.dyndns.org',
                hint: 'Dynamic public IP at the site is fine — use the hostname your DDNS client maintains.',
            },
            {
                key: 'isapi_port',
                label: 'HTTPS port',
                type: 'number',
                placeholder: '443',
            },
            {
                key: 'username',
                label: 'ISAPI user',
                type: 'text',
            },
            {
                key: 'password',
                label: 'ISAPI password',
                type: 'password',
            },
        ],
    },
    {
        type: 'Matrix_COSEC',
        label: 'Matrix — COSEC',
        manufacturer: 'Matrix',
        description:
            'COSEC deployments commonly use a central server API. Record the panel URL and credentials your middleware uses.',
        uaeNotes: 'Matrix is widely used in UAE enterprises; align door/reader IDs with HR staff codes in this app.',
        deviceKeyHint: 'COSEC terminal / panel id',
        defaultConfig: {},
        fields: [
            {
                key: 'cosec_api_base',
                label: 'COSEC API base URL',
                type: 'url',
                placeholder: 'https://cosec.example.com/api',
            },
            {
                key: 'api_token',
                label: 'API token / key',
                type: 'password',
            },
        ],
    },
    {
        type: 'ESSL_eTime',
        label: 'eSSL / Identix — eTimeOffice / similar',
        manufacturer: 'eSSL',
        description:
            'Many eSSL deployments push or poll via their middleware. Store identifiers your integrator maps to this system.',
        deviceKeyHint: 'Terminal id in eTime / middleware',
        defaultConfig: {},
        fields: [
            {
                key: 'middleware_host',
                label: 'Middleware host',
                type: 'text',
            },
            {
                key: 'terminal_uid',
                label: 'Terminal UID',
                type: 'text',
            },
        ],
    },
    {
        type: 'Morpho_Idemia',
        label: 'Idemia / Morpho — Sigma / terminal SDK',
        manufacturer: 'Idemia',
        description:
            'Morpho/Idemia terminals often integrate via OEM SDK or a gateway service. Store network parameters for your bridge.',
        deviceKeyHint: 'Terminal serial',
        defaultConfig: { sdk_port: 7878 },
        fields: [
            {
                key: 'terminal_ip',
                label: 'Terminal hostname (DynDNS) or IP',
                type: 'text',
                placeholder: 'sigma-door.dyndns.org',
            },
            {
                key: 'sdk_port',
                label: 'SDK / gateway port',
                type: 'number',
                placeholder: '7878',
            },
        ],
    },
    {
        type: 'GENERIC_HTTP',
        label: 'Generic — custom HTTP → ingest',
        manufacturer: 'Other',
        description:
            'Any device or script that can POST the same JSON shape as this app’s /api/biometrics/log (with BIOMETRIC_INGEST_TOKEN). Use for Horus, OEM bridges, or MQTT→HTTP workers.',
        deviceKeyHint: 'Must match JSON deviceKey in each POST',
        deviceKeyLabel: 'Device key in JSON payload',
        defaultConfig: {
            staff_id_json_path: 'staffId',
            timestamp_json_path: 'timestamp',
        },
        fields: [
            {
                key: 'bridge_description',
                label: 'Bridge / script name',
                type: 'text',
                placeholder: 'Node-RED flow, n8n, custom worker',
            },
            {
                key: 'staff_id_json_path',
                label: 'Staff id field name in payload',
                type: 'text',
                placeholder: 'staffId',
            },
            {
                key: 'timestamp_json_path',
                label: 'Timestamp field name',
                type: 'text',
                placeholder: 'timestamp',
            },
            {
                key: 'extra_notes',
                label: 'Notes',
                type: 'textarea',
                placeholder: 'Document URL, auth header name, etc.',
            },
        ],
    },
];

export function getBiometricPreset(type: string | undefined | null): BiometricDevicePreset {
    const t = type || 'RA08';
    return BIOMETRIC_DEVICE_PRESETS.find((p) => p.type === t) || BIOMETRIC_DEVICE_PRESETS[BIOMETRIC_DEVICE_PRESETS.length - 1];
}

export function mergePresetDefaults(
    type: string,
    existing: Record<string, string | number | boolean | null | undefined | ''>
): Record<string, string | number | boolean | ''> {
    const preset = getBiometricPreset(type);
    const out: Record<string, string | number | boolean | ''> = { ...preset.defaultConfig };
    for (const [k, v] of Object.entries(existing || {})) {
        if (v === undefined || v === null) continue;
        if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') out[k] = v;
    }
    return out;
}
