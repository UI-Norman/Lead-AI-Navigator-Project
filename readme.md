# Lead AI Navigator Platform

## Overview

Lead Navigator AI is a an analytics platform designed for marketing teams and data analysts to process, analyze, and extract insights from buyers and visitors data. The platform combines powerful data processing capabilities with AI-powered analytics, providing real-time insights, advanced filtering, and intelligent recommendations.

### Key Highlights
- **Dual Data Analysis**: Separate analytics for buyers (revenue/conversion) and visitors (traffic/demographics)
- **AI-Powered Insights**: RAG-based query system using Google Gemini for intelligent data analysis
- **Multi-Workspace Support**: Organize projects with isolated workspaces and team collaboration
- **Advanced Filtering**: 13+ demographic, financial, and behavioral filters
- **Real-Time Processing**: Handle files up to 2GB with intelligent chunking
- **Audit Trail**: Complete activity logging for compliance and security

## Features

### Authentication & Security
- **Password-based login** with bcrypt hashing
- **Magic link authentication** (passwordless login via email)
- **JWT token management** with configurable expiry
- **Role-based access control** (Owner, Analyst, Viewer)
- **Session management** with automatic timeout
- **Audit logging** for all user actions

### Data Management
- **File Upload System**
  - Support for CSV, TSV, GZIP formats
  - Automatic encoding detection (UTF-8, Latin-1, CP1252, etc.)
  - Intelligent separator detection 
  - Chunked reading for large files (>10MB)
  - File size limit: 2GB
  - Row limit: 16,000 (browser storage optimization)

- **Data Processing**
  - Automatic column normalization
  - Missing value handling
  - Duplicate detection and removal
  - Data type inference
  - Real-time preview 

### Buyers Analytics Dashboard
- **Revenue Metrics** (if revenue data exists):
  - Total Revenue
  - Average Order Value (AOV)
  - Customer Lifetime Value (90-day LTV)
  - Gross vs Refunded Revenue
  - Customer Acquisition Cost (CAC)
  - Conversion Rate 

- **Demographic KPIs** (for non-revenue data):
  - Total Buyers
  - Unique Buyers
  - Gender Distribution (Male/Female/Other %)
  - Repeat Buyer Rate
  - Top State/Location
  - Top Income Range
  - Most Common Age Range

- **Visualizations**:
  - Conversions Over Time 
  - Top 15 Channels Performance
  - Custom date range analysis

### 👥 Visitors Analytics Dashboard
- **Demographic Overview**:
  - Total Visitors
  - Unique Visitors
  - Gender Split
  - Repeat Visitor Rate

- **Visualizations**:
  - New vs Returning Visitors 
  - Top 15 Channels
  - Gender Distribution 
  - Age Distribution 
  - Income Range Distribution 
  - Top 15 States 

### Advanced Filtering System

**Filter Categories**:

1. **Date Range**: Custom start/end dates
2. **Channel/Source**: Traffic source 
3. **Campaign**: Marketing campaign names
4. **Gender**: Male, Female, Other
5. **Age Range**: Age groups
6. **Income Range**: Household income levels
7. **Net Worth**: Wealth brackets
8. **Credit Rating**: Credit score tiers
9. **Homeowner Status**: Own/Rent
10. **Marital Status**: Married/Single
11. **Children**: Has children (Yes/No)
12. **State**: Geographic location
13. **Custom**: Any categorical column

**Filter Features**:
- Multi-select for all filters
- Real-time chart updates
- Filter persistence (save/load)
- Active filter badges
- One-click reset

### AI Assistant (RAG-Powered)
- **Vector-Based Search**: Stores data summaries in memory
- **Context-Aware Responses**: Answers based on uploaded data
- **Query Types**:
  - Demographic analysis 
  - Geographic insights 
  - Revenue questions
  - Trend analysis
  - Custom aggregations

- **Features**:
  - Gemini 2.5 Flash model
  - Real-time data retrieval
  - Chat history
  - Error handling with fallbacks

### Workspace Management
- **Multi-Workspace Support**:
  - Create unlimited workspaces
  - Isolate projects/clients
  - Switch between workspaces
  - Rename/delete workspaces

- **Team Collaboration**:
  - Invite users via email
  - Role assignment (Owner/Analyst/Viewer)
  - Invitation expiry (7 days)
  - Accept/reject invitations

- **Audit Trail**:
  - User login/logout
  - File uploads
  - Filter applications
  - Workspace changes
  - Invitation events
  - AI queries

