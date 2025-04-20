from fastapi import APIRouter, File, UploadFile, HTTPException, status , Depends
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from middleWares import verify_device

router = APIRouter(prefix="/photos", tags=["Photos"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_photo(file: UploadFile = File(...) , current_user=Depends(verify_device )):
    """Upload a photo to Cloudinary."""
    try:
        # Read the file content
        file_content = await file.read()

        # Upload to Cloudinary
        result = upload(file_content, folder="notifications")

        # Return the Cloudinary URL
        return {"message": "Photo uploaded successfully", "url": result["secure_url"]}
    except CloudinaryError as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")