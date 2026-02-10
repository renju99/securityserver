# Migration to Existing Ubuntu VM (with Odoo)

Since you already have an Azure VM running Docker and Odoo, we can integrate this service seamlessly using Docker Compose.

## How to Move the Server

### 1. Package the Code
Run this command on your current environment to create a backup of the source code:
```bash
./package_for_migration.sh
```
This will create a `procurement_migration_TIMESTAMP.tar.gz` file in your current folder.

### 2. Transfer to your Azure VM
Use `scp` to copy the package to your `azure-vm`:
```bash
scp procurement_migration_*.tar.gz azureuser@<YOUR_VM_IP>:/home/azureuser/
```

### 3. Deploy on Azure VM
On the Azure VM, extract the package and set up the persistent storage:
```bash
# 1. Extract the package
mkdir -p procurement-app
tar -xzvf procurement_migration_full_*.tar.gz -C procurement-app

# 2. Setup the attachments directory (Matches current server)
sudo mkdir -p /var/www
sudo mv procurement-app/attachments /var/www/
sudo chown -R 1000:1000 /var/www/attachments

# 3. Start the container
cd procurement-app
docker compose up -d --build
```

## Integration with Odoo/Existing Setup

### Networking
If you have an Odoo reverse proxy (like Nginx), you can route traffic to this container. 
The app runs on port `3001` (host) by default in the current `docker-compose.yml`.

### Persistent Storage
The application uses two main directories for data:
- `/var/www/attachments`: This is where uploaded files are stored (mapped to `/app/uploads`).
- `./data`: This is where submission metadata is stored (mapped to `/app/data`).

Ensure `/var/www/attachments` exists and is writable on the Azure VM:
```bash
sudo mkdir -p /var/www/attachments
sudo chown -R 1000:1000 /var/www/attachments # Match node user in container
```

## Reverse Proxy (Nginx Example)
Add this to your existing Nginx config on the VM to expose the portal:
```nginx
server {
    listen 80;
    server_name procurement.yourdomain.com;

    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
