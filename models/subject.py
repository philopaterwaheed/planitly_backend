from .component import Component_db, Component, PREDEFINED_COMPONENT_TYPES
from .widget import Widget_db, Widget
from .category import Category_db
import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, ListField, BooleanField, NULLIFY, DateTimeField
from mongoengine.errors import DoesNotExist, ValidationError
from .templets import TEMPLATES, CustomTemplate_db
from .arrayItem import Arrays
import datetime


# use the Subject_db class to interact with the database directly without the helper
class Subject_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(Component_db, reverse_delete_rule=NULLIFY))
    widgets = ListField(ReferenceField(Widget_db, reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    template = StringField(required=False)
    is_deletable = BooleanField(default=True)
    category = StringField(required=False)  # Store category name as a string
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    times_visited = DictField(default=lambda: {'count': 0, 'last_decay': datetime.datetime.utcnow()})  # Add visit tracking with decay
    last_visited = DateTimeField()  # Track when it was last visited

    meta = {
        'collection': 'subjects',
        'indexes': [
            {'fields': ['name', 'owner'], 'unique': True},
            {'fields': ['owner', '-times_visited.count']},  # Index for efficient sorting by visit count
        ]
    }


# Subject class helper to interact with the database
class Subject:
    def __init__(self, name, owner, template="", components=None, widgets=None, id=None, is_deletable=True, category=None, created_at=None, times_visited=None, last_visited=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.owner = owner
        self.template = template
        self.components = components or []
        self.widgets = widgets or []
        self.is_deletable = is_deletable
        self.category = category or "Uncategorized"
        self.created_at = created_at or datetime.datetime.utcnow()
        self.times_visited = times_visited or {'count': 0, 'last_decay': datetime.datetime.utcnow()}
        self.last_visited = last_visited

    def increment_visit_count(self):
        """
        Increment visit count with decay mechanism to prevent overflow.
        Applies exponential decay based on time elapsed since last decay.
        """
        now = datetime.datetime.utcnow()
        
        # Initialize if needed
        if not isinstance(self.times_visited, dict):
            self.times_visited = {'count': 0, 'last_decay': now}
        
        if 'last_decay' not in self.times_visited:
            self.times_visited['last_decay'] = now
        
        last_decay = self.times_visited['last_decay']
        if not isinstance(last_decay, datetime.datetime):
            last_decay = datetime.datetime.utcnow()
            self.times_visited['last_decay'] = last_decay
        
        # Calculate days since last decay
        days_since_decay = (now - last_decay).days
        
        # Apply decay if more than 7 days have passed
        if days_since_decay >= 7:
            # Exponential decay: reduce count by 10% per week
            decay_factor = 0.9 ** (days_since_decay // 7)
            self.times_visited['count'] = int(self.times_visited['count'] * decay_factor)
            self.times_visited['last_decay'] = now
        
        # Increment visit count (with maximum cap of 10000)
        self.times_visited['count'] = min(self.times_visited['count'] + 1, 10000)
        self.last_visited = now

    async def add_component(self, component_name, component_type, data=None, is_deletable=True):
        if component_type in PREDEFINED_COMPONENT_TYPES:
            component = Component(name=component_name,
                                  host_subject=self.id,
                                  owner=self.owner,
                                  comp_type=component_type,
                                  data=data,
                                  is_deletable=is_deletable)
            component.host_subject = self.id
            
            component.save_to_db()
            # add a reference to the component in the subject if saved
            self.components.append(component.id)
            
            # Handle Array_type and Array_generic components
            if component.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]:
                array_metadata_result = Arrays.create_array(
                    user_id=component.owner,
                    host_id=component.id,
                    array_name=component.name,
                    host_type="component",
                    initial_elements=[]
                )
                if not array_metadata_result["success"]:
                    raise Exception(array_metadata_result["message"])
            self.save_to_db()
        else:
            print(f"Component type '{component_type}' is not defined.")
        return component

    async def add_widget(self, widget_name, widget_type, data=None, reference_component=None, is_deletable=True):
        try:
            # Validate widget type and data
            validated_data = Widget.validate_widget_type(
                widget_type, reference_component, data)

            widget = Widget(
                name=widget_name,
                widget_type=widget_type,
                host_subject=self.id,
                data=validated_data,
                reference_component=reference_component,
                owner=self.owner,
                is_deletable=is_deletable
            )

            widget.save_to_db()
            
            # Create associated arrays for widget types that need them
            await self._create_widget_arrays(widget, widget_type)
            
            # Add reference to the widget in the subject
            self.widgets.append(widget.id)
            self.save_to_db()
            return widget
        except ValidationError as e:
            print(f"Widget validation error: {e}")
            return None

    async def _create_widget_arrays(self, widget, widget_type):
        """Create array components for widgets that need them."""
        from .arrayItem import Arrays
        
        if widget_type == "table":
            # Create columns array
            columns_result = Arrays.create_array(
                user_id=self.owner,
                host_id=widget.id,
                array_name=f"{widget.name}_columns",
                host_type="widget",
                initial_elements=[]
            )
            if not columns_result["success"]:
                raise Exception(f"Failed to create columns array: {columns_result['message']}")
            
            # Create rows array
            rows_result = Arrays.create_array(
                user_id=self.owner,
                host_id=widget.id,
                array_name=f"{widget.name}_rows",
                host_type="widget",
                initial_elements=[]
            )
            if not rows_result["success"]:
                raise Exception(f"Failed to create rows array: {rows_result['message']}")
                
        elif widget_type == "calendar":
            # Create events array
            events_result = Arrays.create_array(
                user_id=self.owner,
                host_id=widget.id,
                array_name=f"{widget.name}_events",
                host_type="widget",
                initial_elements=[]
            )
            if not events_result["success"]:
                raise Exception(f"Failed to create events array: {events_result['message']}")
                
        elif widget_type == "note":
            # Create tags array
            tags_result = Arrays.create_array(
                user_id=self.owner,
                host_id=widget.id,
                array_name=f"{widget.name}_tags",
                host_type="widget",
                initial_elements=[]
            )
            if not tags_result["success"]:
                raise Exception(f"Failed to create tags array: {tags_result['message']}")
                

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def get_widget(self, widget_id):
        try:
            return Widget.load_from_db(widget_id)
        except DoesNotExist:
            print(f"Widget with ID {widget_id} not found.")
            return None

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "template": self.template,
            "category": self.category,  # Return category name
            "components": self.components,
            "widgets": self.widgets,
            "is_deletable": self.is_deletable,
            "owner": self.owner,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "times_visited": self.times_visited.get('count', 0) if isinstance(self.times_visited, dict) else 0,
            "last_visited": self.last_visited.isoformat() if self.last_visited else None,
        }

    async def apply_template(self, template):
        """
        Apply a template to the subject and set its category.
        Supports both built-in and custom templates.
        """
        # First, check built-in templates
        if template in TEMPLATES:
            self.template = template
            self.category = TEMPLATES[template].get("category", "Uncategorized")
            for comp in TEMPLATES[template]["components"]:
                is_comp_deletable = comp.get("is_deletable", True)
                await self.add_component(comp["name"], comp["type"], comp["data"], is_deletable=is_comp_deletable)
            # Add widgets from template if they exist
            if "widgets" in TEMPLATES[template]:
                for widget in TEMPLATES[template]["widgets"]:
                    reference_component = widget.get("reference_component", None)
                    await self.add_widget(
                        widget["name"],
                        widget["type"],
                        widget.get("data", {}),
                        reference_component,
                        widget.get("is_deletable", True),
                    )
        else:
            # Try to find a custom template by id
            custom_template = CustomTemplate_db.objects(id=template).first()
            if not custom_template:
                raise ValueError(f"Template '{template}' does not exist.")
            self.template = str(custom_template.id)
            self.category = custom_template.category or "Uncategorized"
            components = custom_template.data.get("components", [])
            for comp in components:
                is_comp_deletable = comp.get("is_deletable", True)
                await self.add_component(comp["name"], comp["type"], comp["data"], is_deletable=is_comp_deletable)
            widgets = custom_template.data.get("widgets", [])
            for widget in widgets:
                reference_component = widget.get("reference_component", None)
                await self.add_widget(
                    widget["name"],
                    widget["type"],
                    widget.get("data", {}),
                    reference_component,
                    widget.get("is_deletable", True),
                )

    async def get_full_data(self):
        """Fetch all data inside the subject, including its components and widgets with their arrays."""
        # Fetch components
        try:
            components = [
                Component.load_from_db(component_id).get_component()
                for component_id in (self.components or [])
            ]
        except Exception as e:
            raise Exception(f"Error loading components: {str(e)}")

        # Fetch widgets with their arrays
        try:
            widgets = []
            widget_docs = Widget_db.objects(host_subject=self.id)
            
            for widget_doc in widget_docs:
                widget_data = widget_doc.to_mongo().to_dict()
                
                # Add arrays based on widget type
                if widget_doc.type == "table":
                    # Get columns array
                    columns_result = Arrays.get_array(
                        user_id=self.owner,
                        host_id=widget_doc.id,
                        host_type="widget",
                        array_name=f"{widget_doc.name}_columns"
                    )
                    if columns_result["success"]:
                        widget_data["columns"] = columns_result["data"]
                    
                    # Get rows array
                    rows_result = Arrays.get_array(
                        user_id=self.owner,
                        host_id=widget_doc.id,
                        host_type="widget",
                        array_name=f"{widget_doc.name}_rows"
                    )
                    if rows_result["success"]:
                        widget_data["rows"] = rows_result["data"]
                        
                elif widget_doc.type == "calendar":
                    # Get events array
                    events_result = Arrays.get_array(
                        user_id=self.owner,
                        host_id=widget_doc.id,
                        host_type="widget",
                        array_name=f"{widget_doc.name}_events"
                    )
                    if events_result["success"]:
                        widget_data["events"] = events_result["data"]
                        
                elif widget_doc.type == "note":
                    # Get tags array
                    tags_result = Arrays.get_array(
                        user_id=self.owner,
                        host_id=widget_doc.id,
                        host_type="widget",
                        array_name=f"{widget_doc.name}_tags"
                    )
                    if tags_result["success"]:
                        widget_data["tags"] = tags_result["data"]
                
                # For other widget types, check if they have any arrays
                # This handles custom arrays that might be created for widgets
                try:
                    from .arrayItem import ArrayMetadata
                    widget_arrays = ArrayMetadata.objects(
                        user=self.owner,
                        host_widget=widget_doc.id
                    )
                    
                    if widget_arrays:
                        widget_data["arrays"] = []
                        for array_meta in widget_arrays:
                            array_result = Arrays.get_array_by_id(
                                user_id=self.owner,
                                array_id=str(array_meta.id)
                            )
                            if array_result["success"]:
                                widget_data["arrays"].append({
                                    "id": str(array_meta.id),
                                    "name": array_meta.name,
                                    "data": array_result["data"]
                            })
                except Exception as array_error:
                    # Continue if array loading fails
                    print(f"Warning: Could not load arrays for widget {widget_doc.id}: {array_error}")
                
                widgets.append(widget_data)
                
        except Exception as e:
            raise Exception(f"Error loading widgets: {str(e)}")

        # Combine subject, components, and widgets data
        return {
            "subject": self.to_json(),
            "components": components,
            "widgets": widgets,
        }

    @staticmethod
    def from_json(data):
        subject = Subject(name=data["name"],
                          owner=data["owner"],
                          template=data["template"],
                          id=data["id"],
                          is_deletable=data.get("is_deletable", True),
                          category=data.get("category", "Uncategorized"),
                          created_at=data.get("created_at"),  # <-- Add this line
                          ) 
        for comp_id in data["components"]:
            subject.components.append(comp_id)
        for widget_id in data.get("widgets", []):
            subject.widgets.append(widget_id)
        return subject

    # save the subject to the database
    def save_to_db(self):
        subject_db = Subject_db(
            id=self.id,
            name=self.name,
            owner=self.owner,
            template=self.template,
            components=self.components,
            widgets=self.widgets,
            is_deletable=self.is_deletable,
            category=self.category,
            created_at=self.created_at,
            times_visited=self.times_visited,
            last_visited=self.last_visited,
        )
        subject_db.save()

    @staticmethod
    def load_from_db(id):
        try:
            subject_db = Subject_db.objects(id=id).first()
            if subject_db:
                subject = Subject(
                    id=subject_db.id,
                    name=subject_db.name,
                    owner=subject_db.owner,
                    template=subject_db.template,
                    components=[component.id for component in subject_db.components],
                    widgets=[widget.id for widget in subject_db.widgets],
                    is_deletable=subject_db.is_deletable,
                    category=subject_db.category,
                    created_at=subject_db.created_at,
                    times_visited=subject_db.times_visited,
                    last_visited=subject_db.last_visited,
                )
                return subject
            else:
                print(f"Subject with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Subject with ID {id} does not exist.")
            return None

    @staticmethod
    def from_db(subject_db):
        if not subject_db:
            return None
        return Subject(
            id=subject_db.id,
            name=subject_db.name,
            owner=subject_db.owner,
            template=subject_db.template,
            components=[component.id for component in subject_db.components],
            widgets=[widget.id for widget in subject_db.widgets],
            is_deletable=subject_db.is_deletable,
            category=subject_db.category,
            created_at=subject_db.created_at,
            times_visited=subject_db.times_visited,
            last_visited=subject_db.last_visited,
        )
