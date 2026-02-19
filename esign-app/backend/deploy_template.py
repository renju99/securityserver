import os
from azure.storage.blob import BlobServiceClient
from create_new_template import create_improved_capex

def deploy():
    # Generate the template locally
    filename = "Capex Template.docx"
    print(f"Generating {filename}...")
    create_improved_capex(filename)

    # Upload to Azure
    connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")
    
    if not connect_str:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not found.")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        # Verify container exists
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
             container_client.create_container()
             
        # Upload
        blob_path = f"templates/{filename}"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
        
        with open(filename, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            
        print(f"Successfully uploaded {filename} to {container_name}/{blob_path}")

    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    deploy()
