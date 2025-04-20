from models import User, RefreshToken
from models.fcmtoken import FCMManager
from fastapi import HTTPException
from errors import UserLogutError
from utils import remove_refresh_token

async def logout_user(current_user : User, device_id):
    try:
        # Step 1: Remove the device
        success , error_message = await current_user.remove_device(device_id)
        if not success:
            raise UserLogutError(error_message)
        # Step 2: Remove the refresh token
        refresh_token = RefreshToken.objects(device_id=device_id).first()
        if refresh_token:
            # Remove the refresh token from the database
            await RefreshToken.remove_token(device_id)
        else:
            # If no refresh token is found, raise an error
            raise UserLogutError(f"Refresh token not found for device {device_id}")
        removed , error_message = await remove_refresh_token(refresh_token , search_device=False)
        if not removed:
            raise UserLogutError(error_message)
        # Step 3: Remove the FCM token
        success , error_message = await FCMManager.remove_token(str(current_user.id), device_id)
        if not success:
            raise UserLogutError(error_message)   
        return {"message": "Logout successful"}
    except Exception as e:
        # Rollback: Re-add the device if FCM token removal fails
        current_user.devices.append(device_id)
        current_user.save()
        raise UserLogutError(f"An error occurred during logout: {str(e)}")
