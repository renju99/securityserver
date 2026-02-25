import os
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def fix_metadata():
    if not CONNECTION_STRING:
        print("No connection string")
        return
        
    client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container = client.get_container_client(CONTAINER_NAME)
    
    print(f"Scanning container: {CONTAINER_NAME}")
    blobs = container.list_blobs()
    count = 0
    for blob in blobs:
        if blob.name.lower().endswith('.pdf'):
            blob_client = container.get_blob_client(blob)
            # Update content settings
            blob_client.set_http_headers(
                content_settings=ContentSettings(content_type='application/pdf', content_disposition='inline')
            )
            print(f"Fixed: {blob.name}")
            count += 1
    
    print(f"Total PDFs updated: {count}")

if __name__ == "__main__":
    fix_metadata()
