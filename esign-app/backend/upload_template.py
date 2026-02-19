import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def upload_template(file_path, blob_name):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            print(f"Uploaded {file_path} to {blob_name}")
    except Exception as e:
        print(f"Error uploading: {e}")

if __name__ == "__main__":
    upload_template("Capex_Template_Ready.docx", "templates/Capex_Template_Ready.docx")
