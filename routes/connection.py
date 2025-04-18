from fastapi import APIRouter, Depends, HTTPException, status
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db, Connection_db, Connection
from middleWares import verify_device, admin_required
from mongoengine.errors import DoesNotExist

router = APIRouter(prefix="/connections", tags=["Connections"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_connection(data: dict, current_user: User = Depends(verify_device)):
    if 'source_subject' not in data or 'target_subject' not in data:
        raise HTTPException(
            status_code=400, detail="Source and Target subjects are required")

    source_subject = Subject_db.objects(id=data["source_subject"]).first()
    target_subject = Subject_db.objects(id=data["target_subject"]).first()

    if not source_subject:
        raise HTTPException(status_code=404, detail="Source subject not found")

    if not target_subject:
        raise HTTPException(status_code=404, detail="Target subject not found")

    if 'con_type' not in data:
        raise HTTPException(
            status_code=400, detail="Connection type is required")

    new_connection = Connection(
        source_subject=source_subject,
        target_subject=target_subject,
        con_type=data["con_type"],
        owner=current_user.id,
        start_date=data.get("start_date"),
        end_date=data.get("end_date")
    )

    try:
        for transfer in data.get("data_transfers", []):
            source_id = transfer.get("source_component") or 0
            source_component = Component_db.objects(
                id=source_id).first()
            target_component = Component_db.objects(
                id=transfer["target_component"]).first()
            if not target_component:
                raise HTTPException(
                    status_code=404, detail="Target component not found")
            await new_connection.add_data_transfer(
                source_component, target_component, transfer["data_value"], transfer["operation"], transfer.get("details"))
            new_connection.save_to_db()

        # let me see if we need to keep them
        """ source_subject.update(add_to_set__connections=new_connection.id) """
        """ target_subject.update(add_to_set__connections=new_connection.id) """

        return new_connection.to_json()
    finally:
        pass
    """ except Exception as e: """
    """     raise HTTPException( """
    """         status_code=500, detail=f"An error occurred: {str(e)}") """


@router.get("/{connection_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_connection_by_id(connection_id: str):
    """Retrieve a connection by its ID."""
    try:
        connection = Connection_db.objects.get(id=connection_id)
        return connection.to_mongo()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device), Depends(admin_required)])
async def get_all_connections():
    """Retrieve all connections (Admin Only)."""
    connections = Connection_db.objects()
    return [connection.to_mongo() for connection in connections]


@router.delete("/{connection_id}", status_code=status.HTTP_200_OK)
async def delete_connection(connection_id: str, current_user: User = Depends(verify_device)):
    """Delete a connection and remove it from the source and target subjects."""
    try:
        connection = Connection_db.objects.get(id=connection_id)
        if str(current_user.id) == str(connection.owner) or current_user.admin:
            source_subject = Subject_db.objects.get(
                id=connection.source_subject.id)
            target_subject = Subject_db.objects.get(
                id=connection.target_subject.id)

            # let me see if we need to keep them
            """ source_subject.update(pull__connections=connection_id) """
            """ target_subject.update(pull__connections=connection_id) """

            connection.delete()
            return {"message": "Connection deleted successfully", "id": connection_id}

        raise HTTPException(
            status_code=403, detail="Not authorized to delete this connection")

    except DoesNotExist:
        raise HTTPException(
            status_code=404, detail="Connection or Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
