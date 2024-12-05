from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    get_jwt_identity,
)
from utils.database import mongo
from bson.objectid import ObjectId
import datetime

device_bp = Blueprint('device', __name__)

# Add a device tied to the logged-in user
@device_bp.route('/devices', methods=['POST'])
@jwt_required()
def add_device():
    current_user = get_jwt_identity()
    data = request.json

    # Validate input
    if not data.get('name') or not data.get('watts') or not data.get('roomId') or not data.get('status'):
        return jsonify({"error": "Device name, watts, room ID, and status are required"}), 400

    if data['status'] not in ['on', 'off']:
        return jsonify({"error": "Status must be either 'on' or 'off'"}), 400

    try:
        # Convert roomId to ObjectId (since roomId is passed as a string)
        room_id = ObjectId(data['roomId'])  # Convert string ID to ObjectId

        # Insert device into MongoDB with status
        created_at = datetime.datetime.now(datetime.timezone.utc)
        device = {
            "name": data['name'],
            "watts": data['watts'],
            "room_id": room_id,  # Store as ObjectId in MongoDB
            "status": data['status'],  # Store the status of the device (on/off)
            "user_id": current_user,  # Associate device with the logged-in user
            "created_at": created_at
        }
        result = mongo.db.devices.insert_one(device)

        # Create an initial log entry
        initial_log = {
            "device_id": result.inserted_id,  # Use the newly created device ID
            "status": data['status'],  # Use the initial status
            "timestamp": created_at  # Use the device creation time
        }
        mongo.db.device_logs.insert_one(initial_log)

        # Return the created device details with room ID and status
        device['_id'] = str(result.inserted_id)  # Ensure the _id is a string
        device['room_id'] = str(device['room_id'])  # Ensure the room_id is a string
        return jsonify({"message": "Device created successfully", "device": device}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get all devices for the logged-in user
@device_bp.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    current_user = get_jwt_identity()  # Get the logged-in user's ID

    try:
        devices = []
        # Fetch devices tied to the logged-in user
        for device in mongo.db.devices.find({"user_id": current_user}):
            # Ensure _id is serialized to a string
            device['_id'] = str(device['_id'])  # Convert ObjectId to string
            if 'room_id' in device:  # If there's a room_id field
                device['room_id'] = str(device['room_id'])  # Convert room_id ObjectId to string
            devices.append(device)

        return jsonify(devices), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get a single device by ID for the logged-in user
@device_bp.route('/devices/<device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    current_user = get_jwt_identity()

    try:
        device = mongo.db.devices.find_one({
            "_id": ObjectId(device_id),
            "user_id": current_user  # Ensure the device belongs to the current user
        })

        if not device:
            return jsonify({"error": "Device not found"}), 404

        device['_id'] = str(device['_id'])
        device['roomId'] = str(device['roomId'])  # Convert room ID to string for frontend usage
        return jsonify(device), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Get all devices associated with a specific room for the logged-in user
@device_bp.route('/devices/room', methods=['GET'])
@jwt_required()
def get_devices_by_room():
    current_user = get_jwt_identity()  # Get the logged-in user's ID
    room_id = request.args.get('roomId')

    # Validate input
    if not room_id:
        return jsonify({"error": "roomId is required"}), 400

    try:
        # Convert roomId to ObjectId (since roomId is passed as a string)
        room_id_object = ObjectId(room_id)

        devices = []
        # Fetch devices tied to the logged-in user and the specified room
        for device in mongo.db.devices.find({
            "user_id": current_user,
            "room_id": room_id_object  # Ensure the device belongs to the room
        }):
            device['_id'] = str(device['_id'])  # Convert ObjectId to string
            device['room_id'] = str(device['room_id'])  # Convert room_id ObjectId to string
            devices.append(device)

        return jsonify(devices), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@device_bp.route('/devices/status', methods=['PUT'])
@jwt_required()
def update_device_status():
    data = request.get_json()
    device_id = data.get('device_id')
    new_status = data.get('status')

    if not device_id or not new_status:
        return jsonify({"msg": "Device ID and status are required"}), 400

    if new_status not in ['on', 'off']:
        return jsonify({"error": "Status must be either 'on' or 'off'"}), 400

    try:
        # Update the device status
        result = mongo.db.devices.update_one(
            {"_id": ObjectId(device_id)},
            {"$set": {"status": new_status, "status_changed_at": datetime.datetime.now(datetime.timezone.utc)}}
        )

        if result.matched_count > 0:
            # Log the status change
            log_entry = {
                "device_id": ObjectId(device_id),
                "status": new_status,
                "timestamp": datetime.datetime.now(datetime.timezone.utc)
            }
            mongo.db.device_logs.insert_one(log_entry)

            return jsonify({"msg": "Device status updated successfully"}), 200
        else:
            return jsonify({"msg": "Device not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    

# Delete a device by ID
@device_bp.route('/devices/<device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    current_user = get_jwt_identity()

    try:
        # Attempt to delete the device by its ID and ensure it's the logged-in user's device
        result = mongo.db.devices.delete_one({
            "_id": ObjectId(device_id),
            "user_id": current_user  # Only allow the user to delete their own device
        })

        if result.deleted_count > 0:
            return jsonify({"msg": "Device deleted successfully"}), 200
        else:
            return jsonify({"error": "Device not found or not authorized to delete"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Edit a device by ID
@device_bp.route('/devices/<device_id>', methods=['PUT'])
@jwt_required()
def edit_device(device_id):
    current_user = get_jwt_identity()
    data = request.json

    # Validate input
    if not data.get('name') and not data.get('watts') and not data.get('roomId') and not data.get('status'):
        return jsonify({"error": "At least one field (name, watts, room ID, status) must be provided for update"}), 400

    # Convert roomId to ObjectId if provided
    if data.get('roomId'):
        try:
            room_id = ObjectId(data['roomId'])  # Convert string ID to ObjectId
        except Exception as e:
            return jsonify({"error": "Invalid room ID format"}), 400

    try:
        # Prepare the update data
        update_data = {}
        if data.get('name'):
            update_data["name"] = data['name']
        if data.get('watts'):
            update_data["watts"] = data['watts']
        if data.get('roomId'):
            update_data["room_id"] = room_id  # Update room_id if provided
        if data.get('status'):
            if data['status'] not in ['on', 'off']:
                return jsonify({"error": "Status must be either 'on' or 'off'"}), 400
            update_data["status"] = data['status']

        # Update the device in the database
        result = mongo.db.devices.update_one(
            {"_id": ObjectId(device_id), "user_id": current_user},
            {"$set": update_data}
        )

        if result.matched_count > 0:
            # Fetch the updated device data
            updated_device = mongo.db.devices.find_one({"_id": ObjectId(device_id)})
            updated_device['_id'] = str(updated_device['_id'])
            updated_device['room_id'] = str(updated_device['room_id'])  # Ensure room_id is a string
            return jsonify({"msg": "Device updated successfully", "device": updated_device}), 200
        else:
            return jsonify({"error": "Device not found or not authorized to edit"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@device_bp.route('/devices/<device_id>/on-duration-summary', methods=['GET'])
@jwt_required()
def get_device_on_duration_summary(device_id):
    current_user = get_jwt_identity()

    try:
        # Fetch the device to ensure it belongs to the current user
        device = mongo.db.devices.find_one({"_id": ObjectId(device_id), "user_id": current_user})
        if not device:
            return jsonify({"error": "Device not found"}), 404

        # Fetch all logs for the device
        logs = list(mongo.db.device_logs.find({"device_id": ObjectId(device_id)}).sort("timestamp", 1))

        # Calculate durations
        daily_duration = datetime.timedelta(0)
        weekly_duration = datetime.timedelta(0)
        monthly_duration = datetime.timedelta(0)

        now = datetime.datetime.now(datetime.timezone.utc)

        # Determine the start of the current day (00:00)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Determine the start of the current week (Monday, 00:00)
        start_of_week = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

        # Determine the start of the current month
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Track previous log's status and timestamp
        previous_status = None
        previous_timestamp = None

        for log in logs:
            log_timestamp = log["timestamp"]

            # Convert to timezone-aware datetime if naive
            if log_timestamp.tzinfo is None:
                log_timestamp = log_timestamp.replace(tzinfo=datetime.timezone.utc)

            log_status = log["status"]

            # If the previous status was 'on', calculate the duration
            if previous_status == "on":
                duration = log_timestamp - previous_timestamp
                if log_timestamp >= start_of_day:  # Check if the duration falls within the current day
                    daily_duration += duration
                if log_timestamp >= start_of_week:  # Check if the duration falls within the current week
                    weekly_duration += duration
                if log_timestamp >= start_of_month:  # Check if the duration falls within the current month
                    monthly_duration += duration

            # Update previous status and timestamp
            previous_status = log_status
            previous_timestamp = log_timestamp

        # Account for current "on" duration if the device is still on
        if previous_status == "on":
            duration = now - previous_timestamp
            if now >= start_of_day:
                daily_duration += duration
            if now >= start_of_week:
                weekly_duration += duration
            if now >= start_of_month:
                monthly_duration += duration

        # Format durations to HH:MM:SS
        def format_duration(duration):
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        # Get the daily tag in YYYY-MM-DD format
        daily_tag = start_of_day.strftime('%Y-%m-%d')

        return jsonify({
            "device_id": device_id,
            "daily_tag": daily_tag,  # Add the day being measured
            "daily_on_duration": format_duration(daily_duration),
            "weekly_on_duration": format_duration(weekly_duration),
            "monthly_on_duration": format_duration(monthly_duration)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
