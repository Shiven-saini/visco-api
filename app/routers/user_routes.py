from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..schemas import UserResponse, UserUpdate, SuccessResponse
from .. import models
from ..auth import hash_password, get_current_user

router = APIRouter(prefix="/users", tags=["Users Management"])

@router.post('/')
async def admin_add_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only Admin can add users
    if current_user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can add users")

    # Check if role is valid and exists
    if role not in ["Manager", "Viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    target_role = db.query(models.Role).filter(models.Role.name == role).first()
    if not target_role:
        raise HTTPException(status_code=400, detail="Role not found")

    # Check if email already exists
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="This username/Email is already in use")

    # Create new user
    new_user = models.User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role_id=target_role.id,
        org_id=current_user.org_id
    )
    db.add(new_user)
    db.commit()

    return {"msg": f"{role} added successfully."}

@router.get('/')
async def get_all_employees_from_admin(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only Admin can access this
    if current_user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can access this data")

    # Fetch all employees from the same organization except the admin
    employees = db.query(models.User).filter(
        models.User.org_id == current_user.org_id,
        models.User.id != current_user.id
    ).all()

    result = []
    for emp in employees:
        ip_data = db.query(models.IPAddress).filter(
            models.IPAddress.user_id == emp.id
        ).order_by(models.IPAddress.last_login.desc()).first()

        result.append({
            "id": emp.id,
            "name": emp.name,
            "email": emp.email,
            "role": emp.role.name,
            "ip_address": ip_data.ip_address if ip_data else None,
            "created_at": ip_data.created_at if ip_data else None,
            "last_login": ip_data.last_login if ip_data else None
        })

    return {
        "organization_id": current_user.org_id,
        "organization_name": current_user.org.name,
        "email": current_user.email,
        "admin_name": current_user.name,
        "employees": result
    }

@router.get('/{user_id}')
async def get_single_user_from_admin(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only Admin can access this
    if current_user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can access this data")

    emp = db.query(models.User).filter(
        models.User.org_id == current_user.org_id,
        models.User.id == user_id,
        models.User.id != current_user.id  
    ).first()

    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found or not in your organization")

    # Fetch latest IP record
    ip_data = db.query(models.IPAddress).filter(
        models.IPAddress.user_id == emp.id
    ).order_by(models.IPAddress.last_login.desc()).first()

    return {
        "organization_id": current_user.org_id,
        "organization_name": current_user.org.name,
        "admin_email": current_user.email,
        "admin_name": current_user.name,
        "employee": {
            "id": emp.id,
            "name": emp.name,
            "email": emp.email,
            "role": emp.role.name,
            "ip_address": ip_data.ip_address if ip_data else None,
            "created_at": ip_data.created_at if ip_data else None,
            "last_login": ip_data.last_login if ip_data else None
        }
    }

@router.delete('/{user_id}')
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_user)
):
    # Ensure only Admin can delete
    if current_admin.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can delete their Users")

    # Fetch user with organization, ensuring org was created by current admin
    user = db.query(models.User).join(models.Organization, models.User.org_id == models.Organization.id).filter(
        models.User.id == user_id,
        models.User.org_id == current_admin.org_id,
        models.Organization.created_by == current_admin.id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found or unauthorized")

    # Delete dependent records (e.g., IPs)
    db.query(models.IPAddress).filter(models.IPAddress.user_id == user.id).delete()

    # Delete user
    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}
