from fastapi import APIRouter, Depends, HTTPException, status
from models import Widget_db, Widget, Component_db, User, Subject_db
from mongoengine.errors import DoesNotExist, ValidationError
from middleWares import get_current_user
import uuid

router = APIRouter(prefix="/widgets", tags=["Widget"])


@router.post("/", dependencies=[Depends(get_current_user)], status_code=status.HTTP_201_CREATED)
async def create_widget(data: dict, current_user: User = Depends(get_current_user)):
    try:
        data_id = data.get('id', str(uuid.uuid4()))
        widget_type = data.get('type')
        host_subject_id = data.get('host_subject')
        reference_component_id = data.get('reference_component')
        data_value = data.get('data')


        if not widget_type or not host_subject_id:
            raise HTTPException(
                status_code=400, detail="Type and Host Subject are required"
            )

        host_subject = Subject_db.objects(id=host_subject_id).first()
        if not host_subject:
            raise HTTPException(status_code=404, detail="Host Subject not found")

        if current_user.id != host_subject.owner and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to create widget for this subject")

        reference_component = None
        if reference_component_id:
            reference_component = Component_db.objects(id=reference_component_id).first()
            if not reference_component:
                raise HTTPException(status_code=404, detail="Reference Component not found")

        widget = Widget(
            id=data_id,
            type=widget_type,
            host_subject=host_subject_id,
            reference_component=reference_component_id,
            data=data_value,
            owner=current_user.id
        )

        widget.save_to_db()

        return {"message": "Widget created successfully", "id": str(widget.id)}

    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/{widget_id}", dependencies=[Depends(get_current_user)], status_code=status.HTTP_200_OK)
async def get_widget(widget_id: str, current_user: User = Depends(get_current_user)):
    try:
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to access this widget")

        return widget.to_mongo().to_dict()

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/", dependencies=[Depends(get_current_user)], status_code=status.HTTP_200_OK)
async def get_all_widgets(current_user=Depends(get_current_user)):
    widgets = Widget_db.objects(owner=current_user.id)
    return [widget.to_mongo().to_dict() for widget in widgets]


@router.delete("/{widget_id}", dependencies=[Depends(get_current_user)], status_code=status.HTTP_200_OK)
async def delete_widget(widget_id: str, current_user=Depends(get_current_user)):
    try:
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to delete this widget")

        widget.delete()
        return {"message": "Widget deleted successfully", "id": widget_id}

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
