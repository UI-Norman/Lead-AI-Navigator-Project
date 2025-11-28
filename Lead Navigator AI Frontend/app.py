import dash
from dash import html, dcc, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
import requests
import os
from dotenv import load_dotenv
import logging
import jwt
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from callbacks.visitor_analytics_callbacks import register_visitor_analytics_callbacks

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import callback modules
from callbacks.upload_callbacks import register_upload_callbacks
from callbacks.auth_callbacks import register_auth_callbacks
from callbacks.dashboard_callbacks import register_dashboard_callbacks
from callbacks.workspace_callbacks import register_workspace_callbacks
from callbacks.ai_callbacks import register_ai_callbacks

# Load environment variables
load_dotenv(dotenv_path=".env")

# Get API URL from environment
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise EnvironmentError("API_BASE_URL is required in .env file")

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css"
    ],
    suppress_callback_exceptions=True  
)

# Enforce UTF-8 encoding in the browser
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Expose server for deployment
server = app.server
application = server

# Register callbacks from modules
register_upload_callbacks(app)
register_auth_callbacks(app)
register_dashboard_callbacks(app)
register_workspace_callbacks(app)
register_ai_callbacks(app)
register_visitor_analytics_callbacks(app)

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='auth-token', storage_type='local'),
    dcc.Store(id='current-workspace', storage_type='local'),
    dcc.Store(id='current-user', storage_type='session'),
    dcc.Store(id='buyers-data', storage_type='local'),  
    dcc.Store(id='visitors-data', storage_type='local'), 
    dcc.Store(id='upload-trigger', storage_type='memory'),
    dcc.Store(id='recent-uploads-data', storage_type='local'),
    dcc.Store(id='recent-uploads', storage_type='local'),
    dcc.Store(id='user-filters', storage_type='session'),
    dcc.Download(id='download-data'),
    html.Div(id="login-feedback", style={'display': 'none'}),
    html.Div(id="magic-link-feedback", style={'display': 'none'}),
    html.Div(id="register-feedback", style={'display': 'none'}),
    html.Div(id='page-content')
])

# ============================================================================
# ROUTING CALLBACK
# ============================================================================

@app.callback(
    [Output('page-content', 'children'),
     Output('auth-token', 'data', allow_duplicate=True)],
    [Input('url', 'pathname'),
     Input('url', 'search'),
     Input('auth-token', 'data')],
    prevent_initial_call='initial_duplicate'
)
def display_page(pathname, search, token):
    logger.debug(f"Routing: pathname={pathname}, search={search}")

    # ====================================================================
    # MAGIC LINK VERIFICATION
    # ====================================================================
    if pathname == '/auth/verify' and search:
        if search.startswith('?'):
            search = search[1:]
        query = parse_qs(search)
        magic_token = query.get('token', [None])[0]

        if magic_token:
            try:
                logger.info(f"Verifying magic link token: {magic_token[:20]}...")

                resp = requests.get(
                    f"{API_BASE_URL}/auth/verify-magic-link?token={magic_token}",
                    timeout=10
                )

                logger.debug(f"Verify response: {resp.status_code} - {resp.text[:200]}")

                if resp.status_code == 200:
                    data = resp.json()
                    access_token = data.get('access_token')

                    if access_token:
                        logger.info("Magic link verified → Auto login success")
                        return create_dashboard(access_token), access_token
                    else:
                        logger.warning("Magic link verified but no access_token returned")
                        return html.Div([
                            create_login_form(),
                            dbc.Alert("Login failed: No access token received.", color="danger")
                        ]), no_update
                else:
                    try:
                        err_detail = resp.json().get('detail', 'Unknown error')
                    except:
                        err_detail = f"HTTP {resp.status_code}"

                    logger.warning(f"Magic link verification failed: {err_detail}")
                    return html.Div([
                        create_login_form(),
                        dbc.Alert(f"Magic link error: {err_detail}", color="danger")
                    ]), no_update

            except requests.exceptions.Timeout:
                logger.error("Magic link verification timed out")
                return html.Div([
                    create_login_form(),
                    dbc.Alert("Request timed out. Is backend running?", color="danger")
                ]), no_update

            except Exception as e:
                logger.error(f"Magic link verify error: {str(e)}")
                return html.Div([
                    create_login_form(),
                    dbc.Alert("Connection error. Please try again.", color="danger")
                ]), no_update

        return html.Div([
            create_login_form(),
            dbc.Alert("Invalid magic link: No token found.", color="danger")
        ]), no_update

    # ====================================================================
    # PUBLIC PAGES
    # ====================================================================
    if pathname == '/register':
        return create_register_form(), no_update

    # ====================================================================
    # PROTECTED PAGES - Require Auth
    # ====================================================================
    if not token:
        logger.debug("No token → Redirect to login")
        return create_login_form(), no_update

    # Validate token with /users/me
    try:
        resp = requests.get(f"{API_BASE_URL}/users/me", params={"token": token}, timeout=5)
        if resp.status_code != 200:
            logger.warning(f"Invalid token: {resp.status_code}")
            return create_login_form(), None
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return create_login_form(), None

    # ====================================================================
    # AUTHENTICATED ROUTES
    # ====================================================================
    if pathname == '/':
        return create_dashboard(token), no_update
    elif pathname == '/uploads':
        return create_uploads_page(token), no_update
    elif pathname == '/visitors-analytics':  # ✅ NEW ROUTE
        return create_visitors_analytics_page(token), no_update
    elif pathname == '/admin':
        return create_admin_page(), no_update

# ============================================================================
# PAGE LAYOUTS
# ============================================================================