### 📈 Key Metrics & KPIs
**Automatically Calculated**:
- Total Revenue 
- Conversion Rate 
- Average Order Value 
- Repeat Customer Rate 
- 90-Day Lifetime Value 
- Customer Acquisition Cost 
- New vs Returning 

## Tech Stack

### Backend (FastAPI)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI| High-performance async API |
| **Database** | SQLite + SQLAlchemy | Relational data storage |
| **Authentication** | JWT + bcrypt | Secure token-based auth |
| **Email** | SMTP (Gmail) | Magic link delivery |
| **AI Engine** | Google Gemini API | RAG-powered analytics |
| **Data Processing** | Pandas + NumPy | CSV parsing & analytics |
| **Validation** | Pydantic | Request/response validation |

### Frontend (Dash)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Dash| Reactive UI framework |
| **Styling** | Bootstrap| Modern UI components |
| **Charts** | Plotly| Interactive visualizations |
| **State Management** | Dash Stores | Browser-based state |
| **Routing** | Dash Location | Multi-page navigation |
| **Tables** | Dash DataTable | Sortable/filterable tables |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| **Deployment** | AWS Elastic Beanstalk |
| **Web Server** | Gunicorn (backend) |
| **WSGI** | Uvicorn (FastAPI) |
| **Environment** | Python|
| **Package Manager** | pip + virtualenv |

---

## System Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DASH FRONTEND (Port 8050)                        │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐   │
│  │   Login/     │  │   Buyers     │  │   Visitors   │  │   Admin    │   │
│  │   Register   │  │  Dashboard   │  │  Analytics   │  │   Panel    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬─────┘   │
│         │                 │                 │                 │         │
│         └─────────────────┴─────────────────┴─────────────────┘         │
│                                   │                                     │
│         ┌─────────────────────────┴─────────────────────────┐           │
│         │                                                   │           │
│         ▼                                                   ▼           │
│  ┌─────────────────┐                              ┌──────────────────┐  │
│  │  Dash Callbacks │                              │   Dash Stores    │  │
│  ├─────────────────┤                              ├──────────────────┤  │
│  │ • Upload        │                              │ • auth-token     │  │
│  │ • Auth          │                              │ • buyers-data    │  │
│  │ • Dashboard     │◄────────────────────────────►│ • visitors-data  │  │
│  │ • AI Assistant  │     Session Management       │ • user-filters   │  │
│  │ • Workspace     │                              │ • workspaces     │  │
│  │ • Filters       │                              └──────────────────┘  │
│  └─────────┬───────┘                                                    │
│            │                                                            │
└────────────┼────────────────────────────────────────────────────────────┘
             │
             │ HTTP/HTTPS
             │ (API Calls)
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND (Port 8000)                        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        API ENDPOINTS                             │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │  /auth/login          │ POST  │ User authentication              │   │
│  │  /auth/register       │ POST  │ New user registration            │   │
│  │  /auth/magic-link     │ POST  │ Passwordless login               │   │
│  │  /workspaces          │ GET   │ List user workspaces             │   │
│  │  /workspaces/{id}     │ GET   │ Get workspace details            │   │
│  │  /workspaces          │ POST  │ Create new workspace             │   │
│  │  /workspaces/{id}     │ PUT   │ Update workspace                 │   │
│  │  /workspaces/{id}     │ DELETE│ Delete workspace                 │   │
│  │  /workspaces/{id}/    │ POST  │ Upload CSV file                  │   │
│  │    upload             │       │                                  │   │
│  │  /ai/query            │ POST  │ AI-powered data query            │   │
│  │  /workspaces/{id}/    │ GET   │ List uploaded files              │   │
│  │    uploads            │       │                                  │   │
│  │  /workspaces/{id}/    │ POST  │ Save column mapping              │   │
│  │    column-mapping     │       │                                  │   │
│  │  /workspaces/{id}/    │ GET   │ Get audit logs                   │   │
│  │    audit-logs         │       │                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                   │                                     │
│         ┌─────────────────────────┼─────────────────────────┐           │
│         │                         │                         │           │
│         ▼                         ▼                         ▼           │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐      │
│  │  auth.py    │          │  crud.py    │          │ ai_assistant│      │
│  ├─────────────┤          ├─────────────┤          ├─────────────┤      │
│  │ • JWT       │          │ • DB CRUD   │          │ • RAG       │      │
│  │ • bcrypt    │          │ • User Mgmt │          │ • Gemini    │      │
│  │ • Magic Link│          │ • Workspace │          │ • Vector    │      │
│  │ • Token Mgmt│          │ • Audit Log │          │   Store     │      │
│  └─────────────┘          └─────────────┘          └─────────────┘      │
│         │                         │                         │           │
│         └─────────────────────────┼─────────────────────────┘           │
│                                   │                                     │
│                                   ▼                                     │
│         ┌───────────────────────────────────────────────────┐           │
│         │                  DATABASE LAYER                   │           │
│         │            (SQLAlchemy + SQLite)                  │           │
│         ├───────────────────────────────────────────────────┤           │
│         │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐   │           │
│         │  │   users     │  │ workspaces  │  │ uploads  │   │           │
│         │  ├─────────────┤  ├─────────────┤  ├──────────┤   │           │
│         │  │ id          │  │ id          │  │ id       │   │           │
│         │  │ email       │  │ name        │  │ filename │   │           │
│         │  │ hashed_pw   │  │ created_at  │  │ row_count│   │           │
│         │  │ full_name   │  └─────────────┘  │ filepath │   │           │
│         │  │ created_at  │                   └──────────┘   │           │
│         │  └─────────────┘                                  │           │
│         │                                                   │           │
│         │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐   │           │
│         │  │ invitations │  │  mappings   │  │audit_logs│   │           │
│         │  ├─────────────┤  ├─────────────┤  ├──────────┤   │           │
│         │  │ id          │  │ id          │  │ id       │   │           │
│         │  │ email       │  │ file_type   │  │ action   │   │           │
│         │  │ token       │  │ mapping_json│  │ details  │   │           │
│         │  │ expires_at  │  └─────────────┘  │timestamp │   │           │
│         │  └─────────────┘                   └──────────┘   │           │
│         └───────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                                │
│                                                                         │
│  ┌──────────────────┐          ┌──────────────────┐                     │
│  │  Google Gemini   │          │   SMTP Server    │                     │
│  │   API (2.5 Flash)│          │   (Gmail)        │                     │
│  ├──────────────────┤          ├──────────────────┤                     │
│  │ • RAG Queries    │          │ • Magic Links    │                     │
│  │ • AI Insights    │          │ • Invitations    │                     │
│  │ • Context Search │          │ • Notifications  │                     │
│  └──────────────────┘          └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

