import mongoengine as me
from datetime import datetime
import json
from pymongo import UpdateOne
from .user import User
# Removed the Component import from here to avoid circular import
from mongoengine import Document, StringField, ReferenceField, DateTimeField, DynamicField, IntField
from mongoengine.errors import ValidationError


class ArrayMetadata(Document):
    """Array metadata model that can be hosted by either a Component or Widget."""
    user = ReferenceField(User, required=True)
    name = StringField(required=True)
    
    # Host can be either a component or a widget (mutually exclusive)
    host_component = StringField(required=False)  # Component ID as string
    host_widget = StringField(required=False)     # Widget ID as string
    
    length = IntField(default=0)  # Track array size
    created_at = DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'array_metadata',
        'indexes': [
            {'fields': ['user', 'name'], 'unique': True},
            {'fields': ['host_component']},
            {'fields': ['host_widget']},
        ]
    }

    def clean(self):
        """Ensure exactly one host is specified."""
        has_component = bool(self.host_component)
        has_widget = bool(self.host_widget)
        
        if not has_component and not has_widget:
            raise ValidationError("ArrayMetadata must have either host_component or host_widget")
        
        if has_component and has_widget:
            raise ValidationError("ArrayMetadata cannot have both host_component and host_widget")

    def get_host_id(self):
        """Get the host ID regardless of whether it's a component or widget."""
        return self.host_component or self.host_widget

    def get_host_type(self):
        """Get the type of host ('component' or 'widget')."""
        if self.host_component:
            return 'component'
        elif self.host_widget:
            return 'widget'
        return None

    @staticmethod
    def to_dict(self):
        """Convert ArrayMetadata document to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user.id),
            "name": self.name,
            "host_component": self.host_component,
            "host_widget": self.host_widget,
            "host_type": self.get_host_type(),
            "host_id": self.get_host_id(),
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
    def _get_array_metadata(user, host_id, host_type):
        """Get array metadata by host ID and type."""
        if host_type == 'component':
            return ArrayMetadata.objects(user=user, host_component=str(host_id)).first()
        elif host_type == 'widget':
            return ArrayMetadata.objects(user=user, host_widget=str(host_id)).first()
        else:
            raise ValueError("host_type must be 'component' or 'widget'")

    @staticmethod
    def _detect_host_type(host_id):
        """Detect if host_id belongs to a component or widget."""
        try:
            # Try to import and check if it's a component
            from .component import Component_db
            component = Component_db.objects(id=str(host_id)).first()
            if component:
                return 'component'
            
            # Try to check if it's a widget
            from .widget import Widget_db
            widget = Widget_db.objects(id=str(host_id)).first()
            if widget:
                return 'widget'
            
            return None
        except Exception:
            return None

    @staticmethod
    def _get_host_object(host_id, host_type=None):
        """Get the complete host object (Component or Widget)."""
        try:
            if not host_type:
                host_type = Arrays._detect_host_type(host_id)
                if not host_type:
                    return None, None
            
            if host_type == 'component':
                from .component import Component_db
                host = Component_db.objects(id=str(host_id)).first()
                return host, 'component'
            elif host_type == 'widget':
                from .widget import Widget_db
                host = Widget_db.objects(id=str(host_id)).first()
                return host, 'widget'
            else:
                return None, None
        except Exception:
            return None, None

    @staticmethod
    def create_array(user_id, host_id, array_name, host_type=None, initial_elements=None):
        """Create a new array for a user with smart host detection."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type
            host_object, detected_host_type = Arrays._get_host_object(host_id, host_type)
            if not host_object:
                return {"success": False, "message": "Invalid host ID - not a component or widget"}

            # Check if array already exists for this host and array name
            existing_array = Arrays._get_array_metadata_by_name(user, host_id, detected_host_type, array_name)
            if existing_array:
                return {"success": False, "message": f"Array '{array_name}' already exists for this {detected_host_type}"}

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
                name=array_name
            )
            
            # Set the appropriate host
            if detected_host_type == 'component':
                array_metadata.host_component = str(host_id)
            else:  # widget
                array_metadata.host_widget = str(host_id)
            
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

            return {
                "success": True, 
                "message": f"Array '{array_name}' created successfully for {detected_host_type}",
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": detected_host_type
            }
        except Exception as e:
            return {"success": False, "message": f"Error creating array: {e}"}

    @staticmethod
    def _get_array_metadata_by_name(user, host_id, host_type, array_name):
        """Get array metadata by host ID, type, and array name."""
        if host_type == 'component':
            return ArrayMetadata.objects(user=user, host_component=str(host_id), name=array_name).first()
        elif host_type == 'widget':
            return ArrayMetadata.objects(user=user, host_widget=str(host_id), name=array_name).first()
        else:
            raise ValueError("host_type must be 'component' or 'widget'")

    @staticmethod
    def _get_array_metadata_by_name_or_id(user, host_id, host_type, array_name=None, array_id=None):
        """Get array metadata by host ID, type, and either array name or array ID."""
        if array_id:
            # If array_id is provided, use it directly
            metadata = ArrayMetadata.objects(id=array_id, user=user).first()
            if metadata:
                # Verify it belongs to the correct host
                if host_type == 'component' and metadata.host_component == str(host_id):
                    return metadata
                elif host_type == 'widget' and metadata.host_widget == str(host_id):
                    return metadata
            return None
        elif array_name:
            # Use existing name-based lookup
            return Arrays._get_array_metadata_by_name(user, host_id, host_type, array_name)
        else:
            # Neither provided, use default array lookup
            return Arrays._get_array_metadata(user, host_id, host_type)

    @staticmethod
    def get_array_by_name(user_id, host_id, array_name=None, host_type=None, page=0, page_size=100, array_id=None):
        """Get array by name or ID with smart host detection."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type
            host_object, detected_host_type = Arrays._get_host_object(host_id, host_type)
            if not host_object:
                return {"success": False, "message": "Invalid host ID"}

            # Get array metadata by name or ID
            array_metadata = Arrays._get_array_metadata_by_name_or_id(user, host_id, detected_host_type, array_name, array_id)
            if not array_metadata:
                identifier = f"ID '{array_id}'" if array_id else f"name '{array_name}'"
                return {"success": False, "message": f"Array with {identifier} not found for {detected_host_type} '{host_id}'"}

            # Get total count for pagination info
            total_count = ArrayItem_db.objects(user=user, array_metadata=array_metadata).count()
                
            # Calculate pagination values
            total_pages = (total_count + page_size - 1) // page_size
            if page < 0:
                page = 0
            if page >= total_pages and total_pages > 0:
                page = total_pages - 1
                
            # Skip and limit for pagination
            skip_count = page * page_size

            # Retrieve array elements for this page sorted by index
            elements = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata
            ).order_by('index').skip(skip_count).limit(page_size)

            # Convert to pure array
            result_array = [{"value": element.value, "created_at": element.created_at} for element in elements]

            # Return with pagination information
            return {
                "success": True, 
                "array": result_array,
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": detected_host_type,
                "host_id": str(host_id),
                "array_name": array_metadata.name,
                "array_id": str(array_metadata.id),
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
            return {"success": False, "message": f"Error retrieving array: {e}"}

    @staticmethod
    def get_array(user_id, host_id, host_type=None, page=0, page_size=100):
        """Get array with smart host detection."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type
            host_object, detected_host_type = Arrays._get_host_object(host_id, host_type)
            if not host_object:
                return {"success": False, "message": "Invalid host ID"}

            # Get array metadata
            array_metadata = Arrays._get_array_metadata(user, host_id, detected_host_type)
            if not array_metadata:
                return {"success": False, "message": f"Array not found for {detected_host_type} '{host_id}'"}

            # Get total count for pagination info
            total_count = ArrayItem_db.objects(user=user, array_metadata=array_metadata).count()
                
            # Calculate pagination values
            total_pages = (total_count + page_size - 1) // page_size
            if page < 0:
                page = 0
            if page >= total_pages and total_pages > 0:
                page = total_pages - 1
                
            # Skip and limit for pagination
            skip_count = page * page_size

            # Retrieve array elements for this page sorted by index
            elements = ArrayItem_db.objects(
                user=user, array_metadata=array_metadata
            ).order_by('index').skip(skip_count).limit(page_size)

            # Convert to pure array
            result_array = [{"value": element.value, "created_at": element.created_at} for element in elements]

            # Return with pagination information
            return {
                "success": True, 
                "array": result_array,
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": detected_host_type,
                "host_id": str(host_id),
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
            return {"success": False, "message": f"Error retrieving array: {e}"}

    @staticmethod
    def get_entire_array(user_id, component_id):
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object
            host_object, host_type = Arrays._get_host_object(component_id)
            if not host_object:
                return {"success": False, "message": "Invalid component ID"}

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

            return {
                "success": True, 
                "array": result_array,
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": host_type
            }
        except Exception as e:
            return {"success": False, "message": f"Error retrieving array: {e}"}

    @staticmethod
    def append_to_array(user_id, host_id, value, host_type=None, array_name=None, array_id=None):
        """Append a value to the end of an array with smart host detection and name/ID support."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type
            host_object, detected_host_type = Arrays._get_host_object(host_id, host_type)
            if not host_object:
                return {"success": False, "message": "Invalid host ID"}

            # Get array metadata by name or ID
            array_metadata = Arrays._get_array_metadata_by_name_or_id(user, host_id, detected_host_type, array_name, array_id)
            if not array_metadata:
                identifier = f"ID '{array_id}'" if array_id else f"name '{array_name}'" if array_name else "default array"
                return {"success": False, "message": f"Array with {identifier} not found for {detected_host_type} '{host_id}'"}
                
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

            return {
                "success": True, 
                "message": f"Value appended to array '{array_metadata.name}' for {detected_host_type} '{host_id}'",
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": detected_host_type,
                "array_name": array_metadata.name,
                "array_id": str(array_metadata.id)
            }
        except Exception as e:
            return {"success": False, "message": f"Error appending to array: {e}"}

    @staticmethod
    def delete_array(user_id, host_id, host_type=None):
        """Delete an entire array with smart host detection."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type
            host_object, detected_host_type = Arrays._get_host_object(host_id, host_type)
            if not host_object:
                return {"success": False, "message": "Invalid host ID"}

            # Get array metadata
            array_metadata = Arrays._get_array_metadata(user, host_id, detected_host_type)
            if not array_metadata:
                return {"success": False, "message": f"Array not found for {detected_host_type} '{host_id}'"}

            # Count elements for reporting
            element_count = ArrayItem_db.objects(user=user, array_metadata=array_metadata).count()

            # Delete all array elements
            ArrayItem_db.objects(user=user, array_metadata=array_metadata).delete()

            # Delete array metadata
            array_metadata.delete()

            return {
                "success": True,
                "message": f"Array for {detected_host_type} '{host_id}' deleted successfully",
                "elements_deleted": element_count,
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": detected_host_type
            }
        except Exception as e:
            return {"success": False, "message": f"Error deleting array: {e}"}

    @staticmethod
    def insert_at_index(user_id, host_id, index, value, host_type=None, array_name=None, array_id=None):
        """Insert a value at a specific index with smart host detection and name/ID support."""
        try:
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type
            host_object, detected_host_type = Arrays._get_host_object(host_id, host_type)
            if not host_object:
                return {"success": False, "message": "Invalid host ID"}

            # Get array metadata by name or ID
            array_metadata = Arrays._get_array_metadata_by_name_or_id(user, host_id, detected_host_type, array_name, array_id)
            if not array_metadata:
                identifier = f"ID '{array_id}'" if array_id else f"name '{array_name}'" if array_name else "default array"
                return {"success": False, "message": f"Array with {identifier} not found for {detected_host_type} '{host_id}'"}

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
            PAGE_SIZE = 1000
            current_page = 0
            bulk_operations = []

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

            return {
                "success": True, 
                "message": f"Value inserted at index {index} in array '{array_metadata.name}' for {detected_host_type} '{host_id}'",
                "host_object": host_object.to_mongo().to_dict() if hasattr(host_object, 'to_mongo') else host_object.to_dict(),
                "host_type": detected_host_type,
                "array_name": array_metadata.name,
                "array_id": str(array_metadata.id)
            }
        except Exception as e:
            return {"success": False, "message": f"Error inserting at index: {e}"}

    @staticmethod
    def update_at_index(user_id, host_id, index, value, array_name=None, array_id=None, host_type=None):
        """Update the value at a specific index in the array with name/ID support."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type if not provided
            if not host_type:
                _, host_type = Arrays._get_host_object(host_id)

            # Get array metadata by name or ID
            array_metadata = Arrays._get_array_metadata_by_name_or_id(user, host_id, host_type, array_name, array_id)
            if not array_metadata:
                identifier = f"ID '{array_id}'" if array_id else f"name '{array_name}'" if array_name else "default array"
                return {"success": False, "message": f"Array with {identifier} not found"}
                
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

            return {
                "success": True, 
                "message": f"Value at index {index} updated in array '{array_metadata.name}' for {host_id}",
                "array_name": array_metadata.name,
                "array_id": str(array_metadata.id)
            }
        except Exception as e:
            return {"success": False, "message": f"Error updating at index: {e}"}

    @staticmethod
    def remove_at_index(user_id, host_id, index, array_name=None, array_id=None, host_type=None):
        """Remove the value at a specific index in the array with name/ID support."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}

            # Get host object and type if not provided
            if not host_type:
                _, host_type = Arrays._get_host_object(host_id)

            # Get array metadata by name or ID
            array_metadata = Arrays._get_array_metadata_by_name_or_id(user, host_id, host_type, array_name, array_id)
            if not array_metadata:
                identifier = f"ID '{array_id}'" if array_id else f"name '{array_name}'" if array_name else "default array"
                return {"success": False, "message": f"Array with {identifier} not found"}

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
            PAGE_SIZE = 1000
            current_page = 0
            bulk_operations = []

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

            return {
                "success": True, 
                "message": f"Value at index {index} removed from array '{array_metadata.name}' for {host_id}",
                "array_name": array_metadata.name,
                "array_id": str(array_metadata.id)
            }
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