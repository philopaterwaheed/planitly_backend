from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from datetime import datetime, timezone
import uuid
from middleWares import verify_device, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db
from mongoengine.errors import DoesNotExist, ValidationError
from dateutil import parser as date_parser
import pytz

router = APIRouter(prefix="/datatransfers", tags=["DataTransfer"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_data_transfer(data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    try:
        data_id = data.get('id', str(uuid.uuid4()))
        source_component_id = data.get('source_component') or 1
        target_component_id = data.get('target_component') or 1

        if not target_component_id:
            raise HTTPException(  # Check if the target component is provided
                status_code=400, detail="Target component is required")
        source_component = Component_db.objects(
            id=source_component_id).first() or None
        target_component = Component_db.objects(
            id=target_component_id).first() or None

        if not target_component:
            raise HTTPException(
                status_code=404, detail="Target component not found")
        # spearate the if statements to avoid the error of accessing the owner attribute of None
        if source_component != None and current_user.id != source_component.owner:
            raise HTTPException(
                status_code=403, detail="Not authorized to create this data transfer")
        if (current_user.id != target_component.owner) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to create this data transfer")

        schedule_time = None
        if 'schedule_time' in data and data['schedule_time']:
            try:
                dt = date_parser.parse(data['schedule_time'])
                if dt.tzinfo is None:
                    raise HTTPException(
                        status_code=400, detail="schedule_time must include timezone information"
                    )
                schedule_time = dt.astimezone(timezone.utc)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid date format for 'schedule_time'")

        data_transfer = DataTransfer(
            id=data_id,
            source_component=source_component.id if source_component else None,
            target_component=target_component.id,
            data_value=data.get("data_value"),
            operation=data.get("operation"),
            schedule_time=schedule_time,
            details=data.get("details") or {},
            owner = current_user.id
        )

        if schedule_time and datetime.now(timezone.utc) >= schedule_time:
            if data_transfer.execute():
                return {"message": "Data transfer executed immediately", "id": str(data_transfer.id)}
            raise HTTPException(
                status_code=500, detail="Failed to execute data transfer")
        if not schedule_time:
            if data_transfer.execute():
                return {"message": "Data transfer executed immediately", "id": str(data_transfer.id)}
            raise HTTPException(
                status_code=500, detail="Failed to execute data transfer")

        data_transfer.save_to_db()
        return {"message": "Data transfer created", "id": str(data_transfer.id)}
    except DoesNotExist as e:
        raise HTTPException(
            status_code=404, detail=f"Component not found: {str(e)}")
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/{transfer_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_data_transfer(transfer_id: str, user_device: tuple = Depends(verify_device)):
    """ Retrieve a data transfer by its ID. """
    current_user = user_device[0]
    try:
        data_transfer = DataTransfer_db.objects.get(id=transfer_id)
        if (current_user.id != data_transfer.source_component.owner and
                current_user.id != data_transfer.target_component.owner) or not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this data transfer")
        return data_transfer.to_mongo().to_dict()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Data transfer not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/", dependencies=[Depends(verify_device), Depends(admin_required)], status_code=status.HTTP_200_OK)
async def get_all_data_transfers(user_device: tuple =Depends(verify_device)):
    """ Retrieve all data transfers. """
    data_transfers = DataTransfer_db.objects()
    return [dt.to_mongo().to_dict() for dt in data_transfers]


@router.delete("/{transfer_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def delete_data_transfer(transfer_id: str, user_device: tuple =Depends(verify_device)):
    """Delete a data transfer."""
    current_user = user_device[0]
    try:
        data_transfer = DataTransfer_db.objects.get(id=transfer_id)
        if (current_user.id != data_transfer.source_component.owner and
                current_user.id != data_transfer.target_component.owner) or not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this data transfer")
        data_transfer.delete()
        return {"message": "Data transfer deleted successfully", "id": transfer_id}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Data transfer not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
