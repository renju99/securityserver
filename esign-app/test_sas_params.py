import os
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def test_sas():
    client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container = client.get_container_client(CONTAINER_NAME)
    
    # List one blob
    blobs = list(container.list_blobs())
    if not blobs:
        print("No blobs found")
        return
    
    blob_path = blobs[0].name
    print(f"Testing blob: {blob_path}")
    
    sas_token = generate_blob_sas(
        account_name=client.account_name,
        container_name=CONTAINER_NAME,
        blob_name=blob_path,
        account_key=client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1),
        start_time=datetime.utcnow() - timedelta(minutes=15),
        content_disposition='inline',
        content_type='application/pdf'
    )
    
    url = f"https://{client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_path}?{sas_token}"
    print(f"Generated URL: {url}")
    
    # Check if rscd and rsct are in the URL
    if 'rscd=inline' in url:
        print("SUCCESS: rscd=inline found")
    else:
        print("FAILURE: rscd=inline NOT found")
        
    if 'rsct=application%2Fpdf' in url:
        print("SUCCESS: rsct=application/pdf found")
    else:
        print("FAILURE: rsct=application/pdf NOT found")

if __name__ == "__main__":
    test_sas()
