from models import User
from models.fcmtoken import FCMManager
from fastapi import HTTPException
from errors import UserLogutError

async def logout_user(current_user : User, device_id):
    try:
        # Step 1: Remove the device
        success , error_message = await current_user.remove_device(device_id)
        if not success:
            raise UserLogutError(error_message)
        # Step 2: Remove the FCM token
        success , error_message = await FCMManager.remove_token(str(current_user.id), device_id)
        if not success:
            raise UserLogutError(error_message)   
        return {"message": "Logout successful"}
    except Exception as e:
        # Rollback: Re-add the device if FCM token removal fails
        current_user.devices.append(device_id)
        current_user.save()
        raise UserLogutError(f"An error occurred during logout: {str(e)}")