def create_login_form():
    """Create login form with clear instructions"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H2("Lead Navigator AI", className="text-center mb-4"),
                    html.P("Sign in to your account", className="text-muted text-center mb-4"),
                    
                    dbc.Card([
                        dbc.CardBody([
                            dbc.Form([
                                dbc.Label("Email", className="fw-bold"),
                                dbc.Input(
                                    id="login-email",
                                    type="email",
                                    placeholder="Enter your email",
                                    className="mb-3"
                                ),
                                
                                dbc.Label("Password", className="fw-bold"),
                                dbc.Input(
                                    id="login-password",
                                    type="password",
                                    placeholder="Enter your password",
                                    className="mb-3"
                                ),
                                
                                dbc.Button(
                                    [html.I(className="bi bi-box-arrow-in-right me-2"), "Sign In"],
                                    id="login-button",
                                    color="primary",
                                    className="w-100 mb-3",
                                    n_clicks=0
                                ),
                                
                                html.Div(id="login-feedback", className="mt-2 mb-3"),
                                
                                html.Div([
                                    html.Hr(className="my-3"),
                                    html.P("OR", className="text-center text-muted small mb-3")
                                ]),
                                
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="bi bi-magic me-2 text-primary"),
                                            html.Strong("Passwordless Login", className="text-primary")
                                        ], className="mb-2"),
                                        html.P([
                                            html.Small([
                                                "Already have an account? Get a magic link sent to your email for instant login without typing your password.",
                                                html.Br(),
                                                html.Strong("Note: ", className="text-warning"),
                                                "You must register first before using magic link."
                                            ], className="text-muted")
                                        ], className="mb-3"),
                                        dbc.Button(
                                            [html.I(className="bi bi-envelope-paper me-2"), "Send Magic Link"],
                                            id="magic-link-button",
                                            color="info",
                                            outline=True,
                                            className="w-100",
                                            n_clicks=0
                                        ),
                                    ])
                                ], className="bg-light border-0 mb-3"),
                                
                                html.Div(id="magic-link-feedback", className="mt-2 mb-3"),
                                
                                html.Div([
                                    html.Hr(className="my-3"),
                                    html.P([
                                        "Don't have an account? ",
                                        html.A("Create one now", href="/register", className="fw-bold text-decoration-none")
                                    ], className="text-center mb-0")
                                ])
                            ])
                        ])
                    ], className="shadow")
                ], className="mt-5")
            ], width=5)
        ], justify="center")
    ], fluid=True)

def create_register_form():
    """Create registration form"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H2("Create Account", className="text-center mb-4"),
                    html.P("Join Lead Navigator AI", className="text-center text-muted mb-4"),
                    
                    dbc.Card([
                        dbc.CardBody([
                            dbc.Form([
                                dbc.Label("Full Name"),
                                dbc.Input(
                                    id="register-name",
                                    type="text",
                                    placeholder="Enter your full name",
                                    className="mb-3"
                                ),
                                
                                dbc.Label("Email"),
                                dbc.Input(
                                    id="register-email",
                                    type="email",
                                    placeholder="Enter your email",
                                    className="mb-3"
                                ),
                                
                                dbc.Label("Password"),
                                dbc.Input(
                                    id="register-password",
                                    type="password",
                                    placeholder="Choose a password (min 8 characters)",
                                    className="mb-3"
                                ),
                                
                                dbc.Button(
                                    "Create Account",
                                    id="register-button",
                                    color="primary",
                                    className="w-100 mb-3",
                                    n_clicks=0
                                ),
                                
                                html.Div(
                                    html.A("Already have an account? Sign in", href="/", id="sign-in-link"),
                                    className="text-center mt-3"
                                ),
                                
                                html.Div(id="register-feedback", className="mt-3")
                            ])
                        ])
                    ], className="shadow")
                ], className="mt-5")
            ], width=4)
        ], justify="center")
    ], fluid=True)

