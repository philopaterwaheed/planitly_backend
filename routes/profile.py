from fastapi import APIRouter, HTTPException, status, Depends
from middleWares import verify_device
import re
import datetime

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_profile(user_device: tuple = Depends(verify_device)):
    """Retrieve the current user's profile."""
    user = user_device[0]
    try:
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "phone_number": user.phone_number,
            "birthday": user.birthday.isoformat() if user.birthday else None,
            "email_verified": user.email_verified,
            "admin": user.admin,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/", status_code=status.HTTP_200_OK)
async def update_profile(
    profile_data: dict, user_device: tuple = Depends(verify_device)
):
    """Update the current user's profile."""
    user = user_device[0]
    try:
        firstname = profile_data.get("firstname")
        lastname = profile_data.get("lastname")
        phone_number = profile_data.get("phone_number")
        birthday = profile_data.get("birthday")

        if firstname:
            if not firstname.isalpha():
                raise HTTPException(
                    status_code=400,
                    detail="First name must contain only alphabetic characters.",
                )
            user.firstname = firstname

        if lastname:
            if not lastname.isalpha():
                raise HTTPException(
                    status_code=400,
                    detail="Last name must contain only alphabetic characters.",
                )
            user.lastname = lastname

        if phone_number:
            if not re.match(r"^\+?[1-9]\d{1,14}$", phone_number):
                raise HTTPException(
                    status_code=400, detail="Invalid phone number format."
                )
            user.phone_number = phone_number

        if birthday:
            try:
                if not isinstance(birthday, str):
                    birthday = datetime.strptime(birthday, "%Y-%m-%d %H:%M:%S")

                birthday_date = datetime.datetime.fromisoformat(birthday)
                if birthday_date > datetime.datetime.now():
                    raise HTTPException(
                        status_code=400, detail="Birthday cannot be in the future."
                    )
                if (datetime.datetime.now() - birthday_date).days < 13 * 365:
                    raise HTTPException(
                        status_code=400, detail="Users must be at least 13 years old."
                    )
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid birthday format. Use ISO format (YYYY-MM-DD)."
                )
        else: 
                raise HTTPException(
                    status_code=400, detail="Messing birthday"
                )

        user.save()
        return {"message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))