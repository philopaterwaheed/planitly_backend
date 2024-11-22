from flask import Flask, request, jsonify
from mongoengine import connect, Document, StringField, ListField, ReferenceField, DateTimeField, DictField, NULLIFY
from mongoengine.errors import DoesNotExist, ValidationError
from datetime import datetime
from bson import json_util
import json

app = Flask(__name__)
connect(db="planity", host="localhost", port=27017)


class Component(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    hostEntity = StringField()
    data = DictField()
    type = StringField(required=True)    
    meta = {'collection': 'components'}

class Subject(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(Component, reverse_delete_rule=NULLIFY))
    meta = {'collection': 'subjects'}


class DataTransfer(Document):
    id = StringField(primary_key=True)
    sourceComp = ReferenceField(Component, reverse_delete_rule=NULLIFY, required=False) 
    targetSource = ReferenceField(Component, reverse_delete_rule=NULLIFY, required=True)
    data_value = DictField(null=True)
    operation = StringField(required=True)
    schedule = DateTimeField()
    details = DictField(null=True)
    meta = {'collection': 'data_transfers'}

@app.route('/components', methods=['POST'])
def create_component():
    data = request.json
    component = Component(**data)
    component.save()
    return jsonify({"message": "Component created", "id": component.id}), 201

@app.route('/subjects', methods=['POST'])
def create_subject():
    data = request.json
    component_ids = data.pop('components', [])
    components = Component.objects.filter(id__in=component_ids)
    subject = Subject(**data, components=components)
    subject.save()
    return jsonify({"message": "Subject created", "id": subject.id}), 201


@app.route('/data_transfers', methods=['POST'])
def create_data_transfer():
    try:
        data = request.json
        data_id = data.get('id', None)
        source_comp = Component.objects.get(id=data['sourceComp']) if 'sourceComp' in data else None
        target_source = Component.objects.get(id=data['targetSource'])
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
            details=data.get('details')
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
def get_subject(subject_id):
    try:
        subject = Subject.objects.get(id=subject_id)
        return jsonify(subject.to_mongo().to_dict()), 200
    except DoesNotExist:
        return jsonify({"error": "Subject not found"}), 404

@app.route('/components/<component_id>', methods=['GET'])
def get_component_by_id(component_id):
    try:
        component = Component.objects.get(id=component_id)
        return jsonify(component.to_mongo().to_dict()), 200
    except Component.DoesNotExist:
        return jsonify({"error": "Component not found"}), 404

@app.route('/data_transfers/<transfer_id>', methods=['GET'])
def get_data_transfer(transfer_id):
    try:
        data_transfer = DataTransfer.objects.get(id=transfer_id)
        return jsonify(data_transfer.to_mongo().to_dict()), 200
    except DataTransfer.DoesNotExist:
        return jsonify({"error": "Data transfer not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/components', methods=['GET'])
def get_all_components():
    components = Component.objects()
    return json.dumps([comp.to_mongo() for comp in components], default=json_util.default), 200

@app.route('/subjects', methods=['GET'])
def get_all_subjects():
    subjects = Subject.objects()
    return json.dumps([subj.to_mongo() for subj in subjects], default=json_util.default), 200

@app.route('/data_transfers', methods=['GET'])
def get_all_data_transfers():
    data_transfers = DataTransfer.objects()
    return json.dumps([dt.to_mongo() for dt in data_transfers], default=json_util.default), 200


if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1", port=5000)