def create_dashboard(token):
    """Create main dashboard - ONLY FOR BUYERS DATA"""
    # Fetch user data
    try:
        response = requests.get(f"{API_BASE_URL}/users/me?token={token}", timeout=5)
        if response.status_code == 200:
            user_data = response.json()
            user_name = user_data.get('full_name', 'User')
        else:
            user_name = 'User'
    except:
        user_name = 'User'
    
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H1("🛒 Buyers Analytics Dashboard", className="mb-4"),
                dbc.Alert(f"🎉 Welcome {user_name}! You're successfully logged in.", color="success")
            ])
        ]),
        
        # File Upload Section - MOVED TO TOP
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-cart-fill me-2"),
                        "Upload Buyers Data"
                    ]),
                    dbc.CardBody([
                        # ✅ HIDDEN FILE TYPE - ALWAYS BUYERS
                        dcc.Dropdown(
                            id='file-type-dropdown',
                            value='buyers',  # Always buyers on dashboard
                            style={'display': 'none'}  # Hidden
                        ),
                        
                        # Upload Area
                        dcc.Upload(
                            id='upload-data',
                            children=html.Div([
                                html.I(className="bi bi-cloud-upload", style={"fontSize": "48px"}),
                                html.Br(),
                                html.H5("Drag and Drop or Click to Upload"),
                                html.P("Upload your buyers/customers data (CSV, TSV, GZIP)", className="text-muted")
                            ]),
                            style={
                                'width': '100%',
                                'height': '200px',
                                'lineHeight': '60px',
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '10px',
                                'textAlign': 'center',
                                'padding': '40px',
                                'cursor': 'pointer'
                            },
                            multiple=False
                        ),
                        html.Div(id='upload-status', className="mt-3"),
                        html.Div(id='upload-preview', className="mt-3")
                    ])
                ], className="shadow-sm mb-4")
            ], md=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Uploads"),
                    dbc.CardBody([
                        html.Div(id='recent-uploads-display')
                    ])
                ], className="shadow-sm")
            ], md=4)
        ]),
        
        # Dashboard Content - Will be hidden until data is uploaded
        html.Div(id='dashboard-content', children=[
            # KPI Cards
            dbc.Row([
                dbc.Col([html.Div(id='kpi-revenue')], md=3),
                dbc.Col([html.Div(id='kpi-conversion')], md=3),
                dbc.Col([html.Div(id='kpi-aov')], md=3),
                dbc.Col([html.Div(id='kpi-repeat-rate')], md=3),
            ]),
            dbc.Row([
                dbc.Col([html.Div(id='kpi-ltv')], md=3),
                dbc.Col([html.Div(id='kpi-gross')], md=3),
                dbc.Col([html.Div(id='kpi-cac')], md=3),
            ], className="mt-4"),
            
            # Chart 1: Conversions Over Time 
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-graph-up me-2"),
                            "Conversions/Traffic Over Time"
                        ]),
                        dbc.CardBody([
                            dcc.Graph(id='conversions-chart', style={'height': '500px'})
                        ])
                    ], className="shadow-sm")
                ], md=12)
            ], className="mt-4"),

            # Chart 2: Channel Performance (Full Width)
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-bar-chart me-2"),
                            "Top 15 Channels Performance"
                        ]),
                        dbc.CardBody([
                            dcc.Graph(id='channel-performance-chart', style={'height': '500px'})
                        ])
                    ], className="shadow-sm")
                ], md=12)
            ], className="mt-4"),
            
            # IMPROVED FILTERS
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-funnel me-2"),
                            "Filters"
                        ]),
                        dbc.CardBody([
                            # Date Range
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-calendar me-2"),
                                    "Date Range"
                                ], className="fw-bold mb-2"),
                                dcc.DatePickerRange(
                                    id='date-range-picker',
                                    start_date_placeholder_text="Start Date",
                                    end_date_placeholder_text="End Date",
                                    className="mb-3",
                                    style={'width': '100%'}
                                ),
                            ], className="mb-3"),
                            
                            # Channel/Source
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-globe me-2"),
                                    "Channel/Source"
                                ], className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='channel-filter',
                                    multi=True,
                                    placeholder="Select Channels (e.g., Google, Facebook, Email)",
                                    className="mb-2"
                                ),
                                html.Small("Select one or more traffic sources to filter", className="text-muted d-block mb-3")
                            ], className="mb-3"),
                            
                            # Campaign
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-megaphone me-2"),
                                    "Campaign"
                                ], className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='campaign-filter',
                                    multi=True,
                                    placeholder="Select Campaigns (e.g., Summer Sale, Black Friday)",
                                    className="mb-2"
                                ),
                                html.Small("Select specific marketing campaigns", className="text-muted d-block mb-3")
                            ], className="mb-4"),
                            
                            html.Hr(),
                            html.H6("👥 Demographics", className="mb-3"),

                            # Gender filter
                            html.Div([
                                html.Label("Gender", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='gender-filter',
                                    multi=True,
                                    placeholder="Select Gender",
                                    className="mb-3"
                                ),
                            ], id='gender-filter-container', className="mb-3"),

                            # Age filter  
                            html.Div([
                                html.Label("Age Range", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='age-filter',
                                    multi=True,
                                    placeholder="Select Age Range",
                                    className="mb-3"
                                ),
                            ], id='age-filter-container', className="mb-3"),
                                
                            html.Hr(),
                            html.H6("💰 Financial", className="mb-3"),
                            
                            # Income Range
                            html.Div([
                                html.Label("Income Range", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='income-filter',
                                    multi=True,
                                    placeholder="Select Income",
                                    className="mb-3"
                                ),
                            ], id='income-filter-container', className="mb-3"),
                            
                            # Net Worth
                            html.Div([
                                html.Label("Net Worth", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='networth-filter',
                                    multi=True,
                                    placeholder="Select Net Worth",
                                    className="mb-3"
                                ),
                            ], id='networth-filter-container', className="mb-3"),
                            
                            # Credit Rating
                            html.Div([
                                html.Label("Credit Rating", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='credit-filter',
                                    multi=True,
                                    placeholder="Select Credit Rating",
                                    className="mb-4"
                                ),
                            ], id='credit-filter-container', className="mb-4"),
                            
                            html.Hr(),
                            html.H6("🏠 Lifestyle", className="mb-3"),
                            
                            # Homeowner
                            html.Div([
                                html.Label("Homeowner", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='homeowner-filter',
                                    multi=True,
                                    placeholder="Select Homeowner Status",
                                    className="mb-3"
                                ),
                            ], id='homeowner-filter-container', className="mb-3"),
                            
                            # Married
                            html.Div([
                                html.Label("Married", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='married-filter',
                                    multi=True,
                                    placeholder="Select Marital Status",
                                    className="mb-3"
                                ),
                            ], id='married-filter-container', className="mb-3"),
                            
                            # Children
                            html.Div([
                                html.Label("Children", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='children-filter',
                                    multi=True,
                                    placeholder="Select Children Status",
                                    className="mb-4"
                                ),
                            ], id='children-filter-container', className="mb-4"),
                            
                            html.Hr(),
                            html.H6("📍 Location", className="mb-3"),
                            
                            # State
                            html.Div([
                                html.Label("State", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='state-filter',
                                    multi=True,
                                    placeholder="Select State",
                                    className="mb-4"
                                ),
                            ], id='state-filter-container', className="mb-4"),
                            
                            # Action Buttons
                            html.Div([
                                dbc.Button([
                                    html.I(className="bi bi-check-circle me-2"),
                                    "Apply Filters"
                                ], id="apply-filters", color="primary", className="w-100 mb-2"),
                                dbc.Button([
                                    html.I(className="bi bi-arrow-clockwise me-2"),
                                    "Reset Filters"
                                ], id="reset-filters", color="secondary", outline=True, className="w-100 mb-2"),
                                dbc.Button([
                                    html.I(className="bi bi-save me-2"),
                                    "Save Filter Set"
                                ], id="save-filters", color="success", outline=True, className="w-100")
                            ], className="mt-4")
                        ])
                    ], className="shadow-sm", style={'maxHeight': '800px', 'overflowY': 'auto'})
                ], md=4),
                
                dbc.Col([
                    html.Div(id='data-table', children=[
                        # Default empty state
                        html.Div([
                            html.I(className="bi bi-table", style={"fontSize": "64px", "color": "#ccc"}),
                            html.H5("No Data Available", className="mt-3 text-muted"),
                            html.P("Upload buyers data to see the table", className="text-muted")
                        ], className="text-center py-5")
                    ])
                ], md=8),
            ], className="mt-4"),
        ], style={'display': 'none'}),  # HIDDEN BY DEFAULT
        
        # Navigation & Quick Actions
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Quick Actions"),
                        html.Hr(),
                        dbc.ButtonGroup([
                            dbc.Button([
                                html.I(className="bi bi-people me-2"),
                                "Visitors Analytics"  # ✅ NEW BUTTON
                            ], href="/visitors-analytics", color="info", outline=True),
                            dbc.Button([
                                html.I(className="bi bi-plus-circle me-2"),
                                "New Workspace"
                            ], id="open-create-workspace-modal", color="success", outline=True),
                            dbc.Button([
                                html.I(className="bi bi-gear me-2"),
                                "Admin"
                            ], href="/admin", color="secondary", outline=True),
                            dbc.Button([
                                html.I(className="bi bi-robot me-2"),
                                "AI Assistant"
                            ], id="open-ai-modal", color="info", outline=True),
                        ], className="me-2"),
                        dbc.Button([
                            html.I(className="bi bi-box-arrow-right me-2"),
                            "Logout"
                        ], id="logout", color="danger", outline=True, n_clicks=0)
                    ])
                ], className="shadow-sm")
            ])
        ], className="mt-4"),
        
        # Create Workspace Modal
        dbc.Modal([
            dbc.ModalHeader([
                html.I(className="bi bi-plus-circle me-2"),
                "Create New Workspace"
            ]),
            dbc.ModalBody([
                html.P("Create a new workspace to organize your projects separately.", className="text-muted mb-3"),
                dbc.Label("Workspace Name", className="fw-bold"),
                dbc.Input(
                    id="new-workspace-name-modal",
                    placeholder="e.g., Marketing Campaign 2024",
                    type="text",
                    className="mb-3"
                ),
                html.Div(id="create-workspace-modal-feedback")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="close-create-workspace-modal", color="secondary", className="me-2"),
                dbc.Button([
                    html.I(className="bi bi-check-circle me-2"),
                    "Create Workspace"
                ], id="confirm-create-workspace", color="success")
            ])
        ], id="create-workspace-modal", is_open=False),
        
        # AI Modal
        dbc.Modal([
            dbc.ModalHeader("AI Assistant"),
            dbc.ModalBody([
                html.Div(id='ai-chat-history', className="mb-3", style={"maxHeight": "300px", "overflowY": "auto"}),
                dbc.InputGroup([
                    dbc.Input(id='ai-query-input', placeholder="Ask a question about your data...", type="text"),
                    dbc.Button("Send", id="send-ai-query", color="primary")
                ])
            ]),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-ai-modal", className="ms-auto")
            )
        ], id="ai-modal", is_open=False)
    ], fluid=True, className="p-4")

