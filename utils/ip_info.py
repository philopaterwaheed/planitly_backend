import requests
from consts import env_variables

token = env_variables.get("IPI_TOKEN")

async def get_ip_info(ip_address):
    if token:
        headers = {"Authorization": f"Bearer {token}"}
    url = f"https://ipinfo.io/{ip_address}"
    if token:
        response = requests.get(url, headers=headers)
    else :
        response = requests.get(url)

    if response.status_code == 200:
        return response

    elif response.status_code == 429:  # Too Many Requests
        # Fallback to lite version
        lite_url = f"https://api.ipinfo.io/lite/{ip_address}/json"
        lite_response = requests.get(lite_url, headers=headers)
        return lite_response

    else:
        return response
