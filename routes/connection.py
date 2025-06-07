from fastapi import APIRouter, Depends, HTTPException, status
from models import User, Component, Component_db,  Subject_db, DataTransfer, DataTransfer_db, Connection_db, Connection
from middleWares import verify_device, admin_required
from mongoengine.errors import DoesNotExist
from dateutil import parser as date_parser
import pytz

router = APIRouter(prefix="/connections", tags=["Connections"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_connection(data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid request body format")

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

    # Parse and normalize start_date and end_date to UTC
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    try:
        if start_date:
            dt = date_parser.parse(start_date)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            else:
                dt = dt.astimezone(pytz.UTC)
            start_date = dt
        if end_date:
            dt = date_parser.parse(end_date)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            else:
                dt = dt.astimezone(pytz.UTC)
            end_date = dt
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    try:
        new_connection = Connection(
            source_subject=source_subject,
            target_subject=target_subject,
            con_type=data["con_type"],
            owner=current_user.id,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating connection object: {str(e)}")

    daata_transfers = data.get("data_transfers", [])
    try:
        for transfer in daata_transfers:
            if not isinstance(transfer, dict):
                raise HTTPException(status_code=400, detail="Each data_transfer must be a dictionary")
            source_id = transfer.get("source_component") or 0
            source_component = None
            if source_id:
                source_component = Component_db.objects(id=source_id).first()
                if not source_component:
                    raise HTTPException(
                        status_code=404, detail=f"Source component {source_id} not found")
            target_component_id = transfer.get("target_component")
            if not target_component_id:
                raise HTTPException(
                    status_code=400, detail="Target component is required in data_transfer")
            target_component = Component_db.objects(id=target_component_id).first()
            if not target_component:
                raise HTTPException(
                    status_code=404, detail=f"Target component {target_component_id} not found")
            if "data_value" not in transfer or "operation" not in transfer:
                raise HTTPException(
                    status_code=400, detail="data_value and operation are required in data_transfer")
            await new_connection.add_data_transfer(
                source_component, target_component, transfer["data_value"], transfer["operation"], transfer.get("details"))
        if len(daata_transfers) == 0:
            new_connection.save_to_db()

        # let me see if we need to keep them
        """ source_subject.update(add_to_set__connections=new_connection.id) """
        """ target_subject.update(add_to_set__connections=new_connection.id) """

        return new_connection.to_json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")



@router.get("/{connection_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_connection_by_id(connection_id: str):
    """Retrieve a connection by its ID."""
    try:
        connection = Connection_db.objects.get(id=connection_id)
        return connection.to_mongo()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.get("/all", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device), Depends(admin_required)])
async def get_all_connections():
    """Retrieve all connections (Admin Only)."""
    connections = Connection_db.objects()
    return [connection.to_mongo() for connection in connections]

@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_user_connections(user_device: tuple = Depends(verify_device)):
    """Retrieve all connections owned by the current user."""
    current_user = user_device[0]
    connections = Connection_db.objects(owner=current_user.id)
    return [connection.to_mongo() for connection in connections]

@router.delete("/{connection_id}", status_code=status.HTTP_200_OK)
async def delete_connection(connection_id: str, user_device: tuple = Depends(verify_device)):
    """Delete a connection and remove it from the source and target subjects."""
    current_user = user_device[0]
    try:
        connection = Connection_db.objects.get(id=connection_id)
        if str(current_user.id) == str(connection.owner) or current_user.admin:
            # Get data transfer IDs for bulk deletion
            data_transfer_ids = [dt.id for dt in connection.data_transfers if dt]
            
            # Bulk delete all associated data transfers
            if data_transfer_ids:
                deleted_dt_count = DataTransfer_db.objects(id__in=data_transfer_ids).delete()
                print(f"Deleted {deleted_dt_count} data transfers for connection {connection_id}")

            # Delete the connection
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

# Add bulk deletion route for multiple connections
@router.delete("/bulk", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def bulk_delete_connections(data: dict, user_device: tuple = Depends(verify_device)):
    """Bulk delete multiple connections and their data transfers."""
    current_user = user_device[0]
    try:
        connection_ids = data.get("connection_ids", [])
        if not connection_ids:
            raise HTTPException(status_code=400, detail="No connection IDs provided")

        # Get all connections and verify ownership
        connections = Connection_db.objects(id__in=connection_ids)
        authorized_ids = []
        all_data_transfer_ids = []
        
        for connection in connections:
            if str(current_user.id) == str(connection.owner) or current_user.admin:
                authorized_ids.append(connection.id)
                # Collect data transfer IDs
                dt_ids = [dt.id for dt in connection.data_transfers if dt]
                all_data_transfer_ids.extend(dt_ids)

        if not authorized_ids:
            raise HTTPException(status_code=403, detail="Not authorized to delete any of these connections")

        # Bulk delete data transfers first
        dt_deleted_count = 0
        if all_data_transfer_ids:
            dt_deleted_count = DataTransfer_db.objects(id__in=all_data_transfer_ids).delete()

        # Bulk delete connections
        conn_deleted_count = Connection_db.objects(id__in=authorized_ids).delete()
        
        return {
            "message": f"Successfully deleted {conn_deleted_count} connections and {dt_deleted_count} data transfers",
            "connections_deleted": conn_deleted_count,
            "data_transfers_deleted": dt_deleted_count,
            "requested_count": len(connection_ids)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
