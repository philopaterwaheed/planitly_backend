import mongoengine as me
from datetime import datetime
import json
from pymongo import UpdateOne
from models import User, Component
from mongoengine import Document, StringField, ReferenceField, DateTimeField, DynamicField, IntField
from mongoengine.errors import NotUniqueError


class ArrayMetadata(Document):
    """Array metadata model."""
    user = ReferenceField(User, required=True)
    name = StringField(required=True)
    host_component = ReferenceField(Component, required=True)
    created_at = DateTimeField(default=datetime.now)
    meta = {
        'collection': 'array_metadata',
        'indexes': [
            {'fields': ['user', 'name'], 'unique': True}
        ]
    }

    def to_dict(self):
        """Convert ArrayMetadata document to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user.id),
            "name": self.name,
            "created_at": self.created_at
        }


class ArrayItem_db(Document):
    """Array element model."""
    user = ReferenceField(User, required=True)
    array_metadata = ReferenceField(ArrayMetadata, required=True)
    index = IntField(required=True)
    value = DynamicField(required=True)
    created_at = DateTimeField(default=datetime.now)

    meta = {
        'collection': 'array_elements',
        'indexes': [
            {'fields': ['user', 'array_metadata', 'index']},
            {'fields': ['user', 'array_metadata', 'value']}
        ]
    }

    def to_dict(self):
        """Convert ArrayItem_db document to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user.id),
            "array_metadata_id": str(self.array_metadata.id),
            "index": self.index,
            "value": self.value,
            "created_at": self.created_at
        }

