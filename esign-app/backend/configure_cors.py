import os
from azure.storage.blob import BlobServiceClient, CorsRule
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

def configure_cors():
    if not CONNECTION_STRING:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not found in environment.")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)

        print("Setting CORS rules...")
        cors_rule = CorsRule(
            allowed_origins=["*"], 
            allowed_methods=["GET", "HEAD", "OPTIONS", "POST", "PUT"],
            allowed_headers=["*"],
            exposed_headers=["*"],
            max_age_in_seconds=3600
        )

        # Set properties
        blob_service_client.set_service_properties(cors=[cors_rule])
        print("CORS rules updated successfully.")
        
        # Verify
        props = blob_service_client.get_service_properties()
        print("Current CORS rules:", props['cors'])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    configure_cors()
