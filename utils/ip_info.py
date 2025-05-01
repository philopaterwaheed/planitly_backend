import requests
from consts import env_variables

token = env_variables.get("IPI_TOKEN")

async def get_ip_info(ip_address):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    url = f"https://ipinfo.io/{ip_address}"

    # First attempt with token (if available)
    response = requests.get(url, headers=headers) if headers else requests.get(url)

    if response.status_code == 200:
        return response

    elif response.status_code == 429:  # Too Many Requests
        # Retry without token
        response = requests.get(url)
        if response.status_code == 200:
            return response

        elif response.status_code == 429 and headers:  # Still Too Many Requests
            # Fallback to lite version
            lite_url = f"https://api.ipinfo.io/lite/{ip_address}/json"
            lite_response = requests.get(lite_url,headers=headers)
            return lite_response

    return response
