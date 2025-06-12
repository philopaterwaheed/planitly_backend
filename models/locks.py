from datetime import datetime, timedelta
from mongoengine import Document, StringField, DateTimeField, IntField


class AccountLock(Document):
    user_id = StringField(required=True, unique=True)
    locked_until = DateTimeField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'account_locks',
        'indexes': [
            {'fields': ['user_id']},
            {'fields': ['locked_until'], 'expireAfterSeconds': 0}
        ]
    }


async def is_account_locked(user_id):
    """Check if account is temporarily locked"""
    try:
        current_time = datetime.utcnow()
        
        lock = AccountLock.objects(
            user_id=user_id,
            locked_until__gt=current_time
        ).first()

        return bool(lock)
    except Exception as e:
        print(f"Error checking account lock: {e}")
        return False


async def lock_account(user_id, hours=24):
    """Temporarily lock an account"""
    try:
        current_time = datetime.utcnow()
        lock_until = current_time + timedelta(hours=hours)

        # Remove any existing locks
        AccountLock.objects(user_id=user_id).delete()

        # Create new lock
        lock = AccountLock(
            user_id=user_id,
            locked_until=lock_until
        )
        lock.save()

        print(f"Account {user_id} locked until {lock_until}")
        return True
    except Exception as e:
        print(f"Error locking account {user_id}: {e}")
        return False


async def unlock_account(user_id):
    """Unlock an account"""
    try:
        result = AccountLock.objects(user_id=user_id).delete()
        print(f"Account {user_id} unlocked. Deleted {result} lock records.")
        return True
    except Exception as e:
        print(f"Error unlocking account {user_id}: {e}")
        return False


async def get_lock_info(user_id):
    """Get lock information for a user"""
    try:
        current_time = datetime.utcnow()
        lock = AccountLock.objects(
            user_id=user_id,
            locked_until__gt=current_time
        ).first()

        if lock:
            return {
                'is_locked': True,
                'locked_until': lock.locked_until,
                'time_remaining': lock.locked_until - current_time
            }
        else:
            return {'is_locked': False}
    except Exception as e:
        print(f"Error getting lock info for {user_id}: {e}")
        return {'is_locked': False}
