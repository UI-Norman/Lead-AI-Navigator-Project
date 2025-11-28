import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table

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
                className="w-100"
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

def create_header(workspace_name: str = "Workspace"):
    """Create top header bar"""
    return dbc.Navbar([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        dbc.DropdownMenu([
                            dbc.DropdownMenuItem(workspace_name, header=True),
                            dbc.DropdownMenuItem(divider=True),
                            dbc.DropdownMenuItem("Switch Workspace", id="switch-workspace"),
                            dbc.DropdownMenuItem("Create Workspace", id="create-workspace"),
                        ], label=workspace_name, color="light", className="me-2"),
                        
                        dbc.DropdownMenu([
                            dbc.DropdownMenuItem("Profile", id="profile"),
                            dbc.DropdownMenuItem("Settings", id="settings"),
                            dbc.DropdownMenuItem(divider=True),
                            dbc.DropdownMenuItem("Logout", id="logout"),
                        ], label="Account", color="light"),
                    ])
                ], width="auto")
            ], align="center", className="g-0 ms-auto flex-nowrap", justify="end")
        ], fluid=True)
    ], color="white", light=True, className="shadow-sm", style={"marginLeft": "250px"})

def create_ai_modal():
    """Create AI assistant modal with file upload and file type selector"""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("AI Assistant")),
        dbc.ModalBody([
            # File upload
            html.Label("Upload File (optional)", className="form-label"),
            dcc.Upload(
                id='upload-file',
                children=html.Button('Select File', className="btn btn-outline-secondary btn-sm"),
                accept=".csv,.tsv,.txt,.gz,.zip",
                className="mb-2",
                multiple=False
            ),
            # File type selector
            html.Label("File Type", className="form-label"),
            dcc.Dropdown(
                id='file-type',
                options=[
                    {'label': 'Buyers', 'value': 'buyers'},
                    {'label': 'Visitors', 'value': 'visitors'}
                ],
                placeholder="Select file type",
                className="mb-3",
                style={'width': '100%'}
            ),
            # Query input
            dcc.Input(
                id='ai-query-input',
                type='text',
                placeholder="Ask a question about your data...",
                className="form-control mb-2",
                style={'width': '100%'}
            ),
            # Loading indicator
            html.Div(id='ai-loading', className="mb-2 text-center"),
            # Chat history
            html.Div(
                id='ai-chat-history',
                className="border rounded p-3 bg-light",
                style={'maxHeight': '400px', 'overflowY': 'auto'}
            )
        ]),
        dbc.ModalFooter([
            dbc.Button("Send", id="send-ai-query", color="primary"),
            dbc.Button("Close", id="close-ai-modal", className="ms-2")
        ])
    ], id="ai-modal", size="lg", scrollable=True, is_open=False)

def create_upload_area():
    """Create drag-and-drop upload area with file type selector"""
    return html.Div([
        dcc.Dropdown(
            id='file-type-dropdown',
            options=[
                {'label': 'Buyers Data', 'value': 'buyers'},
                {'label': 'Visitors Data', 'value': 'visitors'}
            ],
            placeholder='Select file type...',
            className="mb-3",
            style={'width': '100%'}
        ),
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                html.I(className="bi bi-cloud-upload", style={"fontSize": "48px"}),
                html.Br(),
                html.H5("Drag and Drop or Click to Upload"),
                html.P("Supports CSV, TSV, and GZIP files (Max 2GB)", className="text-muted")
            ]),
            style={
                'width': '100%',
                'height': '200px',
                'lineHeight': '200px',
                'borderWidth': '2px',
                'borderStyle': 'dashed',
                'borderRadius': '10px',
                'textAlign': 'center',
                'cursor': 'pointer'
            },
            multiple=False
        )
    ])

def create_filter_panel():
    """Create filter controls panel"""
    return dbc.Card([
        dbc.CardHeader("Filters"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Date Range"),
                    dcc.DatePickerRange(
                        id='date-range-picker',
                        className="mb-3"
                    )
                ], md=6),
                
                dbc.Col([
                    dbc.Label("Data Source"),
                    dcc.Dropdown(
                        id='data-source-filter',
                        options=[
                            {'label': 'All Data', 'value': 'all'},
                            {'label': 'Buyers Only', 'value': 'buyers'},
                            {'label': 'Visitors Only', 'value': 'visitors'}
                        ],
                        value='all',
                        className="mb-3"
                    )
                ], md=6)
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Label("Channel/Source"),
                    dcc.Dropdown(
                        id='channel-filter',
                        multi=True,
                        placeholder="Select channels..."
                    )
                ], md=6),
                
                dbc.Col([
                    dbc.Label("Campaign"),
                    dcc.Dropdown(
                        id='campaign-filter',
                        multi=True,
                        placeholder="Select campaigns..."
                    )
                ], md=6)
            ]),
            
            html.Div([
                dbc.Button("Apply Filters", id="apply-filters", color="primary", className="me-2"),
                dbc.Button("Reset", id="reset-filters", color="secondary", outline=True),
                dbc.Button("Save", id="save-filters", color="success", outline=True, className="ms-2")
            ], className="mt-3")
        ])
    ], className="shadow-sm mb-4")

def create_empty_state(icon: str, title: str, description: str, action_text: str = None, action_id: str = None):
    """Create empty state component"""
    content = [
        html.I(className=f"bi bi-{icon}", style={"fontSize": "64px", "color": "#ccc"}),
        html.H4(title, className="mt-3 mb-2"),
        html.P(description, className="text-muted mb-3")
    ]
    
    if action_text and action_id:
        content.append(
            dbc.Button(action_text, id=action_id, color="primary")
        )
    
    return html.Div(
        content,
        className="text-center py-5"
    )

def create_data_table(df_dict: dict = None, table_id: str = "data-table"):
    """Create interactive data table"""
    if df_dict is None:
        df_dict = {'data': [], 'columns': []}
    
    return dash_table.DataTable(
        id=table_id,
        data=df_dict.get('data', []),
        columns=df_dict.get('columns', []),
        page_size=20,
        page_action='native',
        sort_action='native',
        filter_action='native',
        column_selectable='multi',
        row_selectable='multi',
        selected_columns=[],
        selected_rows=[],
        export_format='csv',
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'fontSize': '14px'
        },
        style_header={
            'backgroundColor': '#f8f9fa',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': '#f8f9fa'
            }
        ]
    )

def create_main_layout():
    """Create main dashboard layout"""
    return html.Div([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='auth-token', storage_type='local'),
        dcc.Store(id='current-workspace', storage_type='local'),
        dcc.Store(id='user-filters', storage_type='local'),
        dcc.Store(id='buyers-data', storage_type='local'),
        dcc.Store(id='visitors-data', storage_type='local'),
        
        # ---- NEW VISITOR GRAPHS (required for the Visitors page) ----
        dcc.Graph(id='new-vs-returning-visitors', style={'display': 'none'}),
        dcc.Graph(id='conversion-over-time', style={'display': 'none'}),            
        create_sidebar(),
        
        html.Div([
            create_header(),
            html.Div(id='page-content', className="p-4"),
            create_ai_modal()  # Add AI modal to the main layout
        ], style={"marginLeft": "250px"})
    ])
