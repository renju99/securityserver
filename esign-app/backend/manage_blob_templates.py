import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

def manage_templates():
    try:
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # 1. Upload new template
        new_template = "Capex_Template_New.docx"
        blob_name = f"templates/{new_template}"
        blob_client = container_client.get_blob_client(blob_name)
        
        with open(new_template, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            print(f"Uploaded {new_template} to {blob_name}")
            
        # 1b. Upload as legacy name (to fix existing requests)
        legacy_name = "templates/Capex Template.docx"
        blob_client_legacy = container_client.get_blob_client(legacy_name)
        with open(new_template, "rb") as data:
            blob_client_legacy.upload_blob(data, overwrite=True)
            print(f"Uploaded {new_template} to {legacy_name} (Legacy Support)")
            
        # 2. Delete old templates
        old_templates = [
            "templates/Capex_Template_Ready.docx",
            "templates/Capex_Template_Updated.docx"
        ]
        
        for old in old_templates:
            try:
                blob_client_old = container_client.get_blob_client(old)
                if blob_client_old.exists():
                    blob_client_old.delete_blob()
                    print(f"Deleted old template: {old}")
                else:
                    print(f"Old template {old} does not exist in storage.")
            except Exception as e:
                print(f"Error deleting {old}: {e}")
                
    except Exception as e:
        print(f"Error in manage_templates: {e}")

if __name__ == "__main__":
    manage_templates()
