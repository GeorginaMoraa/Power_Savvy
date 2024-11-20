from flask import Blueprint, request, jsonify
from utils.database import mongo
from bson.objectid import ObjectId
import datetime

devices_bp = Blueprint('device', __name__)

@devices_bp.route('/device', methods=['POST'])
def add_device():
    try:
        device_data = request.json
        required_fields = ["device_name", "power_rating", "status"]
        
        # Validate input
        for field in required_fields:
            if field not in device_data:
                return jsonify({"status": "error", "message": f"Missing field: {field}"}), 400
        
        # Insert device into the database
        new_device = {
            "device_name": device_data["device_name"],
            "power_rating": float(device_data["power_rating"]),
            "status": device_data["status"],
            "last_updated": datetime.datetime.now(datetime.timezone.utc)
        }
        mongo.db.devices.insert_one(new_device)
        return jsonify({"status": "success", "message": "Device added successfully"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@devices_bp.route('/device/<device_id>', methods=['PUT'])
def update_device_status(device_id):
    try:
        device_data = request.json
        if "status" not in device_data:
            return jsonify({"status": "error", "message": "Missing field: status"}), 400
        
        # Update device status in the database
        result = mongo.db.devices.update_one(
            {"_id": ObjectId(device_id)},
            {"$set": {
                "status": device_data["status"],
                "last_updated": datetime.timezone.utc()
            }}
        )
        
        if result.matched_count == 0:
            return jsonify({"status": "error", "message": "Device not found"}), 404
        
        return jsonify({"status": "success", "message": "Device status updated successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@devices_bp.route('/device/<device_id>', methods=['DELETE'])
def delete_device(device_id):
    try:
        # Delete device from the database
        result = mongo.db.devices.delete_one({"_id": ObjectId(device_id)})
        
        if result.deleted_count == 0:
            return jsonify({"status": "error", "message": "Device not found"}), 404
        
        return jsonify({"status": "success", "message": "Device deleted successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
