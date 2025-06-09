import cloudinary
from consts import env_variables
# Configure Cloudinary with your credentials
cloudinary.config(
    cloud_name=env_variables["CLOUDINARY_CLOUD_NAME"],  
    api_key=env_variables["CLOUDINARY_API_KEY"],
    api_secret=env_variables["CLOUDINARY_API_SECRET"],
)

def extract_public_id_from_url(cloudinary_url: str) -> str:
    """Extract public_id from Cloudinary URL for deletion."""
    try:
        
        parts = cloudinary_url.split('/')
        # Find the index after 'upload'
        upload_index = parts.index('upload')
        
        # Skip version if present (starts with 'v' followed by numbers)
        start_index = upload_index + 1
        if start_index < len(parts) and parts[start_index].startswith('v') and parts[start_index][1:].isdigit():
            start_index += 1
        
        # Join remaining parts and remove file extension
        public_id_parts = parts[start_index:]
        public_id = '/'.join(public_id_parts)
        
        # Remove file extension
        if '.' in public_id:
            public_id = public_id.rsplit('.', 1)[0]
        
        return public_id
    except Exception as e:
        raise Exception(f"Failed to extract public_id from URL: {str(e)}")