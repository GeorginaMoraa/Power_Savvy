from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.database import mongo
from bson.objectid import ObjectId
import datetime

report_bp = Blueprint('report', __name__)

@report_bp.route('/report', methods=['GET'])
@jwt_required()
def get_report():
    """Fetch total usage for the authenticated user."""
    user_id = get_jwt_identity()
    total_usage = sum(doc["usage_kwh"] for doc in mongo.db.energy_usage.find({"user_id": ObjectId(user_id)}))

    return jsonify({"total_usage": total_usage, "unit": "kWh"}), 200


def calculate_current_usage():
    """
    Calculate the current usage of all ON devices based on their power rating and last_updated field.
    """
    # Fetch all devices that are ON
    devices = mongo.db.devices.find({"status": "ON"})
    
    total_usage = 0.01
    current_time = datetime.datetime.now(datetime.timezone.utc)  # Timezone-aware datetime

    for device in devices:
        power_rating = device.get("power_rating")  # Power consumption in kWh
        last_updated = device.get("last_updated")  # Last time the device was updated

        if not power_rating or not last_updated:
            # Skip devices without a valid power_rating or last_updated
            continue

        # Ensure 'last_updated' is timezone-aware
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=datetime.timezone.utc)

        # Calculate elapsed time in hours
        elapsed_time = (current_time - last_updated).total_seconds() / 3600  # Convert seconds to hours

        # Calculate usage since the device was last updated
        usage = power_rating * elapsed_time
        total_usage += usage

        # Update the last_updated time for the device to current time
        mongo.db.devices.update_one(
            {"_id": device["_id"]},
            {"$set": {"last_updated": current_time}}
        )

    return round(total_usage, 2)



def update_real_time_data():
    """
    Update the real-time data entry with the current usage value.
    """
    current_usage = calculate_current_usage()
    mongo.db.consumption.update_one(
        {"type": "realtime"},  # Identify the real-time data document
        {
            "$set": {
                "current_usage": current_usage,
                "timestamp": datetime.datetime.now(datetime.timezone.utc)  # Record the update time
            }
        },
        upsert=True  # Create the document if it does not exist
    )


@report_bp.route('/update_realtime', methods=['POST'])
def update_realtime_data_route():
    """
    API route to trigger real-time data update.
    """
    update_real_time_data()
    return jsonify({"status": "success", "message": "Real-time data updated."}), 200


@report_bp.route('/consumption/realtime', methods=['GET'])
def get_realtime_data():
    """
    API route to fetch real-time consumption data.
    """
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


# Utility function to backfill 'created_at' for devices without it
def backfill_created_at():
    """
    Utility function to ensure all devices have a 'created_at' field.
    """
    default_time = datetime.datetime.now(datetime.timezone.utc)
    mongo.db.devices.update_many(
        {"created_at": {"$exists": False}},
        {"$set": {"created_at": default_time}}
    )
