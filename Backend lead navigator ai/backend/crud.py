from sqlalchemy.orm import Session
from . import models, schemas, auth
from datetime import datetime, timedelta
import secrets
import json

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_workspace(db: Session, workspace: schemas.WorkspaceCreate, user_id: int):
    db_workspace = models.Workspace(name=workspace.name)
    db.add(db_workspace)
    db.commit()
    db.refresh(db_workspace)
    
    member = models.WorkspaceMember(
        user_id=user_id,
        workspace_id=db_workspace.id,
        role="Owner"
    )
    db.add(member)
    db.commit()
    
    return db_workspace

def get_user_workspaces(db: Session, user_id: int):
    members = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.user_id == user_id
    ).all()
    return [member.workspace for member in members]

def create_invitation(db: Session, workspace_id: int, invitation: schemas.InvitationCreate):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    db_invitation = models.Invitation(
        workspace_id=workspace_id,
        email=invitation.email,
        role=invitation.role,
        token=token,
        expires_at=expires_at
    )
    db.add(db_invitation)
    db.commit()
    db.refresh(db_invitation)
    return db_invitation

def accept_invitation(db: Session, token: str, user_id: int):
    invitation = db.query(models.Invitation).filter(
        models.Invitation.token == token,
        models.Invitation.used == False
    ).first()
    
    if not invitation or invitation.expires_at < datetime.utcnow():
        return None
    
    member = models.WorkspaceMember(
        user_id=user_id,
        workspace_id=invitation.workspace_id,
        role=invitation.role
    )
    db.add(member)
    
    invitation.used = True
    db.commit()
    
    return member

def create_upload_record(db: Session, workspace_id: int, filename: str, filepath: str, 
                        file_type: str, row_count: int, user_id: int):
    upload = models.Upload(
        workspace_id=workspace_id,
        filename=filename,
        filepath=filepath,
        file_type=file_type,
        row_count=row_count,
        uploaded_by=user_id
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload

def save_column_mapping(db: Session, workspace_id: int, file_type: str, mapping: dict):
    existing = db.query(models.ColumnMapping).filter(
        models.ColumnMapping.workspace_id == workspace_id,
        models.ColumnMapping.file_type == file_type
    ).first()
    
    if existing:
        existing.mapping_json = json.dumps(mapping)
        existing.created_at = datetime.utcnow()
    else:
        new_mapping = models.ColumnMapping(
            workspace_id=workspace_id,
            file_type=file_type,
            mapping_json=json.dumps(mapping)
        )
        db.add(new_mapping)
    
    db.commit()
    return True

def get_column_mapping(db: Session, workspace_id: int, file_type: str):
    mapping = db.query(models.ColumnMapping).filter(
        models.ColumnMapping.workspace_id == workspace_id,
        models.ColumnMapping.file_type == file_type
    ).first()
    
    if mapping:
        return json.loads(mapping.mapping_json)
    return None

def log_audit_event(db: Session, user_id: int, workspace_id: int, action: str, details: str):
    log = models.AuditLog(
        user_id=user_id,
        workspace_id=workspace_id,
        action=action,
        details=details
    )
    db.add(log)
    db.commit()

def get_audit_logs(db: Session, workspace_id: int, limit: int = 100):
    return db.query(models.AuditLog).filter(
        models.AuditLog.workspace_id == workspace_id
    ).order_by(models.AuditLog.created_at.desc()).limit(limit).all()

def save_user_filters(db: Session, user_id: int, workspace_id: int, filters: dict):
    pref = db.query(models.UserPreference).filter(
        models.UserPreference.user_id == user_id,
        models.UserPreference.workspace_id == workspace_id
    ).first()
    
    if pref:
        pref.filters_json = json.dumps(filters)
        pref.updated_at = datetime.utcnow()
    else:
        pref = models.UserPreference(
            user_id=user_id,
            workspace_id=workspace_id,
            filters_json=json.dumps(filters)
        )
        db.add(pref)
    
    db.commit()

def get_user_filters(db: Session, user_id: int, workspace_id: int):
    pref = db.query(models.UserPreference).filter(
        models.UserPreference.user_id == user_id,
        models.UserPreference.workspace_id == workspace_id
    ).first()
    
    if pref:
        return json.loads(pref.filters_json)
    return None