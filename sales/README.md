# Odoo 18 Sales Instance (Isolated)

This stack runs a separate Odoo 18 instance for Sales and does not modify anything in `../security`.

## Isolation details

- Separate project folder: `sales/`
- Separate containers: `odoo_sales`, `odoo_sales_db`
- Separate Docker volumes: `sales-odoo-db-data`, `sales-odoo-web-data`
- Separate database name: `sales`
- Separate host port: `8071` (mapped to Odoo container `8069`)

## Start

```bash
cd /home/azureuser/sales
docker compose up -d
```

Open: <http://localhost:8071>

## Stop

```bash
cd /home/azureuser/sales
docker compose down
```

## First-time DB initialization

On first launch, create the `sales` database in Odoo web UI if it is not auto-created.
Use the master password from `config/odoo.conf` (`admin_passwd`).
