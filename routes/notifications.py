from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from models import Notification_db, Notification, NotificationCount, FCMManager
from models import User
from middleWares import verify_device, get_device_identifier
from mongoengine.errors import DoesNotExist

router = APIRouter(prefix="/notifications", tags=["Notification"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_notification(data: dict, current_user: User = Depends(verify_device)):
    """Create a new notification for a user."""
    user_id = data.get("user_id")

    title = data.get("title")
    message = data.get("message")
    if not user_id or not title or not message:
        raise HTTPException(
            status_code=400, detail="user_id, title, and message are required"
        )
    if user_id != str(current_user.id) and not current_user.admin:
        raise HTTPException(
            status_code=403, detail="Not authorized to create notification for this user"
        )

    try:
        notification = Notification_db(
            user_id=user_id,
            title=title,
            message=message,
        )
        notification.save()

        count_obj = NotificationCount.objects(user_id=user_id).first()
        if not count_obj:
            count_obj = NotificationCount(user_id=user_id, count="1")
        else:
            count_obj.count = str(int(count_obj.count) + 1)
        count_obj.save()
        await FCMManager.send_notification(
            user_id=user_id,
            title=title,
            body=message,
            data={
                "type": "notification",
                "notification_id": str(notification.id)
            }
        )
        return {"message": "Notification created successfully", "notification": notification.to_dict()}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/", status_code=status.HTTP_200_OK)
async def get_notifications(
    current_user: User = Depends(verify_device),
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0)
):
    try:
        if not current_user.admin and limit > 20:
            limit = 20

        notifications = Notification_db.objects(user_id=str(current_user.id)) \
            .order_by("-created_at") \
            .skip(offset) \
            .limit(limit)
        count = Notification_db.objects(user_id=str(current_user.id)).count()
        return {
            "total": count,
            "notifications": [notification.to_dict() for notification in notifications]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{notification_id}/mark-read", status_code=status.HTTP_200_OK)
async def mark_notification_as_read(notification_id: str, current_user: User = Depends(verify_device)):
    """Mark a notification as read."""
    try:
        notification = Notification_db.objects.get(
            id=notification_id, user_id=str(current_user.id))
        if notification.user_id != str(current_user.id) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to mark this notification as read"
            )
        notification.is_read = True
        notification.save()
        return {"message": "Notification marked as read", "notification": notification.to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(notification_id: str, current_user: User = Depends(verify_device)):
    """Delete a notification."""
    try:
        notification = Notification_db.objects.get(
            id=notification_id, user_id=str(current_user.id))
        if notification.user_id != str(current_user.id) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this notification"
            )
        count_obj, _ = NotificationCount.objects.get_or_create(
            user_id=current_user.id)
        count_obj.count = str(int(count_obj.count) + 1)
        count_obj.save()

        notification.delete()
        return {"message": "Notification deleted successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.post("/register-fcm-token", status_code=status.HTTP_200_OK)
async def register_fcm_token(request: Request, token_data: dict, current_user: User = Depends(verify_device)):
    """Register a Firebase Cloud Messaging token for the current device"""
    try:
        fcm_token = token_data.get("fcm_token")
        if not fcm_token:
            raise HTTPException(
                status_code=400, detail="FCM token is required")

        device_id = get_device_identifier(request)
        if not device_id:
            raise HTTPException(
                status_code=400, detail="Either device_id or request is required")

        # Check if this is a registered device for the user
        if device_id not in current_user.devices:
            raise HTTPException(status_code=403, detail="Unregistered device")

        # Register the FCM token
        success = await FCMManager.register_token(str(current_user.id), device_id, fcm_token)
        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to register FCM token")

        return {"message": "FCM token registered successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