**1. User Authentication Flow**
```
User → Login Form → POST /auth/login → JWT Token → Store in Browser → Access Dashboard
                                    ↓
                              Audit Log Entry
```

**2. File Upload Flow**
```
User → Select File → Auto-detect Type → Upload → Backend Processing
                                                       ↓
                        ┌──────────────────────────────┴──────────────────┐
                        │                                                 │
                        ▼                                                 ▼
                 Parse & Validate                              Store Metadata
                        ↓                                                 ↓
                 Store in Vector DB                            Database Record
                        ↓                                                 ↓
                 Return Preview                                    Audit Log
                        │                                                 │
                        └─────────────────────┬───────────────────────────┘
                                              ↓
                                      Display Dashboard
```

**3. AI Query Flow**
```
User → Ask Question → POST /ai/query → Retrieve Context from Vector Store
                                              ↓
                                    Build Enhanced Prompt
                                              ↓
                                    Call Gemini API
                                              ↓
                                    Parse Response
                                              ↓
                                    Display in Chat
```

**4. Filter Application Flow**
```
User → Select Filters → Apply → Update URL State → Trigger Callbacks
                                                           ↓
                                                  Filter DataFrame
                                                           ↓
                                                  Recalculate KPIs
                                                           ↓
                                                  Update Charts
                                                           ↓
                                                  Show Badge Count
```

## Installation & Setup

### Prerequisites
- Python
- pip (package manager)
- Virtual environment tool (venv/virtualenv)
- SMTP credentials (Gmail recommended)
- Google Gemini API key

### Step 1: Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Frontend Setup

```bash
# Navigate to frontend (new terminal)
cd frontend

# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Step 7: Access Application

1. Open browser: `http://localhost:8050`
2. Register new account
3. Login with credentials or magic link
4. Upload sample CSV data
5. Explore dashboards!

---

## Project Structure

