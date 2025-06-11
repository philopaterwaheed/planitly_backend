from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile
from middleWares import verify_device, authenticate_user
from cloudinary.uploader import upload, destroy
from cloudinary.exceptions import Error as CloudinaryError
from cloud import extract_public_id_from_url
from models import Device_db, FCMManager
from firebase_admin import auth
import re
import datetime

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
            "full_phone_number": user.get_full_phone_number(),
            "birthday": user.birthday.isoformat() if user.birthday else None,
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
        updated_fields = []
        
        # Handle firstname
        firstname = profile_data.get("firstname")
        if firstname is not None:
            if not firstname.isalpha() or len(firstname) < 2 or len(firstname) > 19:
                raise HTTPException(
                    status_code=400,
                    detail="First name must contain only alphabetic characters and be between 2-19 characters long.",
                )
            if user.firstname != firstname:
                user.firstname = firstname
                updated_fields.append("firstname")

        # Handle lastname
        lastname = profile_data.get("lastname")
        if lastname is not None:
            if not lastname.isalpha() or len(lastname) < 2 or len(lastname) > 19:
                raise HTTPException(
                    status_code=400,
                    detail="Last name must contain only alphabetic characters and be between 2-19 characters long.",
                )
            if user.lastname != lastname:
                user.lastname = lastname
                updated_fields.append("lastname")

        # Handle phone number
        phone_number = profile_data.get("phone_number")
        if phone_number is not None:
            try:
                # Compare current phone number with new one
                current_phone = user.phone_number or {"country_code": "", "number": ""}
                if current_phone != phone_number:
                    user.set_phone_number(phone_number)
                    updated_fields.append("phone_number")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        # Handle birthday
        birthday = profile_data.get("birthday")
        if birthday is not None:
            try:
                if not isinstance(birthday, str):
                    birthday = datetime.datetime.strptime(birthday, "%Y-%m-%d %H:%M:%S")

                birthday_date = datetime.datetime.fromisoformat(birthday)
                if birthday_date > datetime.datetime.now():
                    raise HTTPException(
                        status_code=400, detail="Birthday cannot be in the future."
                    )
                if (datetime.datetime.now() - birthday_date).days < 13 * 365:
                    raise HTTPException(
                        status_code=400, detail="Users must be at least 13 years old."
                    )
                
                # Compare dates (normalize to date only for comparison)
                current_birthday = user.birthday.date() if user.birthday else None
                new_birthday = birthday_date.date()
                
                if current_birthday != new_birthday:
                    user.birthday = birthday_date
                    updated_fields.append("birthday")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid birthday format. Use ISO format (YYYY-MM-DD)."
                )

        # Only save if there are changes
        if updated_fields:
            user.save()
            return {
                "message": "Profile updated successfully",
                "updated_fields": updated_fields
            }
        else:
            return {
                "message": "No changes detected",
                "updated_fields": []
            }
            
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


@router.put("/change-password", status_code=status.HTTP_200_OK)
async def change_password(user_data: dict, user_device: tuple = Depends(verify_device)):
    """
    Change the password for the authenticated user.
    """
    current_user = user_device[0]
    current_device_id = user_device[1]
    
    try:
        old_password = user_data.get("oldPassword")
        new_password = user_data.get("newPassword")

        if not old_password or not new_password:
            raise HTTPException(status_code=400, detail="Old and new passwords are required.")

        # Validate new password strength
        if not re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&^#_+=<>.,;:|\\/-])[A-Za-z\d@$!%*?&^#_+=<>.,;:|\\/-]{8,}$", new_password):
            raise HTTPException(
                status_code=400, detail="Weak password. Must contain uppercase, lowercase, number, special character, and be at least 8 characters long."
            )

        # Verify old password
        user, error_message = await authenticate_user(current_user.email, old_password, None)
        if not user:
            raise HTTPException(status_code=401, detail="Old password is incorrect.")
        
        try:
            # Update password in Firebase
            auth.update_user(current_user.firebase_uid, password=new_password)
        except auth.AuthError as e:
            raise HTTPException(status_code=400, detail=f"Firebase error: {str(e)}")

        # Log out all other devices for security
        try:
            logged_out_devices = []
            devices_to_logout = Device_db.objects(
                user_id=str(current_user.id),
                device_id__ne=current_device_id
            )
            
            for device in devices_to_logout:
                try:
                    from utils import logout_user
                    await logout_user(current_user, device.device_id)
                    logged_out_devices.append(device.device_id)
                except Exception as logout_error:
                    print(f"Warning: Failed to logout device {device.device_id}: {logout_error}")
                    # Continue with other devices even if one fails
            
            # Send notification to other devices about password change and logout
            await FCMManager.send_password_change_notification(
                user_id=str(current_user.id),
                current_device_id=current_device_id
            )
            
            return {
                "message": "Password changed successfully. All other devices have been logged out for security.",
                "updated_fields": ["password"],
                "logged_out_devices": len(logged_out_devices),
                "security_action": "other_devices_logged_out"
            }
            
        except Exception as security_error:
            # Password was changed successfully, but device logout failed
            print(f"Warning: Password changed but failed to logout other devices: {security_error}")
            return {
                "message": "Password changed successfully, but some devices may still be logged in. Please check your devices.",
                "updated_fields": ["password"],
                "warning": "Device logout partially failed"
            }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


