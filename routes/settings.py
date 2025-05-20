from fastapi import APIRouter, Depends, HTTPException, status
from models import User, Subject_db
from middleWares import verify_device

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/ai-accessible", status_code=status.HTTP_200_OK)
async def get_ai_accessible_subjects(user_device: tuple = Depends(verify_device)):
    user = user_device[0]
    return {"ai_accessible": user.settings.get("ai_accessible", [])}

@router.post("/ai-accessible/add", status_code=status.HTTP_200_OK)
async def add_ai_accessible_subject(subject_id: str, user_device: tuple = Depends(verify_device)):
    user = user_device[0]
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
async def remove_ai_accessible_subject(subject_id: str, user_device: tuple = Depends(verify_device)):
    user = user_device[0]
    ai_list = user.settings.get("ai_accessible", [])
    if subject_id not in ai_list:
        raise HTTPException(status_code=404, detail="Subject not in AI-accessible list.")
    ai_list.remove(subject_id)
    user.settings["ai_accessible"] = ai_list
    user.save()
    return {"message": "Subject removed from AI-accessible list.", "ai_accessible": ai_list}