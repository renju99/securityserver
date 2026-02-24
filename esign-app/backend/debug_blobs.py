import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def list_blobs():
    if not CONNECTION_STRING:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not found")
        return

    try:
        service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = service_client.get_container_client(CONTAINER_NAME)
        
        print(f"Listing blobs in container: {CONTAINER_NAME}")
        blobs = container_client.list_blobs()
        for blob in blobs:
            print(f"- {blob.name} ({blob.size} bytes)")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_blobs()
