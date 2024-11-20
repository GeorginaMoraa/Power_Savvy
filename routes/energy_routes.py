from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.database import mongo
from bson.objectid import ObjectId

COST_PER_KWH = 0.15  # $0.15 per kWh

energy_bp = Blueprint('energy', __name__)

@energy_bp.route('/energy', methods=['POST'])
@jwt_required()
def log_energy():
    user_id = get_jwt_identity()
    data = request.get_json()
    usage_kwh = data['usage_kwh']

    mongo.db.energy_usage.insert_one({"user_id": ObjectId(user_id), "usage_kwh": usage_kwh})
    return jsonify({"msg": "Energy usage logged"}), 201

@energy_bp.route('/energy', methods=['GET'])
@jwt_required()
def get_energy():
    user_id = get_jwt_identity()
    usage = mongo.db.energy_usage.find({"user_id": ObjectId(user_id)})

    return jsonify([{"timestamp": str(doc["_id"].generation_time), "usage_kwh": doc["usage_kwh"]} for doc in usage]), 200

@energy_bp.route('/estimate_bill', methods=['POST'])
def estimate_bill():
    data = request.json
    try:
        total_energy = data.get('total_energy')  # in kWh
        if not total_energy:
            return jsonify({"error": "Total energy usage is required"}), 400

        # Calculate estimated bill
        estimated_bill = total_energy * COST_PER_KWH
        return jsonify({"total_energy": total_energy, "estimated_bill": round(estimated_bill, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