def create_uploads_page(token):
    """Create uploads page with file type selector"""
    upload_history = []
    try:
        response = requests.get(f"{API_BASE_URL}/workspaces/1/uploads?token={token}", timeout=5)
        if response.status_code == 200:
            upload_history = response.json().get('uploads', [])
    except:
        pass
    
    return dbc.Container([
        html.H1("Upload Data", className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Upload CSV File"),
                    dbc.CardBody([
                        dbc.Label("Select File Type", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='file-type-dropdown',
                            options=[
                                {'label': '🛒 Buyers Data', 'value': 'buyers'},
                                {'label': '👥 Visitors Data', 'value': 'visitors'}
                            ],
                            value='buyers',
                            className="mb-3"
                        ),
                        
                        dcc.Upload(
                            id='upload-data',
                            children=html.Div([
                                html.I(className="bi bi-cloud-upload", style={"fontSize": "48px"}),
                                html.Br(),
                                html.H5("Drag and Drop or Click to Upload"),
                                html.P("Supports CSV, TSV, and GZIP files", className="text-muted")
                            ]),
                            style={
                                'width': '100%',
                                'height': '200px',
                                'lineHeight': '60px',
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '10px',
                                'textAlign': 'center',
                                'padding': '40px',
                                'cursor': 'pointer'
                            },
                            multiple=False
                        ),
                        html.Div(id='upload-status', className="mt-3"),
                        html.Div(id='upload-preview', className="mt-3")
                    ])
                ], className="shadow-sm mb-4")
            ], md=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Uploads"),
                    dbc.CardBody([
                        html.Div(id='recent-uploads-display')
                    ])
                ], className="shadow-sm")
            ], md=4)
        ])
    ], fluid=True, className="p-4")

