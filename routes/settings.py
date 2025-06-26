from fastapi import APIRouter, Depends, HTTPException, status
from models import  Subject_db, Device_db
from middleWares import verify_device

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/ai-accessible", status_code=status.HTTP_200_OK)
async def get_ai_accessible_subjects(user_device: tuple = Depends(verify_device)):
    user = user_device[0]
    return {"ai_accessible": user.settings.get("ai_accessible", [])}

@router.post("/ai-accessible/add", status_code=status.HTTP_200_OK)
async def add_ai_accessible_subject(data:dict, user_device: tuple = Depends(verify_device)):
    user = user_device[0]
    subject_id = data.get("subject_id")
    if not subject_id:
        raise HTTPException(status_code=400, detail="Missing subject_id in request body.")
    ai_list = user.settings.get("ai_accessible", [])
    if subject_id in ai_list:
        raise HTTPException(status_code=400, detail="Subject already in AI-accessible list.")
    if len(ai_list) >= 10:
        raise HTTPException(status_code=400, detail="AI-accessible subjects limit (10) reached.")
    # Check subject ownership
    subject = Subject_db.objects(id=subject_id, owner=user.id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not owned by user.")
    ai_list.append(subject_id)
    user.settings["ai_accessible"] = ai_list
    user.save()
    return {"message": "Subject added to AI-accessible list.", "ai_accessible": ai_list}

@router.post("/ai-accessible/remove", status_code=status.HTTP_200_OK)
async def remove_ai_accessible_subject(data:dict, user_device: tuple = Depends(verify_device)):
    user = user_device[0]
    subject_id = data.get("subject_id")
    if not subject_id:
        raise HTTPException(status_code=400, detail="Missing subject_id in request body.")
    ai_list = user.settings.get("ai_accessible", [])
    if subject_id not in ai_list:
        raise HTTPException(status_code=404, detail="Subject not in AI-accessible list.")
    ai_list.remove(subject_id)
    user.settings["ai_accessible"] = ai_list
    user.save()
    return {"message": "Subject removed from AI-accessible list.", "ai_accessible": ai_list}

@router.get("/theme", status_code=status.HTTP_200_OK)
async def get_preferred_theme(user_device: tuple = Depends(verify_device)):
    """Get user's preferred theme setting."""
    user = user_device[0]
    return {"preferred_theme": user.settings.get("preferred_theme", "light")}

@router.post("/theme", status_code=status.HTTP_200_OK)
async def set_preferred_theme(data: dict, user_device: tuple = Depends(verify_device)):
    """Set user's preferred theme."""
    user = user_device[0]
    theme = data.get("theme")
    
    if not theme:
        raise HTTPException(status_code=400, detail="Missing theme in request body.")
    
    # Validate theme options
    valid_themes = ["light", "dark", "auto"]
    if theme not in valid_themes:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid theme. Must be one of: {', '.join(valid_themes)}"
        )
    
    # Update user settings
    user.settings["preferred_theme"] = theme
    user.save()
    
    return {
        "message": "Theme preference updated successfully.", 
        "preferred_theme": theme
    }

@router.get("/", status_code=status.HTTP_200_OK)
async def get_all_settings(user_device: tuple = Depends(verify_device)):
    """Get all user settings including logged in devices."""
    user = user_device[0]
    current_device_id = user_device[1]
    
    try:
        # Get all logged in devices for the user
        devices = Device_db.objects(user_id=str(user.id))
        devices_info = []
        
        for device in devices:
            device_info = {
                "device_id": device.device_id,
                "device_name": device.device_name,
                "user_agent": device.user_agent,
                "location": device.location,
                "last_used": device.last_used.isoformat() if device.last_used else None,
                "is_current": device.device_id == current_device_id
            }
            devices_info.append(device_info)
        
        # Sort devices by last used (most recent first)
        devices_info.sort(key=lambda x: x["last_used"] or "", reverse=True)
        
        return {
            "ai_accessible": user.settings.get("ai_accessible", []),
            "preferred_theme": user.settings.get("preferred_theme", "light"),
            "logged_in_devices": {
                "total_devices": len(devices_info),
                "current_device_id": current_device_id,
                "devices": devices_info
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving settings: {str(e)}")