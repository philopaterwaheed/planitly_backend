from fastapi import APIRouter, Depends, status, HTTPException
from middleWares import verify_device
from models import AIMessage_db
from consts import env_variables
from datetime import datetime, timezone
import httpx
import os

router = APIRouter(prefix="/chat", tags=["AI Messaging"])

@router.post("/", status_code=status.HTTP_200_OK)
async def message_ai(
    request: dict,
    user_device: tuple = Depends(verify_device)
):
    """
    Send a message to the AI
    """
    user = user_device[0]
    message = request.get("message", "")
    ai_subject_ids = user.settings.get("ai_accessible", [])

    # Convert user object to JSON-serializable format
    user_data = {
        "id": str(user.id),
        "username": getattr(user, 'username', ''),
        "email": getattr(user, 'email', ''),
        "settings": user.settings if hasattr(user, 'settings') else {},
        "created_at": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None
    }

    # Prepare data to send to AI
    ai_request_data = {
        "message": message,
        "user": user_data,
        "ai_accessible_subjects": ai_subject_ids
    }

    # Send request to AI service
    ai_response = None
    ai_response_text = ""
    
    try:
        print (ai_request_data.get("ai_accessible_subjects", ""))
        ai_service_url = env_variables['AI_SERVICE_URL']
        
        # Configure maximum timeout - 30 minutes total, 60 seconds to connect
        timeout = httpx.Timeout(1800.0, connect=60.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{ai_service_url}/chat", json=ai_request_data)
            response.raise_for_status()
            ai_response = response.json()
            
            ai_response_text = ai_response.get("message", "")
    
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail=f"AI service timeout: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {str(e)}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"AI service error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with AI service: {str(e)}")

    # Prepare response
    response_data = {
        "ai_response": ai_response_text,
    }

    return response_data

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