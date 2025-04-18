from fastapi import APIRouter, Depends, HTTPException, status
from models.notifications import Notification_DB
from models import User
from middleWares import verify_device
from mongoengine.errors import DoesNotExist

router = APIRouter(prefix="/notifications", tags=["Notification_DB"])

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_notification(data: dict, current_user: User = Depends(verify_device)):
    """Create a new notification for a user."""
    try:
        notification = Notification_DB(
            user_id=data.get("user_id"),
            title=data.get("title"),
            message=data.get("message")
        )
        notification.save()
        return {"message": "Notification_DB created successfully", "notification": notification.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/", status_code=status.HTTP_200_OK)
async def get_notifications(current_user: User = Depends(verify_device)):
    """Retrieve all notifications for the current user."""
    try:
        notifications = Notification_DB.objects(user_id=str(current_user.id))
        return [notification.to_dict() for notification in notifications]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.put("/{notification_id}/mark-read", status_code=status.HTTP_200_OK)
async def mark_notification_as_read(notification_id: str, current_user: User = Depends(verify_device)):
    """Mark a notification as read."""
    try:
        notification = Notification_DB.objects.get(id=notification_id, user_id=str(current_user.id))
        notification.is_read = True
        notification.save()
        return {"message": "Notification_DB marked as read", "notification": notification.to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Notification_DB not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(notification_id: str, current_user: User = Depends(verify_device)):
    """Delete a notification."""
    try:
        notification = Notification_DB.objects.get(id=notification_id, user_id=str(current_user.id))
        notification.delete()
        return {"message": "Notification_DB deleted successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Notification_DB not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")