def create_visitors_analytics_page(token):
    """Create dedicated visitors analytics page with COMPLETE metrics and charts"""
    return dbc.Container([
        html.H1("👥 Visitors Analytics Dashboard", className="mb-4"),
        
        # ✅ FILE UPLOAD SECTION AT THE TOP
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-cloud-upload me-2"),
                        "Upload Visitors Data"
                    ]),
                    dbc.CardBody([
                        # Hidden file type selector (always visitors)
                        dcc.Dropdown(
                            id='file-type-dropdown',
                            value='visitors',
                            style={'display': 'none'}
                        ),
                        
                        # Upload Area
                        dcc.Upload(
                            id='upload-data',
                            children=html.Div([
                                html.I(className="bi bi-cloud-upload", style={"fontSize": "48px"}),
                                html.Br(),
                                html.H5("Drag and Drop or Click to Upload"),
                                html.P("Upload your visitors data (CSV, TSV, GZIP)", className="text-muted")
                            ]),
                            style={
                                'width': '100%',
                                'height': '200px',
                                'lineHeight': '60px',
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '10px',
                                'textAlign': 'center',
                                'padding': '40px',
                                'cursor': 'pointer'
                            },
                            multiple=False
                        ),
                        html.Div(id='upload-status', className="mt-3"),
                        html.Div(id='upload-preview', className="mt-3")
                    ])
                ], className="shadow-sm mb-4")
            ], md=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Uploads"),
                    dbc.CardBody([
                        html.Div(id='recent-uploads-display')
                    ])
                ], className="shadow-sm")
            ], md=4)
        ]),
        
        # ✅ ANALYTICS CONTENT
        html.Div(id='visitors-analytics-content', children=[
            # ===================================================================
            # ✅ REVENUE KPIS - WITHOUT CONVERSION RATE (6 KPIs in 2 rows)
            # ===================================================================
            # html.H4("💰 Revenue & Performance Metrics", className="mb-3 mt-4"),
            
            # # ✅ ROW 1: Revenue, AOV, Repeat Rate (3 KPIs)
            # dbc.Row([
            #     dbc.Col([html.Div(id='visitor-kpi-revenue')], md=4),
            #     dbc.Col([html.Div(id='visitor-kpi-aov')], md=4),
            #     dbc.Col([html.Div(id='visitor-kpi-repeat')], md=4),
            # ], className="mb-4"),
            
            # # ✅ ROW 2: LTV, Gross/Refunded, CAC (3 KPIs)
            # dbc.Row([
            #     dbc.Col([html.Div(id='visitor-kpi-ltv')], md=4),
            #     dbc.Col([html.Div(id='visitor-kpi-gross')], md=4),
            #     dbc.Col([html.Div(id='visitor-kpi-cac')], md=4),
            # ], className="mb-4"),
            
            # html.Hr(className="my-4"),
            
            # ===================================================================
            # DEMOGRAPHICS OVERVIEW (4 KPIs)
            # ===================================================================
            html.H4("👥 Demographics Overview", className="mb-3"),
            dbc.Row([
                dbc.Col([html.Div(id='visitor-total-card')], md=3),
                dbc.Col([html.Div(id='visitor-unique-card')], md=3),
                dbc.Col([html.Div(id='visitor-male-card')], md=3),
                dbc.Col([html.Div(id='visitor-female-card')], md=3),
            ], className="mb-4"),
            
            html.Hr(className="my-4"),
            
            # ===================================================================
            # ✅ TOP 15 CHANNELS CHART
            # ===================================================================
            html.H4("📊 Performance Charts", className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-graph-up me-2"),
                            "Top 15 Channels Performance"
                        ]),
                        dbc.CardBody([
                            dcc.Graph(id='visitor-channel-performance-chart')
                        ])
                    ], className="shadow-sm")
                ], md=12)
            ], className="mb-4"),
            
            # ===================================================================
            # DEMOGRAPHIC CHARTS
            # ===================================================================
            html.H4("📈 Demographic Distribution", className="mb-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id='new-vs-returning-visitors'), width=12),
            ], className="mt-4 mb-4"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Gender Distribution"),
                        dbc.CardBody([dcc.Graph(id='visitor-gender-chart')])
                    ], className="shadow-sm")
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Age Distribution"),
                        dbc.CardBody([dcc.Graph(id='visitor-age-chart')])
                    ], className="shadow-sm")
                ], md=6),
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Income Range Distribution"),
                        dbc.CardBody([dcc.Graph(id='visitor-income-chart')])
                    ], className="shadow-sm")
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Top States"),
                        dbc.CardBody([dcc.Graph(id='visitor-state-chart')])
                    ], className="shadow-sm")
                ], md=6),
            ], className="mb-4"),
            
            html.Hr(className="my-4"),
            
            # ===================================================================
            # FILTERS SECTION
            # ===================================================================
            html.H4("🔍 Filter & Analyze Data", className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-funnel me-2"),
                            "Filter Visitors Data"
                        ]),
                        dbc.CardBody([
                            # Date Range
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-calendar me-2"),
                                    "Date Range"
                                ], className="fw-bold mb-2"),
                                dcc.DatePickerRange(
                                    id='visitor-date-range-picker',
                                    start_date_placeholder_text="Start Date",
                                    end_date_placeholder_text="End Date",
                                    className="mb-3",
                                    style={'width': '100%'}
                                ),
                            ], className="mb-3"),
                            
                            html.Hr(),
                            html.H6("👥 Demographics", className="mb-3"),
                            
                            # Gender filter
                            html.Div([
                                html.Label("Gender", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='visitor-gender-filter',
                                    multi=True,
                                    placeholder="Select Gender",
                                    className="mb-3"
                                ),
                            ], id='visitor-gender-filter-container', className="mb-3"),
                            
                            # Age filter  
                            html.Div([
                                html.Label("Age Range", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='visitor-age-filter',
                                    multi=True,
                                    placeholder="Select Age Range",
                                    className="mb-3"
                                ),
                            ], id='visitor-age-filter-container', className="mb-3"),
                            
                            html.Hr(),
                            html.H6("💰 Financial", className="mb-3"),
                            
                            # Income Range
                            html.Div([
                                html.Label("Income Range", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='visitor-income-filter',
                                    multi=True,
                                    placeholder="Select Income",
                                    className="mb-3"
                                ),
                            ], id='visitor-income-filter-container', className="mb-3"),
                            
                            html.Hr(),
                            html.H6("📍 Location", className="mb-3"),
                            
                            # State
                            html.Div([
                                html.Label("State", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='visitor-state-filter',
                                    multi=True,
                                    placeholder="Select State",
                                    className="mb-3"
                                ),
                            ], id='visitor-state-filter-container', className="mb-3"),
                            
                            # Action Buttons
                            html.Div([
                                dbc.Button([
                                    html.I(className="bi bi-check-circle me-2"),
                                    "Apply Filters"
                                ], id="visitor-apply-filters", color="primary", className="w-100 mb-2"),
                                dbc.Button([
                                    html.I(className="bi bi-arrow-clockwise me-2"),
                                    "Reset Filters"
                                ], id="visitor-reset-filters", color="secondary", outline=True, className="w-100")
                            ], className="mt-4")
                        ])
                    ], className="shadow-sm", style={'position': 'sticky', 'top': '20px'})
                ], md=4),
                
                # Data Tables
                dbc.Col([
                    # Full Data Table
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-table me-2"),
                            "Complete Visitors Data"
                        ]),
                        dbc.CardBody([
                            html.Div(id='visitor-data-table')
                        ])
                    ], className="shadow-sm mb-4"),
                    
                    # Filtered Data Table
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-funnel-fill me-2 text-primary"),
                            "Filtered Visitors Data"
                        ]),
                        dbc.CardBody([
                            html.Div(id='visitor-filtered-data-table')
                        ])
                    ], className="shadow-sm")
                ], md=8)
            ], className="mb-4"),
        ], style={'display': 'none'}),  # ✅ HIDDEN BY DEFAULT
        
        # ===================================================================
        # ✅ AI ASSISTANT SECTION - NEW CODE STARTS HERE
        # ===================================================================
        html.Hr(className="my-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-robot me-2 text-info"),
                        html.Strong("AI Assistant - Analyze Your Visitors Data")
                    ]),
                    dbc.CardBody([
                        html.P([
                            "💡 ", 
                            html.Strong("Ask questions about your uploaded visitors data!"),
                            html.Br(),
                            "The AI will analyze your actual data and provide insights."
                        ], className="mb-3"),
                        
                        # Example questions
                        html.Div([
                            html.Small("Example questions:", className="text-muted fw-bold d-block mb-2"),
                            dbc.Badge("What's the gender distribution?", color="light", text_color="dark", className="me-2 mb-2"),
                            dbc.Badge("Which states have most visitors?", color="light", text_color="dark", className="me-2 mb-2"),
                            dbc.Badge("Show me income breakdown", color="light", text_color="dark", className="me-2 mb-2"),
                            dbc.Badge("What's the repeat visitor rate?", color="light", text_color="dark", className="me-2 mb-2"),
                        ], className="mb-3"),
                        
                        dbc.Button([
                            html.I(className="bi bi-robot me-2"),
                            "Open AI Assistant"
                        ], id="open-ai-modal-visitors", color="info", size="lg", className="w-100")
                    ])
                ], className="shadow-sm mb-4")
            ])
        ]),
        
        # Back Button
        dbc.Row([
            dbc.Col([
                html.Hr(className="my-4"),
                dbc.Button([
                    html.I(className="bi bi-arrow-left me-2"),
                    "Back to Dashboard"
                ], href="/", color="secondary", outline=True)
            ])
        ]),
        
        # ===================================================================
        # ✅ AI MODAL - POPUP WINDOW FOR CHAT
        # ===================================================================
        dbc.Modal([
            dbc.ModalHeader([
                html.I(className="bi bi-robot me-2 text-info"),
                html.Strong("AI Assistant - Visitors Data Analysis")
            ], close_button=True),
            
            dbc.ModalBody([
                # Instructions Card
                dbc.Alert([
                    html.Div([
                        html.I(className="bi bi-lightbulb text-warning me-2", style={'fontSize': '24px'}),
                        html.Strong("How to use:", className="ms-2")
                    ], className="d-flex align-items-center mb-2"),
                    html.P("Ask questions about your uploaded visitors data in plain English!", className="mb-2"),
                    html.Div([
                        html.Strong("Example Questions:"),
                        html.Ul([
                            html.Li("What is the gender distribution of my visitors?"),
                            html.Li("Which states have the most visitors?"),
                            html.Li("Show me the top 5 income ranges"),
                            html.Li("How many unique visitors do I have?"),
                            html.Li("What percentage are repeat visitors?"),
                            html.Li("What's the most common age group?")
                        ], className="mb-0 small")
                    ])
                ], color="info", className="mb-3"),
                
                # Chat History Display
                html.Div(
                    id='ai-chat-history-visitors', 
                    className="mb-3 p-3 border rounded", 
                    style={
                        "maxHeight": "400px", 
                        "overflowY": "auto",
                        "backgroundColor": "#f8f9fa"
                    },
                    children=[
                        html.Div([
                            html.I(className="bi bi-robot text-info me-2", style={'fontSize': '20px'}),
                            html.Span([
                                html.Strong("AI Assistant: ", className="text-info"),
                                "Hello! I'm ready to analyze your visitors data. What would you like to know?"
                            ], className="text-muted")
                        ], className="mb-2")
                    ]
                ),
                
                # Query Input
                dbc.InputGroup([
                    dbc.Input(
                        id='ai-query-input-visitors', 
                        placeholder="Type your question here... (e.g., How many visitors from California?)", 
                        type="text",
                        style={'fontSize': '14px'}
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-send-fill me-2"), "Ask"], 
                        id="send-ai-query-visitors", 
                        color="info"
                    )
                ], className="mb-2"),
                
                html.Small("💡 Tip: Be specific in your questions for better results!", className="text-muted")
            ]),
            
            dbc.ModalFooter([
                dbc.Button([
                    html.I(className="bi bi-trash me-2"),
                    "Clear Chat"
                ], id="clear-ai-chat-visitors", color="secondary", outline=True, size="sm", className="me-2"),
                dbc.Button([
                    html.I(className="bi bi-x-circle me-2"),
                    "Close"
                ], id="close-ai-modal-visitors", color="secondary", size="sm")
            ])
        ], id="ai-modal-visitors", size="lg", scrollable=True, is_open=False)
    ], fluid=True, className="p-4")

