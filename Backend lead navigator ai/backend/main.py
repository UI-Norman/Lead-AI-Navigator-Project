from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Query
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import timedelta
import chardet
import pandas as pd
import gzip
import zipfile
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from . import ai_assistant
from . import models, schemas, auth, crud
from .database import engine, get_db, init_db
import logging
from fastapi import HTTPException, Depends
from datetime import datetime, timedelta
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 2 * 1024 * 1024 * 1024))
app = FastAPI(title="Lead Navigator AI API", version="1.0.0")

# Custom security function to get authentication token from query parameter
def get_auth_token(token: Optional[str] = Query(None, description="Authentication token")):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8050", "http://127.0.0.1:8050", "http://0.0.0.0:8050"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "./uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Email Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "your_email@gmail.com")  # CHANGE THIS
SMTP_PASS = os.getenv("SMTP_PASS", "your_app_password")     # CHANGE THIS

# ============================================================================
# EMAIL FUNCTION (MISSING THA!)
# ============================================================================
def send_email(to: str, subject: str, html: str):
    """Send HTML email using SMTP"""
    try:
        msg = MIMEMultipart("alternative")
        msg['From'] = SMTP_USER
        msg['To'] = to
        msg['Subject'] = subject

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to, msg.as_string())

        logger.info(f"Email sent to {to}")
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        # Don't fail login on email error
        pass

# ============================================================================
# ROOT & STARTUP
# ============================================================================
@app.get("/")
async def root():
    return {
        "message": "Welcome to Lead Navigator AI API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "login": "/auth/login",
            "register": "/auth/register",
            "magic_link": "/auth/magic-link",
            "verify_magic": "/auth/verify-magic-link"
        }
    }

@app.on_event("startup")
async def startup():
    init_db()
    print("\n" + "="*60)
    print("Backend API Started Successfully!")
    print("="*60)
    print(f"API URL: http://localhost:8000")
    print(f"Docs: http://localhost:8000/docs")
    print("="*60 + "\n")

