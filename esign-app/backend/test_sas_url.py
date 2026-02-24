import os
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def test_url():
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    
    filename = "Capex Template.pdf"
    blob_path = f"templates/{filename}"
    blob_client = container_client.get_blob_client(blob_path)
    
    if not blob_client.exists():
        print(f"Blob {blob_path} not found!")
        return

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=CONTAINER_NAME,
        blob_name=blob_client.blob_name,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=12),
        start_time=datetime.utcnow() - timedelta(minutes=15)
    )
    
    url = f"https://{blob_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{quote(blob_client.blob_name, safe='/')}?{sas_token}"
    print(f"Generated URL: {url}")
    
    # Try to curl it
    import subprocess
    result = subprocess.run(["curl", "-I", url], capture_output=True, text=True)
    print("\nCurl headers:")
    print(result.stdout)
    if "200" in result.stdout:
        print("URL is accessible!")
    else:
        print("URL access failed!")
        print(result.stderr)

if __name__ == "__main__":
    test_url()