def create_admin_page():
    """Create admin page with improved feedback sections"""
    return dbc.Container([
        html.Div([
            dcc.Dropdown(id='file-type-dropdown', value='buyers', style={'display': 'none'}),
            dcc.Upload(id='upload-data', style={'display': 'none'}),
            html.Div(id='upload-status', style={'display': 'none'}),
            html.Div(id='upload-preview', style={'display': 'none'}),
        ], style={'display': 'none'}),
        html.H1("Administration", className="mb-4"),
        
        # Feedback sections at the top for better visibility
        html.Div(id='save-workspace-feedback', className="mb-3"),
        html.Div(id='delete-workspace-feedback', className="mb-3"),
        html.Div(id='create-workspace-feedback', className="mb-3"),
        
        dbc.Row([
            dbc.Col([
                # Create New Workspace Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-plus-circle me-2"),
                        "Create New Workspace"
                    ]),
                    dbc.CardBody([
                        dbc.InputGroup([
                            dbc.Input(
                                id="new-workspace-name",
                                placeholder="Enter workspace name",
                                type="text"
                            ),
                            dbc.Button(
                                [html.I(className="bi bi-plus me-2"), "Create"],
                                id="create-workspace-btn",
                                color="success",
                                n_clicks=0
                            )
                        ], className="mb-2"),
                        html.Small("Create a new workspace to organize your data separately", className="text-muted")
                    ])
                ], className="shadow-sm mb-4"),
                
                # Workspace Management Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-gear me-2"),
                        "Workspace Settings"
                    ]),
                    dbc.CardBody([
                        dbc.Label("Select Workspace to Manage", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='workspace-selector',
                            placeholder="Select a Workspace",
                            className="mb-3"
                        ),
                        html.Hr(),
                        html.Div(id='workspace-settings')
                    ])
                ], className="shadow-sm mb-4"),
                
                # Workspace List Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-list-ul me-2"),
                        "All Workspaces"
                    ]),
                    dbc.CardBody([
                        html.Div(id='workspace-list')
                    ])
                ], className="shadow-sm mb-4")
            ], md=6),
            
            dbc.Col([
                # Team Members Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-people me-2"),
                        "Invite Team Members"
                    ]),
                    dbc.CardBody([
                        html.P("Invite users to collaborate on your workspace", className="text-muted mb-3"),
                        dbc.InputGroup([
                            dbc.Input(
                                id="invite-email",
                                placeholder="email@example.com",
                                type="email"
                            ),
                            dbc.Button(
                                [html.I(className="bi bi-envelope me-2"), "Invite"],
                                id="invite-btn",
                                color="primary",
                                n_clicks=0
                            )
                        ]),
                        html.Div(id="invite-feedback", className="mt-3")
                    ])
                ], className="shadow-sm mb-4"),
                
                # Help Card
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-question-circle me-2"),
                        "Help & Tips"
                    ]),
                    dbc.CardBody([
                        html.H6("Workspace Management", className="mb-2"),
                        html.Ul([
                            html.Li("Create multiple workspaces to organize different projects"),
                            html.Li("Invite team members by email to collaborate"),
                            html.Li("Only workspace owners can delete workspaces"),
                            html.Li("All workspace data is preserved when you switch between workspaces")
                        ], className="small text-muted"),
                        html.Hr(),
                        html.H6("Roles & Permissions", className="mb-2"),
                        html.Ul([
                            html.Li([html.Strong("Owner: "), "Full access to all features"]),
                            html.Li([html.Strong("Analyst: "), "Can view and analyze data"]),
                            html.Li([html.Strong("Viewer: "), "Read-only access"])
                        ], className="small text-muted")
                    ])
                ], className="shadow-sm mb-4")
            ], md=6)
        ]),
        
        # Delete Workspace Confirmation Modal
        dbc.Modal([
            dbc.ModalHeader([
                html.I(className="bi bi-exclamation-triangle text-danger me-2"),
                "Confirm Delete Workspace"
            ]),
            dbc.ModalBody([
                html.P("Are you sure you want to delete this workspace?", className="mb-2"),
                dbc.Alert([
                    html.I(className="bi bi-exclamation-circle me-2"),
                    html.Strong("Warning: "),
                    "This action cannot be undone. All data, uploads, and settings will be permanently deleted."
                ], color="danger")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="cancel-delete-workspace", color="secondary", className="me-2"),
                dbc.Button([
                    html.I(className="bi bi-trash me-2"),
                    "Delete Permanently"
                ], id="confirm-delete-workspace", color="danger")
            ])
        ], id="delete-workspace-modal", is_open=False),
        
        # Navigation
        dbc.Row([
            dbc.Col([
                html.Hr(className="my-4"),
                dbc.Button([
                    html.I(className="bi bi-arrow-left me-2"),
                    "Back to Dashboard"
                ], href="/", color="secondary", outline=True)
            ])
        ])
    ], fluid=True, className="p-4")

