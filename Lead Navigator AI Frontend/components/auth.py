import dash_bootstrap_components as dbc
from dash import html, dcc

def login_layout():
    """Create login page layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H2("Lead Navigator AI", className="text-center mb-4"),
                    html.P("Sign in to your account", className="text-center text-muted mb-4"),
                    
                    dbc.Card([
                        dbc.CardBody([
                            dbc.Form([
                                dbc.Label("Email"),
                                dbc.Input(
                                    id="login-email",
                                    type="email",
                                    placeholder="Enter your email",
                                    className="mb-3"
                                ),
                                
                                dbc.Label("Password"),
                                dbc.Input(
                                    id="login-password",
                                    type="password",
                                    placeholder="Enter your password",
                                    className="mb-3"
                                ),
                                
                                dbc.Button(
                                    "Sign In",
                                    id="login-button",
                                    color="primary",
                                    className="w-100 mb-3",
                                    n_clicks=0
                                ),
                                
                                html.Hr(),
                                
                                dbc.Button(
                                    "Send Magic Link",
                                    id="magic-link-button",
                                    color="secondary",
                                    outline=True,
                                    className="w-100 mb-2",
                                    n_clicks=0
                                ),
                                
                                html.Div(
                                    html.A("Create new account", href="/register", id="show-register"),
                                    className="text-center mt-3"
                                ),
                                
                                html.Div(id="login-feedback", className="mt-3")
                            ])
                        ])
                    ], className="shadow")
                ], className="mt-5")
            ], width=4)
        ], justify="center")
    ], fluid=True)


def register_layout():
    """Create registration page layout"""
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
                                    html.A("Already have an account? Sign in", href="/", id="show-login"),
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


def create_sidebar():
    """Create sidebar navigation"""
    return html.Div([
        html.Div([
            html.H3("Lead Navigator AI", className="text-white mb-4"),
            html.Hr(className="bg-white"),
            
            dbc.Nav([
                dbc.NavLink([
                    html.I(className="bi bi-house-door me-2"),
                    "Home"
                ], href="/", active="exact", className="text-white"),
                
                dbc.NavLink([
                    html.I(className="bi bi-diagram-3 me-2"),
                    "Segments"
                ], href="/segments", active="exact", className="text-white"),
                
                dbc.NavLink([
                    html.I(className="bi bi-cloud-upload me-2"),
                    "Uploads"
                ], href="/uploads", active="exact", className="text-white"),
                
                dbc.NavLink([
                    html.I(className="bi bi-file-earmark-text me-2"),
                    "Reports"
                ], href="/reports", active="exact", className="text-white"),
                
                dbc.NavLink([
                    html.I(className="bi bi-gear me-2"),
                    "Admin"
                ], href="/admin", active="exact", className="text-white"),
            ], vertical=True, pills=True),
            
            html.Hr(className="bg-white mt-4"),
            
            html.Div([
                html.I(className="bi bi-robot me-2"),
                "AI Assistant"
            ], className="text-white mb-2"),
            
            dbc.Button(
                "Ask AI",
                id="open-ai-modal",
                color="light",
                outline=True,
                size="sm",
                className="w-100",
                n_clicks=0
            )
        ], className="p-3")
    ], style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "bottom": 0,
        "width": "250px",
        "padding": "2rem 1rem",
        "background-color": "#2c3e50"
    })


# Backward compatibility - keep old function names
def create_login_form():
    """Alias for backward compatibility"""
    return login_layout()


def create_register_form():
    """Alias for backward compatibility"""
    return register_layout()