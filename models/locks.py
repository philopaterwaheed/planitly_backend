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
            {'fields': ['locked_until'], 'expireAfterSeconds': 0}  # TTL index
        ]
    }


async def is_account_locked(user_id):
    """Check if account is temporarily locked"""
    current_time = datetime.utcnow()
    lock = AccountLock.objects(
        user_id=user_id,
        locked_until__gt=current_time
    ).first()

    return bool(lock)


async def lock_account(user_id, hours=24):
    """Temporarily lock an account"""
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


async def unlock_account(user_id):
    """Unlock an account"""
    AccountLock.objects(user_id=user_id).delete()
