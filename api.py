from flask import Flask, request, jsonify, session
from mongoengine import connect, Document, StringField, ListField, ReferenceField, DateTimeField, DictField, NULLIFY # type: ignore
from mongoengine.errors import DoesNotExist, ValidationError # type: ignore
from datetime import datetime
from bson import json_util
import json
from functools import wraps

app = Flask(__name__)
connect(db="planity", host="localhost", port=27017)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

class Component(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    hostEntity = StringField()
    data = DictField()
    type = StringField(required=True) 
    owner = StringField(required=True)  # Store user ID
    meta = {'collection': 'components'}

class Subject(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(Component, reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    meta = {'collection': 'subjects'}

class DataTransfer(Document):
    id = StringField(primary_key=True)
    sourceComp = ReferenceField(Component, reverse_delete_rule=NULLIFY, required=False) 
    targetSource = ReferenceField(Component, reverse_delete_rule=NULLIFY, required=True)
    data_value = DictField(null=True)
    operation = StringField(required=True)
    schedule = DateTimeField()
    details = DictField(null=True)
    owner = StringField(required=True)  # Store user ID
    meta = {'collection': 'data_transfers'}


@app.route('/components', methods=['POST'])
@login_required
def create_component():
    data = request.json
    user_id = session['user_id']
    
    component = Component(**data, owner=user_id)
    component.save()
    
    return jsonify({"message": "Component created", "id": component.id}), 201

@app.route('/subjects', methods=['POST'])
@login_required
def create_subject():
    data = request.json
    user_id = session['user_id']
    
    component_ids = data.pop('components', [])
    components = Component.objects.filter(id__in=component_ids, owner=user_id)  # Restrict to user's components
    
    subject = Subject(**data, components=components, owner=user_id)
    subject.save()
    
    return jsonify({"message": "Subject created", "id": subject.id}), 201

@app.route('/data_transfers', methods=['POST'])
@login_required
def create_data_transfer():
    try:
        data = request.json
        user_id = session['user_id']
        
        data_id = data.get('id', None)
        source_comp = Component.objects.get(id=data['sourceComp'], owner=user_id) if 'sourceComp' in data else None
        target_source = Component.objects.get(id=data['targetSource'], owner=user_id)
        
        schedule = None
        if 'schedule' in data and data['schedule']:
            try:
                schedule = datetime.fromisoformat(data['schedule'].replace("Z", "+00:00"))
            except ValueError:
                return jsonify({"error": "Invalid date format for 'schedule'"}), 400
        
        data_transfer = DataTransfer(
            id=data_id,
            sourceComp=source_comp,
            targetSource=target_source,
            data_value=data.get('data_value'),
            operation=data['operation'],
            schedule=schedule,
            details=data.get('details'),
            owner=user_id
        )
        data_transfer.save()
        
        return jsonify({"message": "Data transfer created", "id": str(data_transfer.id)}), 201

    except DoesNotExist as e:
        return jsonify({"error": f"Component not found: {str(e)}"}), 404
    except ValidationError as e:
        return jsonify({"error": f"Validation error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/subjects/<subject_id>', methods=['GET'])
@login_required
def get_subject(subject_id):
    try:
        user_id = session['user_id']
        subject = Subject.objects.get(id=subject_id, owner=user_id)
        return jsonify(subject.to_mongo().to_dict()), 200
    except DoesNotExist:
        return jsonify({"error": "Subject not found"}), 404

@app.route('/components/<component_id>', methods=['GET'])
@login_required
def get_component_by_id(component_id):
    try:
        user_id = session['user_id']
        component = Component.objects.get(id=component_id, owner=user_id)
        return jsonify(component.to_mongo().to_dict()), 200
    except Component.DoesNotExist:
        return jsonify({"error": "Component not found"}), 404

@app.route('/data_transfers/<transfer_id>', methods=['GET'])
@login_required
def get_data_transfer(transfer_id):
    try:
        user_id = session['user_id']
        data_transfer = DataTransfer.objects.get(id=transfer_id, owner=user_id)
        return jsonify(data_transfer.to_mongo().to_dict()), 200
    except DataTransfer.DoesNotExist:
        return jsonify({"error": "Data transfer not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/components', methods=['GET'])
@login_required
def get_all_components():
    user_id = session['user_id']
    components = Component.objects(owner=user_id)
    return json.dumps([comp.to_mongo() for comp in components], default=json_util.default), 200

@app.route('/subjects', methods=['GET'])
@login_required
def get_all_subjects():
    user_id = session['user_id']
    subjects = Subject.objects(owner=user_id)
    return json.dumps([subj.to_mongo() for subj in subjects], default=json_util.default), 200

@app.route('/data_transfers', methods=['GET'])
@login_required
def get_all_data_transfers():
    user_id = session['user_id']
    data_transfers = DataTransfer.objects(owner=user_id)
    return json.dumps([dt.to_mongo() for dt in data_transfers], default=json_util.default), 200

@app.route('/components/<component_id>', methods=['DELETE'])
@login_required
def delete_component(component_id):
    user_id = session['user_id']
    component = Component.objects(id=component_id, owner=user_id).first()

    if not component:
        return jsonify({"error": "Component not found or unauthorized"}), 403
    
    component.delete()
    return jsonify({"message": "Component deleted successfully"}), 200

@app.route('/subjects/<subject_id>', methods=['DELETE'])
@login_required
def delete_subject(subject_id):
    user_id = session['user_id']
    subject = Subject.objects(id=subject_id, owner=user_id).first()

    if not subject:
        return jsonify({"error": "Subject not found or unauthorized"}), 403
    
    subject.delete()
    return jsonify({"message": "Subject deleted successfully"}), 200

@app.route('/data_transfers/<transfer_id>', methods=['DELETE'])
@login_required
def delete_data_transfer(transfer_id):
    user_id = session['user_id']
    data_transfer = DataTransfer.objects(id=transfer_id, owner=user_id).first()

    if not data_transfer:
        return jsonify({"error": "Data transfer not found or unauthorized"}), 403
    
    data_transfer.delete()
    return jsonify({"message": "Data transfer deleted successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1", port=5000)
