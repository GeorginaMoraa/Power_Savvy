from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from utils.database import mongo
from utils.helpers import hash_password, verify_password
from bson.objectid import ObjectId

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data['username']
    email = data['email']
    password = hash_password(data['password'])

    user = mongo.db.users.find_one({"email": email})
    if user:
        return jsonify({"msg": "User already exists"}), 400

    mongo.db.users.insert_one({"username": username, "email": email, "password": password})
    return jsonify({"msg": "User registered successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']

    user = mongo.db.users.find_one({"email": email})
    if not user or not verify_password(password, user['password']):
        return jsonify({"msg": "Invalid credentials"}), 401

    token = create_access_token(identity=str(user['_id']))
    return jsonify({"access_token": token}), 200
