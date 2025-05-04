"""
MongoDB User Array Operations with MongoEngine

This program uses MongoEngine to connect to MongoDB and provides array operations for users.
Instead of storing arrays directly as array types, it uses a more flexible approach
by storing array elements as individual documents with references.
"""

import mongoengine as me
from datetime import datetime
import json

# Connect to MongoDB using MongoEngine
me.connect('array_operations_db', host='mongodb://localhost:27017/')

class User(me.Document):
    """User document model."""
    username = me.StringField(required=True, unique=True)
    email = me.StringField(required=True)
    created_at = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'users',
        'indexes': [
            {'fields': ['username'], 'unique': True}
        ]
    }
    
    def to_dict(self):
        """Convert User document to dictionary."""
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at
        }

class ArrayMetadata(me.Document):
    """Array metadata model."""
    user = me.ReferenceField(User, required=True)
    name = me.StringField(required=True)
    created_at = me.DateTimeField(default=datetime.now)
    
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

class ArrayElement(me.Document):
    """Array element model."""
    user = me.ReferenceField(User, required=True)
    array_metadata = me.ReferenceField(ArrayMetadata, required=True)
    index = me.IntField(required=True)
    value = me.DynamicField(required=True)
    created_at = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'array_elements',
        'indexes': [
            {'fields': ['user', 'array_metadata', 'index']},
            {'fields': ['user', 'array_metadata', 'value']}
        ]
    }
    
    def to_dict(self):
        """Convert ArrayElement document to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user.id),
            "array_metadata_id": str(self.array_metadata.id),
            "index": self.index,
            "value": self.value,
            "created_at": self.created_at
        }


class MongoEngineArrayManager:
    """Manager class for array operations using MongoEngine."""
    
    def create_user(self, username, email):
        """Create a new user."""
        try:
            # Check if user already exists (MongoEngine will handle this with unique index, but we add explicit check)
            if User.objects(username=username).first():
                return {"success": False, "message": "Username already exists"}
            
            # Create new user document
            user = User(
                username=username,
                email=email
            )
            user.save()
            
            return {"success": True, "user_id": str(user.id), "message": "User created successfully"}
        except me.NotUniqueError:
            return {"success": False, "message": "Username already exists"}
        except Exception as e:
            return {"success": False, "message": f"Error creating user: {e}"}
    
    def get_user(self, username):
        """Get user by username."""
        try:
            user = User.objects(username=username).first()
            if user:
                return {"success": True, "user": user.to_dict()}
            return {"success": False, "message": "User not found"}
        except Exception as e:
            return {"success": False, "message": f"Error retrieving user: {e}"}
    
    def create_array(self, user_id, array_name, initial_elements=None):
        """Create a new array for a user."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Check if array name already exists for this user
            existing_array = ArrayMetadata.objects(user=user, name=array_name).first()
            if existing_array:
                return {"success": False, "message": f"Array '{array_name}' already exists for this user"}
            
            # Create array metadata
            array_metadata = ArrayMetadata(
                user=user,
                name=array_name
            )
            array_metadata.save()
            
            # Insert initial elements if provided
            if initial_elements:
                elements_to_insert = []
                for idx, value in enumerate(initial_elements):
                    element = ArrayElement(
                        user=user,
                        array_metadata=array_metadata,
                        index=idx,
                        value=value
                    )
                    elements_to_insert.append(element)
                
                if elements_to_insert:
                    ArrayElement.objects.insert(elements_to_insert)
            
            return {"success": True, "message": f"Array '{array_name}' created successfully"}
        except Exception as e:
            return {"success": False, "message": f"Error creating array: {e}"}
    
    def get_array(self, user_id, array_name):
        """Get an array by user_id and array_name."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Retrieve array elements sorted by index
            elements = ArrayElement.objects(user=user, array_metadata=array_metadata).order_by('index')
            
            # Convert to pure array
            result_array = [element.value for element in elements]
            
            return {"success": True, "array": result_array}
        except Exception as e:
            return {"success": False, "message": f"Error retrieving array: {e}"}
    
    def append_to_array(self, user_id, array_name, value):
        """Append a value to the end of an array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Get current array length
            last_element = ArrayElement.objects(user=user, array_metadata=array_metadata).order_by('-index').first()
            new_index = 0 if last_element is None else last_element.index + 1
            
            # Insert new element
            element = ArrayElement(
                user=user,
                array_metadata=array_metadata,
                index=new_index,
                value=value
            )
            element.save()
            
            return {"success": True, "message": f"Value appended to array '{array_name}'"}
        except Exception as e:
            return {"success": False, "message": f"Error appending to array: {e}"}
    
    def insert_at_index(self, user_id, array_name, index, value):
        """Insert a value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Get current array length for validation
            count = ArrayElement.objects(user=user, array_metadata=array_metadata).count()
            
            # Validate index
            if index < 0 or index > count:
                return {"success": False, "message": f"Index {index} out of bounds"}
            
            # Shift elements to make room - start from the end
            elements_to_shift = ArrayElement.objects(
                user=user, 
                array_metadata=array_metadata,
                index__gte=index
            ).order_by('-index')
            
            for element in elements_to_shift:
                element.index += 1
                element.save()
            
            # Insert new element
            element = ArrayElement(
                user=user,
                array_metadata=array_metadata,
                index=index,
                value=value
            )
            element.save()
            
            return {"success": True, "message": f"Value inserted at index {index} in array '{array_name}'"}
        except Exception as e:
            return {"success": False, "message": f"Error inserting at index: {e}"}
    
    def update_at_index(self, user_id, array_name, index, value):
        """Update the value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Get element at index
            element = ArrayElement.objects(user=user, array_metadata=array_metadata, index=index).first()
            if not element:
                return {"success": False, "message": f"Element at index {index} not found"}
            
            # Update element
            element.value = value
            element.save()
            
            return {"success": True, "message": f"Value at index {index} updated in array '{array_name}'"}
        except Exception as e:
            return {"success": False, "message": f"Error updating at index: {e}"}
    
    def remove_at_index(self, user_id, array_name, index):
        """Remove the value at a specific index in the array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Get element at index
            element = ArrayElement.objects(user=user, array_metadata=array_metadata, index=index).first()
            if not element:
                return {"success": False, "message": f"Element at index {index} not found"}
            
            # Delete the element
            element.delete()
            
            # Shift subsequent elements
            elements_to_shift = ArrayElement.objects(
                user=user, 
                array_metadata=array_metadata,
                index__gt=index
            ).order_by('index')
            
            for element in elements_to_shift:
                element.index -= 1
                element.save()
            
            return {"success": True, "message": f"Value at index {index} removed from array '{array_name}'"}
        except Exception as e:
            return {"success": False, "message": f"Error removing at index: {e}"}
    
    def search_in_array(self, user_id, array_name, value):
        """Search for a value in the array and return its index(es)."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Find elements with the given value
            elements = ArrayElement.objects(user=user, array_metadata=array_metadata, value=value).only('index')
            
            indices = [element.index for element in elements]
            
            return {"success": True, "indices": indices}
        except Exception as e:
            return {"success": False, "message": f"Error searching in array: {e}"}
    
    def slice_array(self, user_id, array_name, start, end=None):
        """Get a slice of the array."""
        try:
            # Get the full array first
            result = self.get_array(user_id, array_name)
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
    
    def delete_array(self, user_id, array_name):
        """Delete an entire array."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get array metadata
            array_metadata = ArrayMetadata.objects(user=user, name=array_name).first()
            if not array_metadata:
                return {"success": False, "message": f"Array '{array_name}' not found"}
            
            # Count elements for reporting
            element_count = ArrayElement.objects(user=user, array_metadata=array_metadata).count()
            
            # Delete all array elements
            ArrayElement.objects(user=user, array_metadata=array_metadata).delete()
            
            # Delete array metadata
            array_metadata.delete()
            
            return {
                "success": True, 
                "message": f"Array '{array_name}' deleted successfully",
                "elements_deleted": element_count
            }
        except Exception as e:
            return {"success": False, "message": f"Error deleting array: {e}"}
    
    def list_arrays(self, user_id):
        """List all arrays for a user."""
        try:
            # Get user by ID
            user = User.objects(id=user_id).first()
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Get all array metadata for user
            array_metadata_list = ArrayMetadata.objects(user=user)
            
            # Get array metadata with counts
            arrays_info = []
            for array_meta in array_metadata_list:
                count = ArrayElement.objects(user=user, array_metadata=array_meta).count()
                arrays_info.append({
                    "name": array_meta.name,
                    "created_at": array_meta.created_at,
                    "element_count": count
                })
            
            return {"success": True, "arrays": arrays_info}
        except Exception as e:
            return {"success": False, "message": f"Error listing arrays: {e}"}


# Example usage
if __name__ == "__main__":
    # Initialize the MongoEngine array manager
    array_manager = MongoEngineArrayManager()
    
    # Create a test user
    user_result = array_manager.create_user("test_user", "test@example.com")
    print(user_result)
    
    if user_result["success"]:
        user_id = user_result["user_id"]
        
        # Create an array with initial elements
        array_manager.create_array(user_id, "numbers", [1, 2, 3, 4, 5])
        
        # Get the array
        result = array_manager.get_array(user_id, "numbers")
        print(f"Initial array: {result['array']}")
        
        # Append to the array
        array_manager.append_to_array(user_id, "numbers", 6)
        
        # Insert at index
        array_manager.insert_at_index(user_id, "numbers", 2, 10)
        
        # Update at index
        array_manager.update_at_index(user_id, "numbers", 0, 100)
        
        # Get the modified array
        result = array_manager.get_array(user_id, "numbers")
        print(f"Modified array: {result['array']}")
        
        # Search for a value
        search_result = array_manager.search_in_array(user_id, "numbers", 10)
        print(f"Search result: {search_result}")
        
        # Get a slice
        slice_result = array_manager.slice_array(user_id, "numbers", 1, 4)
        print(f"Slice result: {slice_result['slice']}")
        
        # List all arrays
        arrays = array_manager.list_arrays(user_id)
        print(f"User arrays: {arrays}")
        
        # Remove an element
        array_manager.remove_at_index(user_id, "numbers", 2)
        
        # Get the final array
        result = array_manager.get_array(user_id, "numbers")
        print(f"Final array: {result['array']}")
        
        # Delete the array
        array_manager.delete_array(user_id, "numbers")
    
    # Close connection
    me.disconnect()