from firebase_admin import auth
class FirebaseRegisterError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

async def revert_firebase_user(firebase_uid):
    if firebase_uid:
        try:
            print(f"Deleting Firebase user with UID: {firebase_uid}")
            await auth.delete_user(firebase_uid)
        except Exception:
            pass  # You may want to log this
