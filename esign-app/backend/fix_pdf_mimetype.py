import os
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def fix_content_types():
    if not CONNECTION_STRING:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not found")
        return

    try:
        service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = service_client.get_container_client(CONTAINER_NAME)
        
        print(f"Checking PDFs in container: {CONTAINER_NAME}")
        blobs = container_client.list_blobs()
        for blob in blobs:
            if blob.name.lower().endswith(".pdf"):
                blob_client = container_client.get_blob_client(blob.name)
                # Check current settings
                props = blob_client.get_blob_properties()
                if props.content_settings.content_type != "application/pdf":
                    print(f"Updating {blob.name} content-type to application/pdf")
                    blob_client.set_http_headers(
                        content_settings=ContentSettings(content_type="application/pdf")
                    )
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_content_types()
