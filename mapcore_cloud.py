from google.cloud import storage

import config

import os


'''credentials_dict = {
    'type': 'service_account',
    'client_id': os.environ['BACKUP_CLIENT_ID'],
    'client_email': os.environ['BACKUP_CLIENT_EMAIL'],
    'private_key_id': os.environ['BACKUP_PRIVATE_KEY_ID'],
    'private_key': os.environ['BACKUP_PRIVATE_KEY'],
}
credentials = ServiceAccountCredentials.from_json_keyfile_dict(
    credentials_dict
)'''

def upload_blob(bucket_name, source_file_name, destination_blob_name, map_name):
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client.from_service_account_json(r"service_account.json", project=config.CLOUD_PROJECT)
    bucket = storage_client.bucket(bucket_name)
    destination_blob_full_name = f"mapcore/{map_name}/{destination_blob_name}"
    print(destination_blob_full_name)
    blob = bucket.blob(destination_blob_full_name)

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to upload is aborted if the object's
    # generation number does not match your precondition. For a destination
    # object that does not yet exist, set the if_generation_match precondition to 0.
    # If the destination object already exists in your bucket, set instead a
    # generation-match precondition using its generation number.
    #generation_match_precondition = 0
    try:
        blob.upload_from_filename(source_file_name)

        print(
            f"File {source_file_name} uploaded to {destination_blob_name}."
        )
        return f"File {source_file_name} uploaded to {destination_blob_name}."
    except Exception as e:
        return e

def blob_exists(bucket_name, filename):
    storage_client = storage.Client.from_service_account_json(r"service_account.json", project=config.CLOUD_PROJECT)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(filename)
    return blob.exists()

#upload_blob(config.CLOUD_BUCKET, f'{config.STORAGE_LOCATION}login.html', "login.html", "CONTEST Bank")

print(blob_exists(config.CLOUD_BUCKET, "main_test.py"))
#https://storage.googleapis.com/mapcore-demos/mapcore/CONTEST%20Bank/1-3cf57572-4dda-41a6-9be5-470d0fdcf069.dem.gz
