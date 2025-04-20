import cloudinary
import cloudinary.uploader
import cloudinary.api
from consts import env_variables
# Configure Cloudinary with your credentials
cloudinary.config(
    cloud_name=env_variables.CLOUDINARY_CLOUD_NAME,  
    api_key=env_variables.CLOUDINARY_API_KEY,
    api_secret=env_variables.CLOUDINARY_API_SECRET,
)