# ============================================================================
# DATA TABLE CALLBACK - SHOWS TABLE ON DASHBOARD
# ============================================================================

@app.callback(
    Output('data-table', 'children'),
    [Input('buyers-data', 'data'),
     Input('visitors-data', 'data'),
     Input('file-type-dropdown', 'value')],
    prevent_initial_call=True
)
def display_data_table(buyers_data, visitors_data, file_type):
    """Display correct data based on selected file type"""
    from dash import dash_table
    
    # If no data at all, show empty state
    if not buyers_data and not visitors_data:
        return html.Div([
            html.I(className="bi bi-table", style={"fontSize": "64px", "color": "#ccc"}),
            html.H5("No Data Available", className="mt-3 text-muted"),
            html.P("Upload data to see the table", className="text-muted")
        ], className="text-center py-5")
    
    logger.info(f"🎯 Displaying table for file_type: {file_type}")
    
    if file_type == 'buyers':
        if not buyers_data:
            return html.Div([
                html.I(className="bi bi-cart-x", style={"fontSize": "64px", "color": "#ccc"}),
                html.H5("No Buyers Data", className="mt-3 text-muted"),
                html.P("Upload buyers data to see analytics", className="text-muted")
            ], className="text-center py-5")
        
        df = pd.DataFrame(buyers_data)
        data_type = "buyers"
        title = "Buyers Data"
        icon = "bi-cart-fill"
        icon_color = "success"
        
    elif file_type == 'visitors':
        if not visitors_data:
            return html.Div([
                html.I(className="bi bi-people-x", style={"fontSize": "64px", "color": "#ccc"}),
                html.H5("No Visitors Data", className="mt-3 text-muted"),
                html.P("Go to Visitors Analytics page to upload visitor data", className="text-muted")
            ], className="text-center py-5")
        
        df = pd.DataFrame(visitors_data)
        data_type = "visitors"
        title = "Visitors Data"
        icon = "bi-people-fill"
        icon_color = "info"
        
    else:
        return html.Div([
            html.I(className="bi bi-question-circle", style={"fontSize": "64px", "color": "#ccc"}),
            html.H5("Please Select Data Type", className="mt-3 text-muted"),
            html.P("Upload data to begin", className="text-muted")
        ], className="text-center py-5")
    
    total_rows = len(df)
    display_rows = min(100, total_rows)
    display_df = df.head(display_rows)
    
    logger.info(f"📊 Displaying {display_rows} of {total_rows:,} {data_type} rows")
    
    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.I(className=f"{icon} me-2 text-{icon_color}", style={'fontSize': '24px'}),
                html.Span(title, className="fw-bold"),
                dbc.Badge(
                    data_type.upper(),
                    color=icon_color,
                    className="ms-2"
                ),
                dbc.Badge(
                    f"Showing {display_rows}",
                    color="secondary",
                    className="ms-2"
                )
            ], className="d-flex align-items-center")
        ]),
        dbc.CardBody([
            # Stats row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_rows:,}", className="mb-0 text-primary"),
                        html.Small("Total Rows", className="text-muted")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H4(f"{len(df.columns)}", className="mb-0 text-info"),
                        html.Small("Columns", className="text-muted")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H4(f"{display_rows}", className="mb-0 text-warning"),
                        html.Small("Displayed", className="text-muted")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    dbc.Button(
                        [
                            html.I(className="bi bi-download me-2"),
                            f"Export CSV"
                        ],
                        id={'type': 'export-data-btn', 'file_type': data_type},
                        color=icon_color,
                        size="sm",
                        className="w-100",
                        n_clicks=0
                    )
                ], width=3)
            ], className="mb-3"),
            
            html.Hr(),
            
            # Data table
            html.Div([
                dash_table.DataTable(
                    data=display_df.to_dict('records'),
                    columns=[{"name": col, "id": col} for col in display_df.columns],
                    page_size=20,
                    page_action='native',
                    sort_action='native',
                    filter_action='native',
                    style_table={
                        'overflowX': 'auto',
                        'maxHeight': '600px',
                        'overflowY': 'auto'
                    },
                    style_cell={
                        'textAlign': 'left',
                        'padding': '10px',
                        'fontSize': '13px',
                        'minWidth': '100px',
                        'maxWidth': '300px',
                        'whiteSpace': 'normal'
                    },
                    style_header={
                        'backgroundColor': '#f8f9fa',
                        'fontWeight': 'bold',
                        'borderBottom': '2px solid #dee2e6',
                        'position': 'sticky',
                        'top': 0,
                        'zIndex': 1
                    },
                    style_data_conditional=[
                        {
                            'if': {'row_index': 'odd'},
                            'backgroundColor': '#f8f9fa'
                        },
                        {
                            'if': {'state': 'selected'},
                            'backgroundColor': '#e3f2fd',
                            'border': '1px solid #2196f3'
                        }
                    ],
                    tooltip_data=[
                        {
                            column: {'value': str(value)[:100], 'type': 'text'}
                            for column, value in row.items()
                        } for row in display_df.to_dict('records')
                    ],
                    tooltip_duration=None,
                    tooltip_delay=0
                )
            ]),
            
            # Show warning if table is truncated
            dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                f"Showing first {display_rows} rows for performance. Export CSV to get all {total_rows:,} rows."
            ], color="info", className="mt-3 mb-0") if total_rows > display_rows else None
        ])
    ], className="shadow-sm mt-4")

