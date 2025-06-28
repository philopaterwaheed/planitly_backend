from fastapi import APIRouter, HTTPException, status, Depends
from models import Category_db , Subject_db
from middleWares import verify_device
from utils import decode_name_from_url, encode_name_for_url
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_category(
    data: dict,
    user_device: tuple = Depends(verify_device)
):
    """
    Create a new category for the current user.
    Optionally, add up to 10 subjects to this category by providing a 'subject_ids' list in the request body.
    """
    current_user = user_device[0]
    try:
        category_name = data.get("name")
        subject_ids = data.get("subject_ids", [])

        if not category_name:
            raise HTTPException(status_code=400, detail="Category name is required.")

        if Category_db.objects(name=category_name, owner=current_user.id).first():
            raise HTTPException(status_code=400, detail="Category already exists.")

        if subject_ids and len(subject_ids) > 10:
            raise HTTPException(status_code=400, detail="You can add at most 10 subjects to a new category.")

        # Create the category
        category = Category_db(
            name=category_name, 
            owner=current_user.id,
            created_at=datetime.now(timezone.utc)
        )
        category.save()

        # Update subjects' category if subject_ids provided
        updated_subjects = []
        if subject_ids:
            subjects = Subject_db.objects(id__in=subject_ids, owner=current_user.id)
            for subject in subjects:
                # Only update if not already in this category
                if subject.category != category_name:
                    if subject.template:
                        # If the subject has a template discard update
                        continue
                    subject.update(category=category_name)
                    updated_subjects.append(str(subject.id))

        return {
            "message": "Category created successfully.",
            "name": category.name,
            "created_at": category.created_at.isoformat(),
            "subjects_updated": updated_subjects
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{category_name}", status_code=status.HTTP_200_OK)
async def update_category(category_name: str, data: dict, user_device: tuple = Depends(verify_device)):
    """Update a category's name."""
    current_user = user_device[0]
    try:
        # Decode URL-encoded category names (e.g., spaces as %20)
        decoded_category_name = decode_name_from_url(category_name)
        
        category = Category_db.objects(name=decoded_category_name, owner=current_user.id).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Category '{decoded_category_name}' not found.")
            
        new_name = data.get("name")
        if not new_name:
            raise HTTPException(status_code=400, detail="New category name is required.")

        # Check if the new name already exists
        if Category_db.objects(name=new_name, owner=current_user.id).first():
            raise HTTPException(status_code=400, detail="Category with this name already exists.")

        # Update all subjects in the old category to the new category name
        Subject_db.objects(category=decoded_category_name, owner=current_user.id).update(category=new_name)
        category.update(name=new_name)
        return {"message": "Category updated successfully."}
    except Category_db.DoesNotExist:
        raise HTTPException(status_code=404, detail="Category not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{category_name}", status_code=status.HTTP_200_OK)
async def delete_category(category_name: str, user_device: tuple = Depends(verify_device)):
    """Delete a category and set all its associated subjects to 'Uncategorized'."""
    current_user = user_device[0]
    try:
        # Decode URL-encoded category names (e.g., spaces as %20)
        decoded_category_name = decode_name_from_url(category_name)

        category = Category_db.objects(name=decoded_category_name, owner=current_user.id).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Category '{decoded_category_name}' not found.")

        # Bulk update all subjects in the category to "Uncategorized"
        update_result = Subject_db.objects(
            category=decoded_category_name, 
            owner=current_user.id
        ).update(category="Uncategorized")

        # Delete the category
        category.delete()

        return {
            "message": f"Category '{decoded_category_name}' deleted, and {update_result} associated subjects have been set to 'Uncategorized'."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/", status_code=status.HTTP_200_OK)
async def list_categories(
    user_device: tuple = Depends(verify_device),
    skip: int = 0,
    limit: int = 40
):
    """List all categories for the current user with pagination."""
    MAX_LIMIT = 40
    current_user = user_device[0]
    try:
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT

        query = Category_db.objects(owner=current_user.id).order_by('-created_at')
        total = query.count()
        categories = query.skip(skip).limit(limit)
        return {
            "total": total,
            "categories": [category.to_json() for category in categories]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/{category_name}/subjects", status_code=status.HTTP_200_OK)
async def list_subjects_in_category(
    category_name: str,
    user_device: tuple = Depends(verify_device),
    skip: int = 0,
    limit: int = 40
):
    """
    List subjects within a specific category for the current user, with pagination.
    """
    MAX_LIMIT = 40
    current_user = user_device[0]
    try:
        # Decode URL-encoded category names (e.g., spaces as %20)
        decoded_category_name = decode_name_from_url(category_name)
        
        # Ensure the category exists for the user
        category = Category_db.objects(name=decoded_category_name, owner=current_user.id).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Category '{decoded_category_name}' not found.")

        if limit > MAX_LIMIT:
            limit = MAX_LIMIT

        query = Subject_db.objects(category=decoded_category_name, owner=current_user.id).order_by('-created_at')
        total = query.count()
        subjects = query.skip(skip).limit(limit)
        return {
            "total": total,
            "subjects": [subject.to_mongo() for subject in subjects]
        }
    except Category_db.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Category '{category_name}' not found.")
    except Subject_db.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"No subjects found in category '{category_name}'.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/uncategorized", status_code=status.HTTP_200_OK)
async def list_uncategorized_subjects(
    user_device: tuple = Depends(verify_device),
    skip: int = 0,
    limit: int = 40
):
    """
    List all uncategorized subjects for the current user, with pagination.
    """
    MAX_LIMIT = 40
    current_user = user_device[0]
    try:
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT

        query = Subject_db.objects(category="Uncategorized", owner=current_user.id).order_by('-created_at')
        total = query.count()
        subjects = query.skip(skip).limit(limit)
        return {
            "total": total,
            "subjects": [subject.to_mongo() for subject in subjects]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