```
lead-navigator-ai/
│
├── backend/                       # FastAPI Backend
│   ├── main.py                    # API endpoints & routing
│   ├── models.py                  # SQLAlchemy ORM models
│   ├── schemas.py                 # Pydantic validation schemas
│   ├── crud.py                    # Database CRUD operations
│   ├── auth.py                    # Authentication logic
│   ├── ai_assistant.py            # RAG & AI query engine
│   ├── database.py                # Database connection
│   ├── schemas.py                 # schema
│   ├── requirements.txt           # Backend dependencies
│   ├── .env                       # Backend environment variables
│   └── data/                      # SQLite database storage
│       └── database.db
│
├── frontend/                      # Dash Frontend
│   ├── app.py                     # Main Dash app & routing
│   │
│   ├── callbacks/                 # Dash callback modules
│   │   ├── upload_callbacks.py    # File upload handling
│   │   ├── auth_callbacks.py      # Login/register callbacks
│   │   ├── dashboard_callbacks.py # KPI & chart updates
│   │   ├── ai_callbacks.py        # AI assistant interface
│   │   ├── workspace_callbacks.py  # Workspace management
│   │   ├── visitor_analytics_callbacks.py # Visitors page
│   │   └── mapping_callbacks.py  # Column mapping 
│   │
│   ├── components/                # Reusable UI components
│   │   ├── layout.py             # Page layouts & structure
│   │   ├── charts.py             # Plotly chart creation
│   │   └── auth.py               # Auth page layouts
│   │
│   ├── utils/                     # Helper utilities
│   │   ├── metrics.py            # KPI calculation functions
│   │   └── csv_processor.py     # CSV parsing helpers
│   │
│   ├── requirements.txt           # Frontend dependencies
│   └── .env                       # Frontend environment variables
│
├── uploads/                       # Uploaded file storage
└── Readme.md
```

---

## Security & Authentication

### Password Security
- **Hashing Algorithm**: bcrypt with auto-generated salts
- **Password Requirements**:
  - Minimum 8 characters
  - Maximum 128 characters
  - No complexity requirements (configurable)
- **Storage**: Only hashed passwords stored in database
- **Verification**: Constant-time comparison to prevent timing attacks

### JWT Token Management
- **Algorithm**: HS256 (HMAC with SHA-256)
- **Expiry**: 30 days (43,200 minutes) 
- **Storage**: Browser localStorage
- **Transmission**: Query parameter 

### Magic Link Authentication
- **Token Generation**: 32-byte URL-safe random string
- **Expiry**: 5 minutes
- **One-Time Use**: Token marked as used after verification
- **Delivery**: SMTP email with HTML template
- **Flow**:
  1. User enters email
  2. Backend generates token + access_token
  3. Email sent with magic link
  4. User clicks link → Auto-login
  5. Token marked as used

### Role-Based Access Control (RBAC)
| Role | Permissions |
|------|-------------|
| **Owner** | Full access: create/delete workspaces, invite users, all features |
| **Analyst** | View/analyze data, apply filters, use AI assistant |
| **Viewer** | Read-only access to dashboards and reports |

### Audit Logging
**Logged Events**:
- User registration
- Login/logout
- File uploads
- Workspace creation/deletion/rename
- Invitation sent/accepted
- AI queries
- Filter applications
- Column mapping changes

**Log Fields**:
- User ID
- Workspace ID
- Action type
- Timestamp (UTC)
- Details (JSON)

### Data Protection
- **In Transit**: HTTPS (enforced in production)
- **At Rest**: SQLite database with file-level permissions
- **Browser Storage**: Encrypted tokens in localStorage
- **File Uploads**: Validated file types, size limits
- **Input Validation**: Pydantic schemas on all endpoints

---

## Key Metrics & Calculations

### Revenue Metrics (Buyers with Revenue Data)

1. Total Revenue

2. Average Order Value (AOV)

3. Conversion Rate

4. Repeat Customer Rate

5. 90-Day Lifetime Value (LTV)

6. Customer Acquisition Cost (CAC)

### Demographic Metrics (Buyers without Revenue)

1. Total Buyers

2. Unique Buyers

3. Gender Distribution

4. Top Demographics

### Visitor Metrics

1. Total Visitors

2. Unique Visitors

3. New vs Returning

## Troubleshooting

### Common Issues & Solutions

#### 1. Backend Won't Start

**Solutions**:
```bash
# Ensure virtual environment is activated
cd backend
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Check Python version
python --version  # Should be 3.9+
```

#### 2. Database Connection Error

**Solutions**:
```bash
# Create data directory
mkdir -p backend/data

# Initialize database
cd backend
```
#### 3. Frontend Can't Connect to Backend

**Check**:
1. Backend is running: `curl http://localhost:8000`
2. Frontend `.env` has correct `API_BASE_URL`
3. No firewall blocking port 8000
4. CORS headers allow localhost:8050

#### 4. Magic Link Not Working

**Check**:
1. SMTP credentials in backend `.env`
2. Gmail "App Password" (not regular password)
3. "Less Secure Apps" enabled in Gmail

**Enable Gmail App Passwords**:
1. Go to Google Account Settings
2. Security → 2-Step Verification
3. App Passwords → Generate
4. Copy password to `.env` as `SMTP_PASS`

**Built the Lead Navigator AI**