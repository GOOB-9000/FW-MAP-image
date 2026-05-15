import os
from dotenv import load_dotenv
from joserfc import jwt
from joserfc.jwk import RSAKey
import time
import requests

# Load variables from .env
load_dotenv()

# Access them using os.getenv
APP_ID = os.getenv("APP_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")


def get_installation_token():
    # 1. Read the Private Key
    with open(PRIVATE_KEY_PATH, 'rb') as f:
        private_key = f.read()

    key = RSAKey.import_key(private_key)

    # 2. Create the JWT payload
    # GitHub requires 'iat' (issued at) and 'exp' (expiration)
    now = int(time.time())
    payload = {
        'iat': now - 60,        # Issued 60s ago to account for clock drift
        'exp': now + (10 * 60), # Expires in 10 minutes
        'iss': APP_ID           # The Issuer is your App ID
    }

    # 3. Sign the JWT using Authlib
    header = {'alg': 'RS256'}
    encoded_jwt = jwt.encode(header, payload, key)

    # 4. Get the Installation ID
    # We first ask GitHub: "Where is this app installed for this user?"
    headers = {
        "Authorization": f"Bearer {encoded_jwt}",
        "Accept": "application/vnd.github+json"
    }
    install_res = requests.get(
        f"https://api.github.com/users/{REPO_OWNER}/installation", 
        headers=headers
    )
    install_res.raise_for_status()
    installation_id = install_res.json()['id']

    # 5. Get the actual Access Token (the ghs_... token)
    token_res = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers=headers
    )
    token_res.raise_for_status()
    return token_res.json()['token']

def commit_image(token, repo_path, local_image_path, message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # 1. Read the ACTUAL image file from your computer as BINARY
    with open(local_image_path, "rb") as image_file:
        binary_data = image_file.read()
        # 2. Encode the raw binary bytes to Base64
        import base64
        encoded_content = base64.b64encode(binary_data).decode('utf-8')

    # 3. Check for existing file SHA (to allow overwriting)
    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get('sha') if get_res.status_code == 200 else None

    # 4. Prepare payload
    data = {
        "message": message,
        "content": encoded_content
    }
    if sha:
        data["sha"] = sha

    # 5. Push to GitHub
    put_res = requests.put(url, headers=headers, json=data)
    return put_res.json()

# --- RUN THE TEST ---
try:
    print("🔑 Generating token via Authlib...")
    token = get_installation_token()
    
    print("🚀 Committing file...")
    result = commit_image(token, "assets/poster.webp", "poster.png", "updated poster")
    
    print(f"✅ Success! View it at: {result['content']['html_url']}")
except Exception as e:
    print(f"❌ Error: {e}")