import os
from datetime import datetime, timedelta
from urllib.parse import quote
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

class BlobService:
    def __init__(self):
        if not CONNECTION_STRING:
            print("Azure Storage Connection String not found in environment")
            self.blob_service_client = None
            self.container_client = None
            return

        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
            self.container_client = self.blob_service_client.get_container_client(CONTAINER_NAME)
            if not self.container_client.exists():
                self.container_client.create_container()
        except Exception as e:
            print(f"Azure Storage Initialization Error: {e}")
            self.blob_service_client = None
            self.container_client = None

    def upload_blob(self, file_content: bytes, blob_path: str, overwrite: bool = True, content_type: str = None):
        if not self.container_client:
            raise Exception("Blob service not initialized")
        
        # Auto-detect PDF if not specified
        if not content_type and blob_path.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        
        blob_client = self.container_client.get_blob_client(blob_path)
        content_settings = ContentSettings(content_type=content_type) if content_type else None
        blob_client.upload_blob(file_content, overwrite=overwrite, content_settings=content_settings)
        return blob_client

    def get_sas_url(self, blob_path: str, expiry_hours: int = 1, read: bool = True):
        if not self.container_client:
            return None
        
        blob_client = self.container_client.get_blob_client(blob_path)
        if not blob_client.exists():
            return None

        # Prepare SAS parameters
        sas_args = {
            "account_name": self.blob_service_client.account_name,
            "container_name": CONTAINER_NAME,
            "blob_name": blob_path,
            "account_key": self.blob_service_client.credential.account_key,
            "permission": BlobSasPermissions(read=read),
            "expiry": datetime.utcnow() + timedelta(hours=expiry_hours),
            "start_time": datetime.utcnow() - timedelta(minutes=15),
            "content_disposition": f'inline; filename="{os.path.basename(blob_path)}"'
        }
        
        # If it's a PDF or common image, force the content type in the response
        lower_path = blob_path.lower()
        if lower_path.endswith('.pdf'):
            sas_args["content_type"] = 'application/pdf'
        elif lower_path.endswith('.jpg') or lower_path.endswith('.jpeg'):
            sas_args["content_type"] = 'image/jpeg'
        elif lower_path.endswith('.png'):
            sas_args["content_type"] = 'image/png'
        elif lower_path.endswith('.gif'):
            sas_args["content_type"] = 'image/gif'
        elif lower_path.endswith('.webp'):
            sas_args["content_type"] = 'image/webp'

        sas_token = generate_blob_sas(**sas_args)
        return f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{quote(blob_path, safe='/')}?{sas_token}"

    def delete_blob(self, blob_path: str):
        if not self.container_client:
            return False
        blob_client = self.container_client.get_blob_client(blob_path)
        if blob_client.exists():
            blob_client.delete_blob()
            return True
        return False

    def list_blobs(self, name_starts_with: str = None):
        if not self.container_client:
            return []
        return self.container_client.list_blobs(name_starts_with=name_starts_with)

    def download_blob(self, blob_path: str):
        if not self.container_client:
            raise Exception("Blob service not initialized")
        blob_client = self.container_client.get_blob_client(blob_path)
        return blob_client.download_blob().readall()

blob_service = BlobService()
