from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import json

app = Flask(__name__)
CORS(app)

# IBM Cloud Object Storage konfigurálása
cos = ibm_boto3.client(
    's3',
    ibm_api_key_id='i4LdD__uysZhfV-WPzWvzH8kKr_gq7K7KX55DPVkZHes',
    ibm_service_instance_id='4dd2087c-b236-4cb9-9089-faa38562f64b',
    config=Config(signature_version='oauth'),
    endpoint_url='https://s3.direct.us-south.cloud-object-storage.appdomain.cloud'
)

bucket_name = 'servicenow2'  # COS bucket neve

# Segédfüggvény assignment groupok és prioritások lekérésére és tárolására
def load_and_store_options(headers):
    try:
        # Assignment groups lekérése
        response_groups = requests.get(
            'https://dev227667.service-now.com/api/now/table/sys_user_group',
            headers=headers
        )
        if response_groups.status_code == 200:
            global_assignment_groups = [{"name": group["name"], "sys_id": group["sys_id"]} for group in response_groups.json().get('result', [])]
            cos.put_object(Bucket=bucket_name, Key='global_assignment_groups', Body=json.dumps(global_assignment_groups))
            print("Assignment groups sikeresen frissítve és tárolva a COS-ban.")
        else:
            print("Assignment groups lekérése sikertelen:", response_groups.status_code, response_groups.text)

        # Priorities lekérése
        response_priorities = requests.get(
            'https://dev227667.service-now.com/api/now/table/sys_choice?sysparm_query=name=incident^element=priority',
            headers=headers
        )
        if response_priorities.status_code == 200:
            global_priorities = [{"label": priority["label"], "value": priority["value"]} for priority in response_priorities.json().get('result', [])]
            cos.put_object(Bucket=bucket_name, Key='global_priorities', Body=json.dumps(global_priorities))
            print("Priorities sikeresen frissítve és tárolva a COS-ban.")
        else:
            print("Priorities lekérése sikertelen:", response_priorities.status_code, response_priorities.text)

    except ClientError as e:
        print(f"Error storing options in COS: {e}")

# 1. Bejelentkezés és felhasználói adatok (token, caller_id) mentése a felhasználónév alapján
@app.route('/get_user_data', methods=['POST'])
def get_user_data():
    request_data = request.json
    felhasználónév = request_data.get('felhasználónév')
    jelszó = request_data.get('jelszó')

    # Token megszerzése a ServiceNow-tól
    auth_data = {
        'grant_type': 'password',
        'client_id': '45f3f2fb2ead4928ab994c64c664dfdc',
        'client_secret': 'fyHL1.@d&7',
        'username': felhasználónév,
        'password': jelszó
    }

    response = requests.post('https://dev227667.service-now.com/oauth_token.do', data=auth_data)
    if response.status_code == 200:
        access_token = response.json().get('access_token')
        
        # Egyedi token mentése a felhasználónév alapján
        cos.put_object(Bucket=bucket_name, Key=f'{felhasználónév}_user_token', Body=access_token)

        # Felhasználói sys_id lekérése a token segítségével
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        response_user = requests.get(
            f"https://dev227667.service-now.com/api/now/table/sys_user?sysparm_query=user_name={felhasználónév}",
            headers=headers
        )
        if response_user.status_code == 200:
            caller_id = response_user.json().get('result', [])[0].get("sys_id")
            
            # Egyedi sys_id mentése a felhasználónév alapján
            cos.put_object(Bucket=bucket_name, Key=f'{felhasználónév}_user_sys_id', Body=caller_id)

            # Assignment groups és priorities frissítése és tárolása
            load_and_store_options(headers)

            # Sikeres hitelesítés üzenet visszaadása
            return jsonify({"message": "Sikeres hitelesítés"}), 200
        else:
            return jsonify({"error": "Felhasználói azonosító lekérése sikertelen."}), 400
    else:
        return jsonify({"error": "Authentication failed", "details": response.text}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