# ============================================================================
# AUTH ENDPOINTS
# ============================================================================
@app.post("/auth/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = crud.create_user(db=db, user=user)
    
    default_workspace = schemas.WorkspaceCreate(name=f"{new_user.full_name}'s Workspace")
    workspace = crud.create_workspace(db, default_workspace, new_user.id)
    
    crud.log_audit_event(
        db, 
        new_user.id, 
        workspace.id, 
        "user-register",
        f"User {new_user.email} registered and default workspace created"
    )
    
    logger.info(f"New user registered: {new_user.email}")
    
    return new_user

@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    workspaces = crud.get_user_workspaces(db, user.id)
    workspace_id = workspaces[0].id if workspaces else 0
    
    crud.log_audit_event(db, user.id, workspace_id, "sign-in", f"User {user.email} logged in")
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    
    logger.info(f"User logged in: {user.email}")
    
    return {"access_token": access_token, "token_type": "bearer"}

# ============================================================================
# MAGIC LINK WITH EMAIL
# ============================================================================
@app.post("/auth/magic-link")
def request_magic_link(email: str = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate magic token (short-lived: 5 min)
    magic_token = auth.create_magic_link_token(email)
    magic_link = f"http://localhost:8050/auth/verify?token={magic_token}"

    # Generate access_token immediately (optional, risky)
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # Beautiful HTML Email
    html_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
        <h2 style="color: #007bff; text-align: center;">Lead Navigator AI</h2>
        <p style="font-size: 16px;">Hi <strong>{user.full_name}</strong>,</p>
        <p>Click the button below to <strong>login instantly</strong>:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{magic_link}" style="background: #007bff; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                Login Now
            </a>
        </div>
        <p style="color: #666; font-size: 14px;">Link expires in <strong>5 minutes</strong>.</p>
        <hr>
        <p style="font-size: 12px; color: #999; text-align: center;">
            © 2025 Lead Navigator AI
        </p>
    </div>
    """

    send_email(to=email, subject="Your Magic Login Link", html=html_email)

    # RETURN ACCESS TOKEN IN RESPONSE (FOR DEV ONLY)
    return {
        "message": "Magic link sent",
        "magic_link": magic_link,
        "access_token": access_token,           # YE ADD KARO
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "full_name": user.full_name
        }
    }

@app.get("/auth/verify-magic-link")
def verify_magic_link(token: str, db: Session = Depends(get_db)):
    user = auth.verify_magic_link_token(token, db)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "full_name": user.full_name
        }
    }

@app.get("/users/me", response_model=schemas.User)
async def read_users_me(token: str = Depends(get_auth_token), db: Session = Depends(get_db)):
    user = auth.get_current_active_user_from_query(token, db)
    return user

@app.post("/workspaces", response_model=schemas.Workspace)
def create_workspace(
    workspace: schemas.WorkspaceCreate,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    new_workspace = crud.create_workspace(db, workspace, user.id)
    
    crud.log_audit_event(
        db,
        user.id,
        new_workspace.id,
        "workspace-create",
        f"Workspace '{new_workspace.name}' created by {user.email}"
    )
    
    logger.info(f"✅ Workspace created: '{new_workspace.name}' (ID: {new_workspace.id}) by {user.email}")
    
    return new_workspace

@app.get("/workspaces", response_model=List[schemas.Workspace])
def list_workspaces(
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    return crud.get_user_workspaces(db, user.id)

@app.get("/workspaces/{workspace_id}", response_model=schemas.Workspace)
def get_workspace(
    workspace_id: int,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    member = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == workspace_id,
        models.WorkspaceMember.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    return workspace

@app.put("/workspaces/{workspace_id}", response_model=schemas.Workspace)
def update_workspace(
    workspace_id: int,
    workspace_update: schemas.WorkspaceCreate,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    member = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == workspace_id,
        models.WorkspaceMember.user_id == user.id
    ).first()
    
    if not member or member.role != "Owner":
        raise HTTPException(status_code=403, detail="Only workspace owners can update workspace settings")
    
    old_name = workspace.name
    new_name = workspace_update.name
    
    workspace.name = new_name
    db.commit()
    db.refresh(workspace)
    
    crud.log_audit_event(
        db, 
        user.id, 
        workspace_id, 
        "workspace-rename",
        f"Workspace renamed from '{old_name}' to '{new_name}' by {user.email}"
    )
    
    logger.info(f"✅ Workspace {workspace_id} renamed: '{old_name}' → '{new_name}'")
    
    return workspace

@app.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    member = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == workspace_id,
        models.WorkspaceMember.user_id == user.id
    ).first()
    
    if not member or member.role != "Owner":
        raise HTTPException(status_code=403, detail="Only workspace owners can delete workspaces")
    
    workspace_name = workspace.name
    
    crud.log_audit_event(
        db, 
        user.id, 
        workspace_id, 
        "workspace-delete",
        f"Workspace '{workspace_name}' deleted by {user.email}"
    )
    
    db.query(models.WorkspaceMember).filter(models.WorkspaceMember.workspace_id == workspace_id).delete()
    db.query(models.Upload).filter(models.Upload.workspace_id == workspace_id).delete()
    db.query(models.ColumnMapping).filter(models.ColumnMapping.workspace_id == workspace_id).delete()
    db.query(models.UserPreference).filter(models.UserPreference.workspace_id == workspace_id).delete()
    
    db.delete(workspace)
    db.commit()
    
    logger.info(f"✅ Workspace {workspace_id} ('{workspace_name}') deleted by {user.email}")
    
    return {
        "message": "Workspace deleted successfully",
        "workspace_name": workspace_name,
        "deleted_by": user.email
    }

@app.post("/workspaces/{workspace_id}/invite")
def invite_user(
    workspace_id: int,
    invitation: schemas.InvitationCreate,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    inv = crud.create_invitation(db, workspace_id, invitation)
    
    crud.log_audit_event(
        db, 
        user.id, 
        workspace_id, 
        "invite-send",
        f"Invited {invitation.email} as {invitation.role} by {user.email}"
    )
    
    invite_link = f"http://localhost:8050/invite?token={inv.token}"
    
    # Email bhi bhej do (optional)
    html_email = f"""
    <h2>You're Invited to Lead Navigator AI!</h2>
    <p><strong>{invitation.email}</strong> has been invited as <strong>{invitation.role}</strong>.</p>
    <p><a href='{invite_link}' style='background:#007bff;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;'>Join Now</a></p>
    <p>Link expires in 7 days.</p>
    """
    try:
        send_email(to=invitation.email, subject="You're Invited!", html=html_email)
    except:
        pass  # Email fail ho to bhi invite create ho

    logger.info(f"Invitation sent: {invitation.email} → workspace {workspace_id} as {invitation.role}")
    
    return {
        "message": "Invitation sent successfully",
        "invite_link": invite_link,
        "invited_email": invitation.email,
        "role": invitation.role
    }

@app.post("/invitations/accept/{invite_token}")
def accept_invite(
    invite_token: str,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    member = crud.accept_invitation(db, invite_token, user.id)
    
    if not member:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")
    
    workspace = db.query(models.Workspace).filter(
        models.Workspace.id == member.workspace_id
    ).first()
    
    workspace_name = workspace.name if workspace else "Unknown"
    
    crud.log_audit_event(
        db, 
        user.id, 
        member.workspace_id, 
        "invite-accept",
        f"User {user.email} accepted invitation and joined workspace '{workspace_name}' as {member.role}"
    )
    
    logger.info(f"✅ User {user.email} accepted invite to workspace {member.workspace_id}")
    
    return {
        "message": "Invitation accepted successfully",
        "workspace_id": member.workspace_id,
        "workspace_name": workspace_name,
        "role": member.role,
        "user_email": user.email
    }

@app.post("/workspaces/{workspace_id}/upload")
async def upload_file(
    workspace_id: int,
    file: UploadFile = File(...),
    file_type: str = Form(...),
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    allowed_extensions = ['.csv', '.tsv', '.txt', '.gz', '.gzip', '.zip']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file format. Allowed: {', '.join(allowed_extensions)}"
        )
    
    file_path = os.path.join(UPLOAD_FOLDER, f"{workspace_id}_{file.filename}")
    
    try:
        content = await file.read()
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        if file.filename.lower().endswith(('.gz', '.gzip')):
            try:
                content = gzip.decompress(content)
                logger.info(f"Decompressed GZIP file: {file.filename}")
            except Exception as e:
                logger.error(f"GZIP decompression failed: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid GZIP file: {str(e)}")
        
        elif file.filename.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(BytesIO(content)) as zf:
                    csv_files = [f for f in zf.namelist() if f.lower().endswith(('.csv', '.tsv', '.txt'))]
                    if not csv_files:
                        raise HTTPException(status_code=400, detail="No CSV/TSV files found in ZIP")
                    content = zf.read(csv_files[0])
                    logger.info(f"Extracted {csv_files[0]} from ZIP")
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid ZIP file")
        
        def detect_encoding(data):
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252']
            for enc in encodings:
                try:
                    data.decode(enc)
                    return enc
                except:
                    continue
            return 'latin-1'
        
        encoding = detect_encoding(content[:10000])
        logger.info(f"Detected encoding: {encoding}")
        
        sample = content[:10000].decode(encoding, errors='ignore')
        separators = {',': sample.count(','), '\t': sample.count('\t'), ';': sample.count(';')}
        separator = max(separators.items(), key=lambda x: x[1])[0]
        logger.info(f"Detected separator: {repr(separator)}")
        
        try:
            df = pd.read_csv(
                BytesIO(content), 
                encoding=encoding, 
                sep=separator,
                on_bad_lines='skip',
                engine='c'
            )
        except Exception as e1:
            logger.warning(f"C engine failed, trying Python engine: {e1}")
            try:
                df = pd.read_csv(
                    BytesIO(content), 
                    encoding=encoding, 
                    sep=separator,
                    on_bad_lines='skip',
                    engine='python'
                )
            except Exception as e2:
                logger.error(f"Python engine also failed: {e2}")
                raise HTTPException(status_code=400, detail=f"Error reading file: {str(e2)}")
        
        original_rows = len(df)
        df = df.dropna(how='all')
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        if df.empty:
            raise HTTPException(status_code=400, detail="File is empty or unreadable")
        
        row_count = len(df)
        columns = df.columns.tolist()
        
        logger.info(f"✅ Processed {row_count:,} rows × {len(columns)} columns")
        
        try:
            ai_assistant.vector_store.store_data(workspace_id, file_type, df)
            logger.info(f"📚 Data stored in vector store for AI queries")
        except Exception as e:
            logger.error(f"⚠️ Failed to store in vector store: {e}")
        
        upload = crud.create_upload_record(
            db, workspace_id, file.filename, file_path, 
            file_type, row_count, user.id
        )
        
        crud.log_audit_event(
            db, user.id, workspace_id, "upload", 
            f"Uploaded {file.filename} ({row_count:,} rows, {len(columns)} columns) by {user.email}"
        )
        
        logger.info(f"✅ File uploaded: {file.filename} ({row_count:,} rows)")
        
        return {
            "success": True,
            "message": f"File uploaded successfully and ready for AI queries: {file.filename}",
            "upload": {
                "id": upload.id,
                "filename": upload.filename,
                "file_type": upload.file_type,
                "row_count": upload.row_count,
                "uploaded_at": upload.uploaded_at.isoformat(),
                "columns": columns[:100],
                "total_columns": len(columns),
                "encoding": encoding,
                "separator": repr(separator),
                "rag_enabled": True
            }
        }
    
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.error(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500, 
            detail=f"Upload failed: {str(e)}"
        )

@app.post("/ai/query")
async def query_ai(
    query: str = Form(...),
    workspace_id: int = Form(...),
    file: Optional[UploadFile] = File(None),
    file_type: Optional[str] = Form(None),
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    """
    Enhanced AI query endpoint: Handles file upload, stores data in vector store, and processes RAG query
    """
    user = auth.get_current_active_user_from_query(token, db)
    
    # Validate workspace access
    workspace = db.query(models.Workspace).filter(models.Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    member = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == workspace_id,
        models.WorkspaceMember.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    # Handle file upload if provided
    if file and file_type:
        allowed_extensions = ['.csv', '.tsv', '.txt', '.gz', '.gzip', '.zip']
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file format. Allowed: {', '.join(allowed_extensions)}"
            )
        
        if file_type not in ['buyers', 'visitors']:
            raise HTTPException(status_code=400, detail="File type must be 'buyers' or 'visitors'")
        
        file_path = os.path.join(UPLOAD_FOLDER, f"{workspace_id}_{file.filename}")
        
        try:
            content = await file.read()
            
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            
            if file.filename.lower().endswith(('.gz', '.gzip')):
                try:
                    content = gzip.decompress(content)
                    logger.info(f"Decompressed GZIP file: {file.filename}")
                except Exception as e:
                    logger.error(f"GZIP decompression failed: {e}")
                    raise HTTPException(status_code=400, detail=f"Invalid GZIP file: {str(e)}")
            
            elif file.filename.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(BytesIO(content)) as zf:
                        csv_files = [f for f in zf.namelist() if f.lower().endswith(('.csv', '.tsv', '.txt'))]
                        if not csv_files:
                            raise HTTPException(status_code=400, detail="No CSV/TSV files found in ZIP")
                        content = zf.read(csv_files[0])
                        logger.info(f"Extracted {csv_files[0]} from ZIP")
                except zipfile.BadZipFile:
                    raise HTTPException(status_code=400, detail="Invalid ZIP file")
            
            def detect_encoding(data):
                encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252']
                for enc in encodings:
                    try:
                        data.decode(enc)
                        return enc
                    except:
                        continue
                return 'latin-1'
            
            encoding = detect_encoding(content[:10000])
            logger.info(f"Detected encoding: {encoding}")
            
            sample = content[:10000].decode(encoding, errors='ignore')
            separators = {',': sample.count(','), '\t': sample.count('\t'), ';': sample.count(';')}
            separator = max(separators.items(), key=lambda x: x[1])[0]
            logger.info(f"Detected separator: {repr(separator)}")
            
            try:
                df = pd.read_csv(
                    BytesIO(content), 
                    encoding=encoding, 
                    sep=separator,
                    on_bad_lines='skip',
                    engine='c'
                )
            except Exception as e1:
                logger.warning(f"C engine failed, trying Python engine: {e1}")
                try:
                    df = pd.read_csv(
                        BytesIO(content), 
                        encoding=encoding, 
                        sep=separator,
                        on_bad_lines='skip',
                        engine='python'
                    )
                except Exception as e2:
                    logger.error(f"Python engine also failed: {e2}")
                    raise HTTPException(status_code=400, detail=f"Error reading file: {str(e2)}")
            
            df = df.dropna(how='all')
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            if df.empty:
                raise HTTPException(status_code=400, detail="File is empty or unreadable")
            
            row_count = len(df)
            columns = df.columns.tolist()
            
            logger.info(f"✅ Processed uploaded file: {row_count:,} rows × {len(columns)} columns")
            
            # Store in vector store
            try:
                ai_assistant.vector_store.store_data(workspace_id, file_type, df)
                logger.info(f"📚 Data stored in vector store for AI queries")
                
                # Save upload record
                upload = crud.create_upload_record(
                    db, workspace_id, file.filename, file_path, 
                    file_type, row_count, user.id
                )
                
                crud.log_audit_event(
                    db, user.id, workspace_id, "upload", 
                    f"Uploaded {file.filename} ({row_count:,} rows, {len(columns)} columns) via AI query endpoint by {user.email}"
                )
            except Exception as e:
                logger.error(f"⚠️ Failed to store in vector store: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to store data: {str(e)}")
        
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            logger.error(f"Upload error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Process RAG query
    try:
        result = ai_assistant.query_ai_with_rag(query, workspace_id)
        
        crud.log_audit_event(
            db, user.id, workspace_id, "ai-query",
            f"AI query: '{query[:50]}...' - Context used: {result.get('context_used', False)}"
        )
        
        return {
            "response": result['response'],
            "sources": result.get('sources', []),
            "context_used": result.get('context_used', False),
            "context_length": result.get('context_length', 0),
            "upload_status": {
                "uploaded": bool(file and file_type),
                "filename": file.filename if file else None,
                "file_type": file_type,
                "row_count": row_count if file else None,
                "columns": columns if file else None
            } if file else None
        }
    
    except Exception as e:
        logger.error(f"AI query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI query failed: {str(e)}")

@app.get("/workspaces/{workspace_id}/ai-status")
def get_ai_status(
    workspace_id: int,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    if workspace_id not in ai_assistant.vector_store.workspaces:
        return {
            "ai_ready": False,
            "message": "No data uploaded yet. Upload data to enable AI queries.",
            "buyers_data": False,
            "visitors_data": False
        }
    
    workspace_data = ai_assistant.vector_store.workspaces[workspace_id]
    
    return {
        "ai_ready": True,
        "message": "AI assistant is ready with your data!",
        "buyers_data": workspace_data['buyers'] is not None,
        "buyers_rows": workspace_data['buyers']['total_rows'] if workspace_data['buyers'] else 0,
        "visitors_data": workspace_data['visitors'] is not None,
        "visitors_rows": workspace_data['visitors']['total_rows'] if workspace_data['visitors'] else 0
    }

@app.get("/workspaces/{workspace_id}/uploads")
def list_uploads(
    workspace_id: int,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    uploads = db.query(models.Upload).filter(models.Upload.workspace_id == workspace_id).order_by(models.Upload.uploaded_at.desc()).all()
    return {
        "uploads": [
            {
                "id": u.id,
                "filename": u.filename,
                "file_type": u.file_type,
                "row_count": u.row_count,
                "uploaded_at": u.uploaded_at.isoformat()
            }
            for u in uploads
        ]
    }

@app.post("/workspaces/{workspace_id}/column-mapping")
def save_mapping(
    workspace_id: int,
    mapping_data: schemas.ColumnMappingCreate,  # YE SAHI HAI
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    if not mapping_data.mapping:
        raise HTTPException(status_code=400, detail="Mapping cannot be empty")
    
    # YE LINE GALAT HAI:
    # crud.save_column_mapping(db, workspace_id, mapping_data.file_type, mapping_data.mapping)
    
    # YE SAHI HAI:
    crud.save_column_mapping(db, workspace_id, mapping_data.file_type, mapping_data.mapping)
    
    mapped_count = len([v for v in mapping_data.mapping.values() if v])
    crud.log_audit_event(
        db, user.id, workspace_id, "mapping-save",
        f"Saved {mapping_data.file_type} mapping: {mapped_count} columns mapped"
    )
    
    return {
        "success": True,
        "message": "Mapping saved successfully",
        "file_type": mapping_data.file_type,
        "mapped_columns": mapped_count
    }

@app.get("/workspaces/{workspace_id}/column-mapping/{file_type}")
def get_mapping(
    workspace_id: int,
    file_type: str,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    mapping = crud.get_column_mapping(db, workspace_id, file_type)
    
    if mapping:
        mapped_count = len([v for v in mapping.values() if v is not None])
        return {
            "success": True,
            "mapping": mapping,
            "file_type": file_type,
            "mapped_columns": mapped_count
        }
    else:
        return {
            "success": False,
            "mapping": None,
            "message": f"No saved mapping found for {file_type}"
        }

@app.post("/workspaces/{workspace_id}/suggest-mapping")
async def suggest_mapping(
    workspace_id: int,
    file: UploadFile = File(...),
    file_type: str = Form(...),
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)

    try:
        content = await file.read()

        if file.filename.lower().endswith(('.gz', '.gzip')):
            content = gzip.decompress(content)
        elif file.filename.lower().endswith('.zip'):
            with zipfile.ZipFile(BytesIO(content)) as zf:
                csv_files = [f for f in zf.namelist() if f.lower().endswith(('.csv', '.tsv', '.txt'))]
                if csv_files:
                    content = zf.read(csv_files[0])

        def detect_encoding(data):
            for enc in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                try: data.decode(enc); return enc
                except: pass
            return 'latin-1'
        encoding = detect_encoding(content[:10000])
        sample = content[:10000].decode(encoding, errors='ignore')
        sep = max({',': sample.count(','), '\t': sample.count('\t'), ';': sample.count(';')}.items(), key=lambda x: x[1])[0]

        df = pd.read_csv(
            BytesIO(content),
            encoding=encoding,
            sep=sep,
            nrows=2000,
            on_bad_lines='skip',
            dtype=str
        ).fillna("")

        columns = df.columns.tolist()

        # Store data in vector store
        try:
            ai_assistant.vector_store.store_data(workspace_id, file_type, df)
            logger.info(f"📚 Data stored in vector store for AI queries")
        except Exception as e:
            logger.error(f"⚠️ Failed to store in vector store: {e}")

        mapping = ai_assistant.suggest_column_mapping(
            columns=columns,
            file_type=file_type,
            sample_data=df
        )

        mapped = len([v for v in mapping.values() if v])
        confidence = round(mapped / len(columns) * 100, 1) if columns else 0

        crud.log_audit_event(
            db, user.id, workspace_id, "mapping-suggest",
            f"AI suggested {mapped}/{len(columns)} columns for {file.filename}"
        )

        return {
            "success": True,
            "suggested_mapping": mapping,
            "file_type": file_type,
            "confidence": confidence,
            "stats": {
                "total_columns": len(columns),
                "mapped_columns": mapped
            }
        }

    except Exception as e:
        logger.error(f"Mapping error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/workspaces/{workspace_id}/column-mapping/{file_type}")
def delete_mapping(
    workspace_id: int,
    file_type: str,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    existing = db.query(models.ColumnMapping).filter(
        models.ColumnMapping.workspace_id == workspace_id,
        models.ColumnMapping.file_type == file_type
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        
        crud.log_audit_event(
            db, user.id, workspace_id, "mapping-delete",
            f"Deleted {file_type} column mapping"
        )
        
        logger.info(f"✅ Mapping deleted: {file_type}")
        
        return {
            "success": True,
            "message": f"Mapping for {file_type} deleted successfully"
        }
    else:
        raise HTTPException(status_code=404, detail=f"No mapping found for {file_type}")

@app.get("/workspaces/{workspace_id}/audit-logs")
def get_audit_logs(
    workspace_id: int,
    limit: int = 100,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    
    member = db.query(models.WorkspaceMember).filter(
        models.WorkspaceMember.workspace_id == workspace_id,
        models.WorkspaceMember.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    logs = db.query(models.AuditLog).filter(
        models.AuditLog.workspace_id == workspace_id
    ).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    
    enhanced_logs = []
    for log in logs:
        user_obj = db.query(models.User).filter(models.User.id == log.user_id).first()
        enhanced_logs.append({
            "id": log.id,
            "action": log.action,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
            "user_email": user_obj.email if user_obj else "Unknown",
            "user_name": user_obj.full_name if user_obj else "Unknown User"
        })
    
    logger.info(f"✅ Retrieved {len(enhanced_logs)} audit logs for workspace {workspace_id}")
    
    return {
        "logs": enhanced_logs,
        "total": len(enhanced_logs),
        "workspace_id": workspace_id
    }

@app.post("/workspaces/{workspace_id}/filters")
def save_filters(
    workspace_id: int,
    filters: dict,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    crud.save_user_filters(db, user.id, workspace_id, filters)
    return {"message": "Filters saved"}

@app.get("/workspaces/{workspace_id}/filters")
def get_filters(
    workspace_id: int,
    token: str = Depends(get_auth_token),
    db: Session = Depends(get_db)
):
    user = auth.get_current_active_user_from_query(token, db)
    filters = crud.get_user_filters(db, user.id, workspace_id)
    return {"filters": filters}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Lead Navigator AI API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)