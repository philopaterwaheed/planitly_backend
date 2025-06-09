from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile
from middleWares import verify_device
from cloudinary.uploader import upload, destroy
from cloudinary.exceptions import Error as CloudinaryError
import re
import datetime
from cloud import extract_public_id_from_url

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_profile(user_device: tuple = Depends(verify_device)):
    """Retrieve the current user's profile."""
    user = user_device[0]
    try:
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "phone_number": user.phone_number,
            "birthday": user.birthday.isoformat() if user.birthday else None,
            "email_verified": user.email_verified,
            "admin": user.admin,
            "profile_image": user.profile_image,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/", status_code=status.HTTP_200_OK)
async def update_profile(
    profile_data: dict, user_device: tuple = Depends(verify_device)
):
    """Update the current user's profile."""
    user = user_device[0]
    try:
        firstname = profile_data.get("firstname")
        lastname = profile_data.get("lastname")
        phone_number = profile_data.get("phone_number")
        birthday = profile_data.get("birthday")

        if firstname:
            if not firstname.isalpha():
                raise HTTPException(
                    status_code=400,
                    detail="First name must contain only alphabetic characters.",
                )
            user.firstname = firstname

        if lastname:
            if not lastname.isalpha():
                raise HTTPException(
                    status_code=400,
                    detail="Last name must contain only alphabetic characters.",
                )
            user.lastname = lastname

        if phone_number:
            if not re.match(r"^\+?[1-9]\d{1,14}$", phone_number):
                raise HTTPException(
                    status_code=400, detail="Invalid phone number format."
                )
            user.phone_number = phone_number

        if birthday:
            try:
                if not isinstance(birthday, str):
                    birthday = datetime.strptime(birthday, "%Y-%m-%d %H:%M:%S")

                birthday_date = datetime.datetime.fromisoformat(birthday)
                if birthday_date > datetime.datetime.now():
                    raise HTTPException(
                        status_code=400, detail="Birthday cannot be in the future."
                    )
                if (datetime.datetime.now() - birthday_date).days < 13 * 365:
                    raise HTTPException(
                        status_code=400, detail="Users must be at least 13 years old."
                    )
                user.birthday = birthday_date
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid birthday format. Use ISO format (YYYY-MM-DD)."
                )
        else: 
                raise HTTPException(
                    status_code=400, detail="Messing birthday"
                )

        user.save()
        return {"message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-image", status_code=status.HTTP_200_OK)
async def upload_profile_image(
    file: UploadFile = File(...),
    user_device: tuple = Depends(verify_device)
):
    """Upload or update user's profile image."""
    user = user_device[0]
    
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Only JPG, JPEG, and PNG are allowed"
            )
        
        # Validate file size (5MB limit)
        file_content = await file.read()
        if len(file_content) > 5 * 1024 * 1024:  # 5 MB
            raise HTTPException(
                status_code=400, 
                detail="File size exceeds 5 MB limit"
            )

        # Delete old profile image if it exists
        if user.profile_image:
            try:
                # Extract public_id from Cloudinary URL
                old_public_id = extract_public_id_from_url(user.profile_image)
                destroy(old_public_id)
            except Exception as e:
                print(f"Warning: Failed to delete old profile image: {str(e)}")

        # Upload new image to Cloudinary
        result = upload(
            file_content, 
            folder="profile_images",
            public_id=f"user_{user.id}_{datetime.datetime.now().timestamp()}",
            overwrite=True,
            resource_type="image"
        )

        # Update user's profile image URL
        user.profile_image = result["secure_url"]
        user.save()

        return {
            "message": "Profile image uploaded successfully",
            "image_url": result["secure_url"]
        }

    except CloudinaryError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Cloudinary error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete("/image", status_code=status.HTTP_200_OK)
async def delete_profile_image(user_device: tuple = Depends(verify_device)):
    """Delete user's profile image."""
    user = user_device[0]
    
    try:
        if not user.profile_image:
            raise HTTPException(
                status_code=404, 
                detail="No profile image found"
            )

        # Extract public_id and delete from Cloudinary
        public_id = extract_public_id_from_url(user.profile_image)
        destroy(public_id)

        # Remove image URL from user profile
        user.profile_image = None
        user.save()

        return {"message": "Profile image deleted successfully"}

    except CloudinaryError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Cloudinary error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )


