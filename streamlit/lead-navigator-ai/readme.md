# Lead Navigator AI - Buyers Analytics Dashboard

## Overview

- A Streamlit-based analytics platform for analyzing buyer behavior, demographic segmentation, and conversion metrics. 
- Built for marketing teams to identify high-converting audience segments and optimize targeting strategies.

## Key Features

### Core Analytics
- **Real-time Dashboard** : Interactive metrics with filtering
- **Conversion Analysis** : Track performance across buyer combos
- **Demographic Insights** : Age, income, location, and behavior patterns
- **Trend Visualization** : Plotly-powered interactive charts

### Data Management
- **Smart Upload System** : Auto-parse CSV/Excel with validation
- **Upload History** : Track and reload previous datasets
- **Data Caching** : Fast retrieval with hash-based deduplication
- **Export Tools** : Download filtered segments and reports

### Segmentation Tools
- **Segment Builder** : Multi-attribute filtering engine
- **Saved Segments** : Store and compare custom audiences
- **Side-by-Side Comparison** : Compare up to 4 segments simultaneously
- **Performance Analytics** : Identify segments by volume or conversion

### User Management
- **Role-Based Access** : Owner, Analyst, Viewer permissions
- **Magic Link Login** : Passwordless authentication option
- **Audit Logging** : Track all user actions and data changes
- **User Invitations** : Email-based onboarding

### Advanced Analysis
- **Buyer Deep Dive** : Drill down into individual combo performance
- **Attribute Explorer** : Visual breakdown of demographic distributions
- **Search & Filter** -: Global search across all data columns

## Project Structure

```
lead-navigator-ai-buyers-data/
│
├── app.py                                
├── requirements.txt               
├── README.md                    
│
├── .streamlit/                    
│   └── secrets.toml
│   └── config.toml                            
│
└── buyers_dashboard.db            
```

### File Descriptions

| File | Purpose |
|------|---------|
| `app.py` | Main application with all UI, logic, and database functions |
| `requirements.txt` | Python package dependencies |
| `config.toml` | Server settings (upload limits, CORS, XSRF protection) |
| `buyers_dashboard.db` | SQLite database storing users, uploads, segments, audit logs |

## System Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      STREAMLIT FRONTEND                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │   Home   │  │ Segments │  │  Deep    │  │  Admin   │     │
│  │Dashboard │  │ Builder  │  │  Dive    │  │  Panel   │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       │             │             │             │           │
│       └─────────────┴─────────────┴─────────────┘           │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Session State Management                  │ │
│  │  • authenticated  • user_email  • user_role            │ │
│  │  • data  • saved_segments  • current_file_hash         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────┐  ┌────────────────┐  ┌───────────────┐   │
│  │ Authentication│  │ Data Processing│  │  Visualization│   │
│  │   Module      │  │    Engine      │  │    Engine     │   │
│  │               │  │                │  │               │   │
│  │ • Login       │  │ • CSV Parser   │  │ • Plotly      │   │
│  │ • Magic Links │  │ • Filtering    │  │ • Charts      │   │
│  │ • Password    │  │ • Aggregation  │  │ • Metrics     │   │
│  │ • Audit Log   │  │ • Caching      │  │ • Tables      │   │
│  └───────┬───────┘  └───────┬────────┘  └───────────────┘   │
│          │                  │                               │
└──────────┼──────────────────┼───────────────────────────────┘
           │                  │
           ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   DATA LAYER (SQLite DB)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  buyers_dashboard.db                                   │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐   │ │ 
│  │  │    users     │  │upload_history│  │ audit_log   │   │ │
│  │  ├──────────────┤  ├──────────────┤  ├─────────────┤   │ │
│  │  │ id           │  │ id           │  │ id          │   │ │
│  │  │ email        │  │ user_email   │  │ user_email  │   │ │
│  │  │ password     │  │ filename     │  │ action      │   │ │
│  │  │ role         │  │ upload_date  │  │ timestamp   │   │ │
│  │  │ created_at   │  │ row_count    │  │ details     │   │ │
│  │  │ last_login   │  │ file_data    │  └─────────────┘   │ │
│  │  └──────────────┘  └──────────────┘                    │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐                    │ │
│  │  │magic_links   │  │saved_segments│                    │ │
│  │  ├──────────────┤  ├──────────────┤                    │ │
│  │  │ id           │  │ id           │                    │ │
│  │  │ email        │  │ user_email   │                    │ │
│  │  │ token        │  │ segment_name │                    │ │
│  │  │ created_at   │  │ filters      │                    │ │
│  │  │ expires_at   │  │ created_at   │                    │ │
│  │  │ used         │  └──────────────┘                    │ │
│  │  └──────────────┘                                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. **Frontend Layer (Streamlit UI)**
- **Pages**: Home, Top Combos, Segment Builder, Deep Dive, Uploads, Admin
- **Navigation**: Sidebar radio buttons with role-based visibility

#### 2. **Application Layer**
- **Session Management**: Stores user state, data cache, filters
- **Authentication Engine**: Login, magic links, password hashing (SHA-256)
- **Data Processing**: Pandas-based CSV parsing, filtering, aggregation
- **Visualization**: Plotly Express/Graph Objects for interactive charts
- **Audit System**: Logs all user actions with timestamps

#### 3. **Data Layer (SQLite)**
- **Tables**: core tables (users, uploads, logs, links, segments)
- **Indexing**: Primary keys with auto-increment

## Installation & Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Run the Application

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

### Step 3: Login

**Default credentials:**
**Signup**
**Magic Link**

## User Roles & Permissions

### Role Matrix

| Feature | Viewer 👁️ | Analyst  | Owner |
|---------|-----------|-----------|---------|
| **Viewing** |
| View Dashboards | ✅ | ✅ | ✅ |
| View Charts | ✅ | ✅ | ✅ |
| Search Data | ✅ | ✅ | ✅ |
| **Administration** |
| Invite Users | ❌ | ❌ | ✅ |

### Creating New Users

**Method 1: Self-Registration** (Default: Viewer role)
1. Go to "Create Account" tab on login page
2. Enter email and password
3. Submit

**Method 2: Admin Invitation** 
1. Login as Owner
2. Navigate to **Admin** > **User Management**
3. Enter user email and select role
4. System generates credentials
5. Copy and share securely

## Security & Authentication

### Authentication Methods

#### 1. **Password Authentication**
- SHA-256 hashed passwords
- Minimum 6 characters (8+ recommended)
- Stored in `users` table

#### 2. **Magic Link Login**
- Passwordless authentication
- 1-hour expiration
- Single-use tokens
- Stored in `magic_links` table

### Audit Logging

All actions are logged with:
- User email
- Action type (Login, Upload, Export, etc.)
- Timestamp
- Action details

View logs in **Admin Panel** > **Audit Log**


## Dashboard Pages

### 1. Home Dashboard 
**Purpose**: Overview of all buyer data with global filters

**Features:**
- Key metrics cards (Total Buyers, Top 50%, Best Combos)
- Global filters (Min Purchasers, Min Conversion, Combo Size)
- Search across all columns
- Demographic charts (Age, Income, State, Credit Rating)
- Buyer concentration analysis
- Export to CSV

**Use Case**: Quick insights and filtering before deep analysis

### 2. Top Combos
**Purpose**: Full ranked list of all combos

**Features:**
- Sortable table (by Rank, Conversion, Purchasers)
- Ascending/Descending order toggle
- Full dataset view with scroll

**Use Case**: Browse complete combo rankings

### 3. Segment Builder
**Purpose**: Create custom audience segments with filters

**Features:**
- Multi-select filters (Age, Income, Gender, State)
- Real-time segment metrics
- Preview filtered data
- Save segments with names
- Export segment data
- Compare up to 4 saved segments side-by-side

**Comparison Tools:**
- Metrics table (Purchasers, Conversion %, % of Total)
- Bar charts (Volume vs. Conversion)
- Filter details breakdown

**Use Case**: Identify high-value audience segments for targeting

### 4. Buyer Deep Dive 🔍
**Purpose**: Detailed analysis of individual combos

**Features:**
- Slider to navigate through combos
- Quick jump to specific rank
- Performance comparison charts vs. surrounding ranks
- Conversion rate trend analysis
- Complete attribute breakdown
- Demographic distribution charts

**Insights:**
- Visitor/Purchaser performance vs. peers
- Conversion percentile ranking
- Attribute values with dataset distributions
- Visual highlighting of current combo

**Use Case**: Understand what makes specific combos successful

### 5. Uploads 
**Purpose**: Manage upload history and reload datasets

**Features:**
- Upload history table (Filename, Date, Row Count)
- Search by filename
- View stored data
- Load previous uploads as current dataset
- Export stored data
- Clear current data
- Upload new files

**Use Case**: Track data versions and reload previous analyses

### 6. Admin Panel
**Purpose**: User management and system administration (Owner only)

## User Roles

### Owner
- Full access to all features
- User management
- Invite new users
- View audit logs
- Manage roles

### Analyst
- View and analyze data
- Create and save segments
- Upload new data files
- Export data

### Viewer
- View dashboards
- View saved segments
- Limited export capabilities

## Default Filters

On app load, the following filters are automatically applied:
- **Combo Size**: 2 to 5
- **Minimum Purchasers**: 10
- **Minimum Conversion Rate**: 4.0%

These can be adjusted using the global filters in the sidebar.

## Key Metrics

### KPIs Tracked
1. Total Buyers (in date range)
2. % of Buyers from Top 50 Combos
3. Highest Converting Combo
4. Best Volume Combo

### Analytics
- Buyer concentration charts
- Single-attribute leaderboards
- Credit rating distributions
- State-wise buyer analysis


**Tabs:**

#### **Users Tab**
- User list with roles
- Create new users
- Auto-generate secure passwords
- Copy credentials
- Email invitations

#### **Audit Log Tab**
- User activity tracking
- Timestamp and details
- Filter by user/action

#### **System Info Tab**
- Total users count
- Total uploads
- Total audit logs

**Use Case**: Administer users and monitor system activity

## Troubleshooting

### Common Issues

#### **1. Can't Login**
**Symptoms**: Invalid email/password error

**Solutions:**
- Verify email format (must include @ and .)
- Passwords are case-sensitive
- Use "Create Account" tab for first-time users

#### **2. Upload Fails**
**Symptoms**: Error loading file

**Solutions:**
- Check for metadata rows 

#### **3. Database Locked**
**Symptoms**: "Database is locked" error

**Solutions:**
- Close other Streamlit instances

## Testing

### Manual Testing Checklist

- Login with default credentials
- Create new user account
- Upload CSV
- Apply global filters
- Search for demographic value
- Create and save segment
- Compare 2+ segments
- Navigate to specific combo in Deep Dive
- Export data to CSV
- View upload history
- Check audit logs (Owner only)
- Invite new user (Owner only)
- Test magic link login
- Logout and re-login

## Acknowledgments

- **Streamlit**:Built with [Streamlit](https://streamlit.io/).
