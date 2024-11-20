from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.database import mongo
from bson.objectid import ObjectId
import datetime
import pytz

report_bp = Blueprint('report', __name__)

@report_bp.route('/report', methods=['GET'])
@jwt_required()
def get_report():
    user_id = get_jwt_identity()
    total_usage = sum(doc["usage_kwh"] for doc in mongo.db.energy_usage.find({"user_id": ObjectId(user_id)}))

    return jsonify({"total_usage": total_usage, "unit": "kWh"}), 200


def calculate_current_usage():
    # Fetch all devices that are ON
    devices = mongo.db.devices.find({"status": "on"})
    
    total_usage = 0.0
    current_time = datetime.datetime.now(datetime.timezone.utc)  # Timezone-aware datetime
    
    for device in devices:
        power_rating = device["power_rating"]  # kWh
        last_updated = device.get("last_updated", current_time)
        
        # Ensure last_updated is timezone-aware
        if last_updated.tzinfo is None:  # If it's naive (no timezone info)
            last_updated = last_updated.replace(tzinfo=datetime.timezone.utc)  # Make it aware

        # Calculate the elapsed time in hours
        elapsed_time = (current_time - last_updated).total_seconds() / 3600  # Convert to hours
        
        # Calculate usage since the last update
        usage = power_rating * elapsed_time
        total_usage += usage
        
        # Update the last_updated time for the device
        mongo.db.devices.update_one(
            {"_id": device["_id"]},
            {"$set": {"last_updated": current_time}}
        )
    
    return round(total_usage, 2)

def update_real_time_data():
    current_usage = calculate_current_usage()
    mongo.db.consumption.update_one(
        {"type": "realtime"},  # Identify real-time data entry
        {
            "$set": {
                "current_usage": current_usage,
                "timestamp": datetime.datetime.now(datetime.timezone.utc)  # Fixed timezone-aware datetime
            }
        },
        upsert=True  # Create the document if it doesn't exist
    )

@report_bp.route('/update_realtime', methods=['POST'])
def update_realtime_data_route():
    update_real_time_data()
    return jsonify({"status": "success", "message": "Real-time data updated."}), 200


@report_bp.route('/consumption/realtime', methods=['GET'])
def get_realtime_data():
    data = mongo.db.consumption.find_one({"type": "realtime"})
    if data:
        return jsonify({
            "status": "success",
            "data": {
                "current_usage": data["current_usage"],
                "timestamp": data["timestamp"]
            }
        })
    return jsonify({"status": "error", "message": "No real-time data available"}), 404
