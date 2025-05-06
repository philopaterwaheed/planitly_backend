import mongoengine as me
from datetime import datetime
import json
from pymongo import UpdateOne
from .user import User
# Removed the Component import from here to avoid circular import
from mongoengine import Document, StringField, ReferenceField, DateTimeField, DynamicField, IntField
from mongoengine.errors import NotUniqueError


class ArrayMetadata(Document):
    """Array metadata model."""
    user = ReferenceField(User, required=True)
    name = StringField(required=True)
    host_component = StringField(required=True)  # Changed to StringField to store Component ID as string
    length = IntField(default=0)  # Added length field to track array size
    created_at = DateTimeField(default=datetime.now)
    meta = {
        'collection': 'array_metadata',
        'indexes': [
            {'fields': ['user', 'name'], 'unique': True}
        ]
    }

    @staticmethod
    def to_dict(self):
        """Convert ArrayMetadata document to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user.id),
            "name": self.name,
            "length": self.length if hasattr(self, 'length') else 0,
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
    
    # Constants for limits
    MAX_ARRAY_SIZE = 100000  # Maximum number of elements allowed in an array
    MAX_VALUE_SIZE = 1048576  # 1MB maximum size for a single value (in bytes)
    
    @staticmethod
    def _check_value_size(value):
        """Check if value size is within limits."""
        try:
            # Try to estimate size using JSON serialization
            value_size = len(json.dumps(value).encode('utf-8'))
            if value_size > Arrays.MAX_VALUE_SIZE:
                return False, f"Value size exceeds maximum allowed ({Arrays.MAX_VALUE_SIZE} bytes)"
            return True, None
        except (TypeError, OverflowError) as e:
            return False, f"Unable to determine value size: {str(e)}"

    @staticmethod
    def create_array(user_id, component_id, array_name, initial_elements=None):
        """Create a new array for a user."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Lazy import Component to avoid circular import
            from .component import Component_db
            component = Component_db.objects(id=component_id).first()
            if not component:
                return {"success": False, "message": "Component not found for user"}
                
            existing_array = ArrayMetadata.objects(
                user=user, name=array_name).first()
            if existing_array:
                return {"success": False, "message": f"Array '{array_name}' already exists for this user"}
                
            # Check initial elements size
            if initial_elements:
                if len(initial_elements) > Arrays.MAX_ARRAY_SIZE:
                    return {"success": False, "message": f"Initial array size exceeds maximum allowed ({Arrays.MAX_ARRAY_SIZE} elements)"}
                
                # Check individual element sizes
                for value in initial_elements:
                    is_valid, error_msg = Arrays._check_value_size(value)
                    if not is_valid:
                        return {"success": False, "message": error_msg}

            # Create array metadata
            array_metadata = ArrayMetadata(
                user=user,
                host_component=str(component_id),  # Store as string
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
                    
                # Update length in array metadata
                array_metadata.length = len(initial_elements)
                array_metadata.save()

            return {"success": True, "message": f"Array '{array_name}' created successfully"}
        except Exception as e:
            return {"success": False, "message": f"Error creating array: {e}"}
    
    @staticmethod
    def get_array(user_id, component_id, page=0, page_size=100):
        try:
            print ("entering get_array")
            # Log the input parameters
            print(f"get_array called with user_id={user_id}, component_id={component_id}, page={page}, page_size={page_size}")

            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                print(f"User with id {user_id} not found")
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
            if not array_metadata:
                print(f"Array metadata for component_id {component_id} not found")
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Get total count for pagination info
            total_count = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()
            print(f"Total items in array: {total_count}")
                
            # Calculate pagination values
            total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
            print(f"Total pages: {total_pages}")

            # Validate page number
            if page < 0:
                print(f"Page number {page} is less than 0, resetting to 0")
                page = 0
            if page >= total_pages and total_pages > 0:
                print(f"Page number {page} exceeds total pages, resetting to {total_pages - 1}")
                page = total_pages - 1
                
            # Skip and limit for pagination
            skip_count = page * page_size
            print(f"Skipping {skip_count} items, retrieving next {page_size} items")

            # Retrieve array elements for this page sorted by index
            elements = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata
            ).order_by('index').skip(skip_count).limit(page_size)

            # Convert to pure array
            result_array = [{"value" : element.value , "created_at" : element.created_at} for element in elements]
            print(f"Retrieved {len(result_array)} items for page {page}")

            # Return with pagination information
            return {
                "success": True, 
                "array": result_array,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages - 1,
                    "has_prev": page > 0
                }
            }
        except Exception as e:
            print(f"Error in get_array: {e}")
            return {"success": False, "message": f"Error retrieving array: {e}"}

    @staticmethod
    def get_entire_array(user_id, component_id):
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Get total count
            total_count = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()
                
            # Initialize result array
            result_array = []
            
            # Process in batches
            BATCH_SIZE = 1000
            for offset in range(0, total_count, BATCH_SIZE):
                batch = ArrayItem_db.objects(
                    user=user, array_metadata=array_metadata
                ).order_by('index').skip(offset).limit(BATCH_SIZE)
                
                # Extend result array with batch values
                result_array.extend([element.value for element in batch])

            return {"success": True, "array": result_array}
        except Exception as e:
            return {"success": False, "message": f"Error retrieving array: {e}"}

    @staticmethod
    def append_to_array(user_id, component_id, value):
        """Append a value to the end of an array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}
                
            # Check value size
            is_valid, error_msg = Arrays._check_value_size(value)
            if not is_valid:
                return {"success": False, "message": error_msg}
                
            # Check if appending would exceed the maximum array size
            current_length = array_metadata.length if hasattr(array_metadata, 'length') else ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()
                
            if current_length >= Arrays.MAX_ARRAY_SIZE:
                return {"success": False, "message": f"Cannot append: array size would exceed maximum allowed ({Arrays.MAX_ARRAY_SIZE} elements)"}

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
            
            # Update length in array metadata
            array_metadata.length = new_index + 1
            array_metadata.save()

            return {"success": True, "message": f"Value appended to array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error appending to array: {e}"}

    @staticmethod
    def insert_at_index(user_id, component_id, index, value):
        """Insert a value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Check value size
            is_valid, error_msg = Arrays._check_value_size(value)
            if not is_valid:
                return {"success": False, "message": error_msg}
                
            # Get current array length for validation
            count = array_metadata.length if hasattr(array_metadata, 'length') else ArrayItem_db.objects(
                user=user, array_metadata=array_metadata).count()
                
            # Check if inserting would exceed the maximum array size
            if count >= Arrays.MAX_ARRAY_SIZE:
                return {"success": False, "message": f"Cannot insert: array size would exceed maximum allowed ({Arrays.MAX_ARRAY_SIZE} elements)"}

            # Validate index
            if index < 0 or index > count:
                return {"success": False, "message": f"Index {index} out of bounds"}

            # Use bulk update with pagination to shift elements efficiently
            PAGE_SIZE = 1000  #
            current_page = 0
            bulk_operations = []  # Initialize outside the loop

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

                # Add to bulk operations
                for element in elements_list:
                    bulk_operations.append(
                        UpdateOne(
                            {"_id": element.id},
                            {"$inc": {"index": 1}}
                        )
                    )

                current_page += 1

            # Execute bulk update if there are operations
            if bulk_operations:
                ArrayItem_db._get_collection().bulk_write(bulk_operations)

            # Insert new element
            element = ArrayItem_db(
                user=user,
                array_metadata=array_metadata,
                index=index,
                value=value
            )
            element.save()
            
            # Update length in array metadata
            array_metadata.length = count + 1
            array_metadata.save()

            return {"success": True, "message": f"Value inserted at index {index} in array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error inserting at index: {e}"}

    @staticmethod
    def update_at_index(user_id, component_id, index, value):
        """Update the value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata - fixed field name from component_id to host_component
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}
                
            # Check value size
            is_valid, error_msg = Arrays._check_value_size(value)
            if not is_valid:
                return {"success": False, "message": error_msg}

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

    @staticmethod
    def remove_at_index(user_id, component_id, index):
        """Remove the value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
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
            bulk_operations = []  # Initialize outside the loop

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

                # Add to bulk operations
                for element in elements_list:
                    bulk_operations.append(
                        UpdateOne(
                            {"_id": element.id},
                            {"$inc": {"index": -1}}
                        )
                    )

                current_page += 1

            # Execute bulk update if there are operations
            if bulk_operations:
                ArrayItem_db._get_collection().bulk_write(bulk_operations)
                
            # Update length in array metadata
            array_metadata.length = count - 1
            array_metadata.save()

            return {"success": True, "message": f"Value at index {index} removed from array '{component_id}'"}
        except Exception as e:
            return {"success": False, "message": f"Error removing at index: {e}"}

    @staticmethod
    def search_in_array(user_id, component_id, value):
        """Search for a value in the array and return its index(es)."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{component_id}' not found"}

            # Find elements with the given value
            elements = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata, value=value).only('index')

            indices = [element.index for element in elements]

            return {"success": True, "indices": indices}
        except Exception as e:
            return {"success": False, "message": f"Error searching in array: {e}"}

    @staticmethod
    def slice_array(user_id, component_id, start, end=None):
        """Get a slice of the array."""
        try:
            # Get the full array first - fixed the self reference
            result = Arrays.get_array(user_id, component_id)
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

    @staticmethod
    def delete_array(user_id, component_id):
        """Delete an entire array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get array metadata
            array_metadata = ArrayMetadata.objects(
                user=user, host_component=str(component_id)).first()
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

    @staticmethod
    def list_arrays(component_id):
        """List all arrays for a user."""
        try:
            # Get all array metadata for the component
            array_metadata_list = ArrayMetadata.objects(
                host_component=str(component_id))

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