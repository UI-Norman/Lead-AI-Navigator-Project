from pydantic import BaseModel, EmailStr, field_validator, ValidationError
from datetime import datetime
from typing import Optional, List, Dict, Any

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must not exceed 128 characters')
        # Optional: Add more validation rules
        # if not any(c.isupper() for c in v):
        #     raise ValueError('Password must contain at least one uppercase letter')
        # if not any(c.islower() for c in v):
        #     raise ValueError('Password must contain at least one lowercase letter')
        # if not any(c.isdigit() for c in v):
        #     raise ValueError('Password must contain at least one number')
        return v
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name"""
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError('Full name must be at least 2 characters long')
            if len(v) > 100:
                raise ValueError('Full name must not exceed 100 characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class WorkspaceCreate(BaseModel):
    name: str
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate workspace name"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Workspace name must be at least 2 characters long')
        if len(v) > 100:
            raise ValueError('Workspace name must not exceed 100 characters')
        return v

class Workspace(BaseModel):
    id: int
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = "Viewer"
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        """Validate role"""
        allowed_roles = ['Owner', 'Analyst', 'Viewer']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class UploadResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    row_count: int
    uploaded_at: datetime
# Add these classes to backend/schemas.py

class RAGQueryRequest(BaseModel):
    """Request for RAG-powered AI query"""
    query: str
    workspace_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError('Query must be at least 3 characters')
        if len(v) > 1000:
            raise ValueError('Query must not exceed 1000 characters')
        return v


class RAGQueryResponse(BaseModel):
    """Response from RAG-powered AI query"""
    response: str
    sources: List[str] = []
    num_sources: int = 0
    
    class Config:
        from_attributes = True


class VectorStoreRequest(BaseModel):
    """Request to store data in vector database"""
    workspace_id: int
    file_type: str
    
    @field_validator('file_type')
    @classmethod
    def validate_file_type(cls, v):
        if v not in ['buyers', 'visitors']:
            raise ValueError('File type must be buyers or visitors')
        return v
class ColumnMappingCreate(BaseModel):
    file_type: str
    mapping: Dict[str, Optional[str]]  # {"csv_column": "standard_field" or null}
    
    @field_validator('file_type')
    @classmethod
    def validate_file_type(cls, v):
        """Validate file type"""
        allowed_types = ['buyers', 'visitors']
        if v not in allowed_types:
            raise ValueError(f'File type must be one of: {", ".join(allowed_types)}')
        return v
    
    @field_validator('mapping')
    @classmethod
    def validate_mapping(cls, v):
        """Validate mapping structure"""
        if not isinstance(v, dict):
            raise ValueError('Mapping must be a dictionary')
        
        # All values must be strings or None
        for key, value in v.items():
            if value is not None and not isinstance(value, str):
                raise ValueError(f'Mapping value for {key} must be a string or null')
        
        return v


class ColumnMappingResponse(BaseModel):
    success: bool
    mapping: Optional[Dict[str, Optional[str]]]
    file_type: str
    mapped_columns: int
    
    class Config:
        from_attributes = True
class AIQueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Validate AI query"""
        v = v.strip()
        if len(v) < 3:
            raise ValueError('Query must be at least 3 characters long')
        if len(v) > 1000:
            raise ValueError('Query must not exceed 1000 characters')
        return v

class AIQueryResponse(BaseModel):
    response: str
    confidence: Optional[float] = None