class Arrays:
    """Manager class for array operations using MongoEngine."""

    def create_array(self, user_id, component_id, array_name, initial_elements=None):
        """Create a new array for a user."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            component = Component.objects(id=component_id).first()
            if not component:
                return {"success": False, "message": "Component not found for user"}
            existing_array = ArrayMetadata.objects(
                user=user, name=array_name).first()
            if existing_array:
                return {"success": False, "message": f"Array '{array_name}' already exists for this user"}

            # Create array metadata
            array_metadata = ArrayMetadata(
                user=user,
                host_component=component_id,
                name=array_name
            )
            array_metadata.save()

            # Insert initial elements if provided
            if initial_elements:
                elements_to_insert = []
                for idx, value in enumerate(initial_elements):
                    element = ArrayItem_db(
                        user=user,
                        array_metadata=array_metadata,
                        index=idx,
                        value=value
                    )
                    elements_to_insert.append(element)

                if elements_to_insert:
                    ArrayItem_db.objects.insert(elements_to_insert)

            return {"success": True, "message": f"Array '{array_name}' created successfully"}
        except Exception as e:
            return {"success": False, "message": f"Error creating array: {e}"}

    def get_array(self, user_id, component_id):
        """Get an array by user_id and array_na"""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Retrieve array elements sorted by index
            elements = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).order_by('index')

            # Convert to pure array
            result_array = [element.value for element in elements]

            return {"success": True, "array": result_array}
        except Exception as e:
            return {"success": False, "message": f"Error retrieving array: {e}"}

    def append_to_array(self, user_id, component_id, value):
        """Append a value to the end of an array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Get current array length
            last_element = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).order_by('-index').first()
            new_index = 0 if last_element is None else last_element.index + 1

            # Insert new element
            element = ArrayItem_db(
                user=user,
                array_metadata=array_metadata,
                index=new_index,
                value=value
            )
            element.save()

            return {"success": True, "message": f"Value appended to array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error appending to array: {e}"}

    def insert_at_index(self, user_id, component_id, index, value):
        """Insert a value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Get current array length for validation
            count = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()

            # Validate index
            if index < 0 or index > count:
                return {"success": False, "message": f"Index {index} out of bounds"}

            # Use bulk update with pagination to shift elements efficiently
            PAGE_SIZE = 1000  #
            current_page = 0

            while True:
                # Get a page of elements to update
                elements_to_shift = ArrayItem_db.objects(
                    user=user,
                    array_metadata=array_metadata,
                    index__gte=index
                ).order_by('-index').skip(current_page * PAGE_SIZE).limit(PAGE_SIZE)

                # Convert to list to check if we have elements
                elements_list = list(elements_to_shift)
                if not elements_list:
                    break

                # Bulk update operations
                bulk_operations = []
                for element in elements_list:
                    bulk_operations.append(
                        UpdateOne(
                            {"_id": element.id},
                            {"$inc": {"index": 1}}
                        )
                    )

            # Execute bulk update if there are operations
            if bulk_operations:
                ArrayItem_db._get_collection().bulk_write(bulk_operations)

            current_page += 1

            # Insert new element
            element = ArrayItem_db(
                user=user,
                array_metadata=array_metadata,
                index=index,
                value=value
            )
            element.save()

            # Update array metadata if needed (e.g., length)
            array_metadata.length = count + 1
            array_metadata.save()

            return {"success": True, "message": f"Value inserted at index {index} in array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error inserting at index: {e}"}

    def update_at_index(self, user_id, component_id, index, value):
        """Update the value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, component_id=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Get element at index
            element = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata, index=index).first()
            if not element:
                return {"success": False, "message": f"Element at index {index} not found"}

            # Update element
            element.value = value
            element.save()

            return {"success": True, "message": f"Value at index {index} updated in array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error updating at index: {e}"}

    def remove_at_index(self, user_id, component_id, index):
        """Remove the value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Get current array length for validation
            count = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()

            # Validate index
            if index < 0 or index >= count:
                return {"success": False, "message": f"Index {index} out of bounds"}

            # Get element at index to be removed
            element_to_remove = ArrayItem_db.objects(
                user=user,
                array_metadata=array_metadata,
                index=index
            ).first()

            if not element_to_remove:
                return {"success": False, "message": f"Element at index {index} not found"}

            # First delete the element
            element_to_remove.delete()

            # Use bulk update with pagination to shift subsequent elements efficiently
            PAGE_SIZE = 1000  # Adjust based on your system resources
            current_page = 0

            while True:
                # Get a page of elements to update (those with indices > index)
                elements_to_shift = ArrayItem_db.objects(
                    user=user,
                    array_metadata=array_metadata,
                    index__gt=index
                ).order_by('index').skip(current_page * PAGE_SIZE).limit(PAGE_SIZE)

                # Convert to list to check if we have elements
                elements_list = list(elements_to_shift)
                if not elements_list:
                    break

                # Bulk update operations
                bulk_operations = []
                for element in elements_list:
                    bulk_operations.append(
                        UpdateOne(
                            {"_id": element.id},
                            {"$inc": {"index": -1}}
                        )
                    )

                # Execute bulk update if there are operations
                if bulk_operations:
                    ArrayItem_db._get_collection().bulk_write(bulk_operations)

                current_page += 1

            # Update array metadata if needed
            array_metadata.length = count - 1
            array_metadata.save()

            return {"success": True, "message": f"Value at index {index} removed from array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error removing at index: {e}"}

    def search_in_array(self, user_id, component_id, value):
        """Search for a value in the array and return its index(es)."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Find elements with the given value
            elements = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata, value=value).only('index')

            indices = [element.index for element in elements]

            return {"success": True, "indices": indices}
        except Exception as e:
            return {"success": False, "message": f"Error searching in array: {e}"}

    def slice_array(self, user_id, component_id, start, end=None):
        """Get a slice of the array."""
        try:
            # Get the full array first
            result = self.get_array(user_id, component_id)
            if not result["success"]:
                return result

            current_array = result["array"]

            # Default end value if not provided
            if end is None:
                end = len(current_array)

            # Validate indices
            start = max(0, min(start, len(current_array)))
            end = max(start, min(end, len(current_array)))

            # Get slice
            slice_result = current_array[start:end]

            return {"success": True, "slice": slice_result}
        except Exception as e:
            return {"success": False, "message": f"Error slicing array: {e}"}

    def delete_array(self, user_id, component_id):
        """Delete an entire array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=component_id).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Count elements for reporting
            element_count = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()

            # Delete all array elements
            ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).delete()

            # Delete array metadata
            array_metadata.delete()

            return {
                "success": True,
                "message": f"Array '{component_id}' deleted successfully",
                "elements_deleted": element_count
            }
        except Exception as e:
            return {"success": False, "message": f"Error deleting array: {e}"}

    def list_arrays(self, component_id):
        """List all arrays for a user."""
        try:
            # Get user by ID
            # Get all array metadata for user
            array_metadata_list = ArrayMetadata.objects(
                host_component=component_id)

            # Get array metadata with counts
            arrays_info = []
            for array_meta in array_metadata_list:
                count = ArrayItem_db.objects(
                    array_metadata=array_meta).count()
                arrays_info.append({
                    "name": array_meta.name,
                    "created_at": array_meta.created_at,
                    "element_count": count
                })

            return {"success": True, "arrays": arrays_info}
        except Exception as e:
            return {"success": False, "message": f"Error listing arrays: {e}"}