# ============================================================================
# SHOW/HIDE DASHBOARD CALLBACK
# ============================================================================

@app.callback(
    Output('dashboard-content', 'style'),
    [Input('buyers-data', 'data'),
     Input('visitors-data', 'data')]
)
def show_hide_dashboard(buyers_data, visitors_data):
    """Show dashboard only when data is uploaded"""
    logger.debug(f"Checking data: buyers={bool(buyers_data)}, visitors={bool(visitors_data)}")
    if buyers_data or visitors_data:
        logger.info("✅ Showing dashboard - data available")
        return {'display': 'block'}
    logger.info("⏸️ Hiding dashboard - no data yet")
    return {'display': 'none'}

# ============================================================================
# FILTER RESET CALLBACK
# ============================================================================

@app.callback(
    [Output('date-range-picker', 'start_date', allow_duplicate=True),
     Output('date-range-picker', 'end_date', allow_duplicate=True),
     Output('channel-filter', 'value'),
     Output('campaign-filter', 'value'),
     Output('gender-filter', 'value'),
     Output('age-filter', 'value'),
     Output('income-filter', 'value'),
     Output('networth-filter', 'value'),
     Output('credit-filter', 'value'),
     Output('homeowner-filter', 'value'),
     Output('married-filter', 'value'),
     Output('children-filter', 'value'),
     Output('state-filter', 'value')],
    [Input('reset-filters', 'n_clicks')],
    [State('buyers-data', 'data')],
    prevent_initial_call=True
)
def reset_filters(n_clicks, buyers_data):
    """Reset all filters to default values"""
    if not n_clicks:
        return [no_update] * 13
    
    logger.info("🔄 Resetting all filters to default")
    
    if buyers_data:
        try:
            df = pd.DataFrame(buyers_data)
            date_col = None
            
            for col in df.columns:
                if any(kw in col.lower() for kw in ['date', 'time', 'timestamp', 'created', 'updated']):
                    try:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                        if df[col].notna().sum() > 0:
                            date_col = col
                            break
                    except:
                        continue
            
            if date_col:
                min_date = df[date_col].min().date()
                max_date = df[date_col].max().date()
                logger.info(f"📅 Reset date range: {min_date} to {max_date}")
                return [min_date, max_date] + [None] * 11
        except Exception as e:
            logger.error(f"Error getting date range: {e}")
    
    end_date = datetime.now().date()
    start_date = (datetime.now() - timedelta(days=30)).date()
    
    logger.info(f"📅 Reset date range (fallback): {start_date} to {end_date}")
    return [start_date, end_date] + [None] * 11

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == '__main__':
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8050))

    print("\n" + "="*60)
    print("🚀 Lead Navigator AI - Frontend Server")
    print("="*60)
    print(f"📊 Dashboard URL: http://localhost:{PORT}")
    print(f"🔌 Backend API: {API_BASE_URL}")
    print(f"🐛 Debug Mode: {DEBUG}")
    print("="*60)
    print("✅ Using external backend — no local server needed")
    print("⌨️  Press CTRL+C to stop\n")

    try:
        app.run_server(debug=DEBUG, host=HOST, port=PORT)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("\n🔧 Troubleshooting:")
        print("  1. Check .env has API_BASE_URL")
        print("  2. Run: pip install -r requirements.txt")
        print("  3. Check EB logs: eb logs")