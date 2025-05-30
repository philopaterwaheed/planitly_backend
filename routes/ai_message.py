from fastapi import APIRouter, Depends, status
from models import User, Subject_db, Subject, Connection_db, CustomTemplate_db
from middleWares import verify_device
from models import AIMessage_db

router = APIRouter(prefix="/chat", tags=["AI Messaging"])

@router.post("/", status_code=status.HTTP_200_OK)
async def message_ai(
    request: dict,
    user_device: tuple = Depends(verify_device)
):
    """
    Send a message to the AI, providing AI-accessible subjects (full data), not-done connections, templates, and user id.
    """
    user = user_device[0]

    # Get AI-accessible subjects (full data)
    message = request.get("message", "")
    ai_subject_ids = user.settings.get("ai_accessible", [])
    ai_subjects_full_data = []
    for subj_id in ai_subject_ids:
        subj_db = Subject_db.objects(id=subj_id, owner=user.id).first()
        if subj_db:
            subj = Subject.from_db(subj_db)
            if subj:
                full_data = await subj.get_full_data()
                ai_subjects_full_data.append(full_data)

    # Get current not-done connections
    connections = list(Connection_db.objects(owner=user.id, done=False))
    connections_data = [conn.to_json() for conn in connections]

    # Get user's custom templates
    templates = list(CustomTemplate_db.objects(owner=user.id))
    templates_data = [tpl.to_mongo().to_dict() for tpl in templates]

    return {
        "message": message,
        "user_id": str(user.id),
        "ai_accessible_subjects": ai_subjects_full_data,
        "not_done_connections": connections_data,
        "custom_templates": templates_data
    }

@router.get("/messages", status_code=status.HTTP_200_OK)
async def get_user_messages(user_device: tuple = Depends(verify_device)):
    """
    Get all AI messages for the current user.
    """
    user = user_device[0]
    messages = list(AIMessage_db.objects(user_id=str(user.id)).order_by("-created_at"))
    messages_data = [
        {
            "user_message": msg.user_message,
            "ai_response": msg.ai_response,
            "created_at": msg.created_at
        }
        for msg in messages
    ]
    return {"messages": messages_data}