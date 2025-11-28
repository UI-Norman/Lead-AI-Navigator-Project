# ============================================================================
# NEW FILE: callbacks/mapping_callbacks.py
# ============================================================================

from dash import Input, Output, State, callback, no_update, html, ALL, callback_context
import dash_bootstrap_components as dbc
import requests
import os
import base64
import logging
from dotenv import load_dotenv
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env")

# Get API URL from environment
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise EnvironmentError("API_BASE_URL is required in .env file")


def register_mapping_callbacks(app):
    """Register all column mapping callbacks"""
    
    @app.callback(
        [Output('mapping-suggestions-modal', 'is_open'),
         Output('mapping-suggestions-content', 'children'),
         Output('suggested-mapping-data', 'data')],
        [Input('suggest-mapping-btn', 'n_clicks')],
        [State('upload-data', 'contents'),
         State('upload-data', 'filename'),
         State('file-type-dropdown', 'value'),
         State('auth-token', 'data'),
         State('current-workspace', 'data')],
        prevent_initial_call=True
    )
    def get_mapping_suggestions(n_clicks, contents, filename, file_type, token, workspace_id):
        """Get AI-powered mapping suggestions"""
        if not n_clicks or not contents:
            return False, "", None
        
        if not token:
            error = dbc.Alert("Please login first", color="danger")
            return True, error, None
        
        try:
            # Decode file
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            # Prepare file for upload
            files = {'file': (filename, decoded, 'text/csv')}
            data = {'file_type': file_type}
            
            workspace_id = workspace_id or 1
            
            # Call suggest mapping endpoint
            response = requests.post(
                f"{API_BASE_URL}/workspaces/{workspace_id}/suggest-mapping?token={token}",
                files=files,
                data=data,
                timeout=50
            )
            
            if response.status_code == 200:
                result = response.json()
                mapping = result['suggested_mapping']
                columns = result['columns']
                confidence = result.get('confidence', 0)
                stats = result.get('stats', {})
                
                # Create mapping UI
                mapping_ui = create_mapping_ui(mapping, columns, confidence, stats)
                
                logger.info(f"✅ Got mapping suggestions: {stats.get('mapped_columns', 0)}/{stats.get('total_columns', 0)} mapped")
                
                return True, mapping_ui, mapping
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                error = dbc.Alert(
                    f"Failed to get suggestions: {error_detail}",
                    color="danger"
                )
                return True, error, None
        
        except Exception as e:
            logger.error(f"Mapping suggestion error: {e}")
            error = dbc.Alert(
                f"Error: {str(e)}",
                color="danger"
            )
            return True, error, None
    
    
    @app.callback(
        Output('save-mapping-feedback', 'children'),
        [Input('save-mapping-btn', 'n_clicks')],
        [State('suggested-mapping-data', 'data'),
         State('file-type-dropdown', 'value'),
         State('auth-token', 'data'),
         State('current-workspace', 'data')],
        prevent_initial_call=True
    )
    def save_mapping(n_clicks, mapping, file_type, token, workspace_id):
        """Save approved mapping to backend"""
        if not n_clicks or not mapping:
            return ""
        
        if not token:
            return dbc.Alert("Please login first", color="danger")
        
        try:
            workspace_id = workspace_id or 1
            
            # Save mapping
            response = requests.post(
                f"{API_BASE_URL}/workspaces/{workspace_id}/column-mapping?token={token}",
                json={
                    "file_type": file_type,
                    "mapping": mapping
                },
                timeout=50
            )
            
            if response.status_code == 200:
                result = response.json()
                mapped_count = result.get('mapped_columns', 0)
                
                return dbc.Alert(
                    [
                        html.I(className="bi bi-check-circle me-2"),
                        html.Strong("Success! "),
                        f"Saved mapping for {mapped_count} columns"
                    ],
                    color="success",
                    dismissable=True,
                    duration=4000
                )
            else:
                error = response.json().get('detail', 'Failed to save')
                return dbc.Alert(f"Error: {error}", color="danger")
        
        except Exception as e:
            logger.error(f"Save mapping error: {e}")
            return dbc.Alert(f"Error: {str(e)}", color="danger")
    
    
    @app.callback(
        Output('load-mapping-feedback', 'children'),
        [Input('load-mapping-btn', 'n_clicks')],
        [State('file-type-dropdown', 'value'),
         State('auth-token', 'data'),
         State('current-workspace', 'data')],
        prevent_initial_call=True
    )
    def load_saved_mapping(n_clicks, file_type, token, workspace_id):
        """Load previously saved mapping"""
        if not n_clicks:
            return ""
        
        if not token:
            return dbc.Alert("Please login first", color="danger")
        
        try:
            workspace_id = workspace_id or 1
            
            response = requests.get(
                f"{API_BASE_URL}/workspaces/{workspace_id}/column-mapping/{file_type}?token={token}",
                timeout=50
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result['success'] and result['mapping']:
                    mapping = result['mapping']
                    mapped_count = result['mapped_columns']
                    
                    return dbc.Alert(
                        [
                            html.I(className="bi bi-check-circle me-2"),
                            html.Strong("Loaded! "),
                            f"Found saved mapping with {mapped_count} columns"
                        ],
                        color="info",
                        dismissable=True,
                        duration=4000
                    )
                else:
                    return dbc.Alert(
                        f"No saved mapping found for {file_type}",
                        color="warning",
                        dismissable=True,
                        duration=3000
                    )
            else:
                return dbc.Alert("Failed to load mapping", color="danger")
        
        except Exception as e:
            logger.error(f"Load mapping error: {e}")
            return dbc.Alert(f"Error: {str(e)}", color="danger")


def create_mapping_ui(mapping: dict, columns: list, confidence: float, stats: dict):
    """Create interactive mapping UI"""
    
    # Separate mapped and unmapped columns
    mapped_cols = {k: v for k, v in mapping.items() if v is not None}
    unmapped_cols = [k for k, v in mapping.items() if v is None]
    
    return html.Div([
        # Header with confidence
        dbc.Alert([
            html.Div([
                html.I(className="bi bi-robot me-2", style={"fontSize": "24px"}),
                html.Strong("AI Mapping Suggestions"),
            ], className="d-flex align-items-center mb-2"),
            html.Hr(),
            html.Div([
                dbc.Progress(
                    value=confidence,
                    label=f"{confidence:.0f}% Confidence",
                    color="success" if confidence > 70 else "warning",
                    className="mb-2"
                ),
                html.Small([
                    f"Mapped: {stats.get('mapped_columns', 0)} / {stats.get('total_columns', 0)} columns",
                    html.Br(),
                    f"Unmapped: {stats.get('unmapped_columns', 0)} columns"
                ], className="text-muted")
            ])
        ], color="light", className="mb-3"),
        
        # Mapped columns section
        html.Div([
            html.H5([
                html.I(className="bi bi-check-circle text-success me-2"),
                "Mapped Columns"
            ], className="mb-3"),
            
            dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("CSV Column", style={"width": "45%"}),
                        html.Th("→", className="text-center", style={"width": "10%"}),
                        html.Th("Standard Field", style={"width": "45%"})
                    ])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td([
                            dbc.Badge(csv_col, color="light", className="text-dark")
                        ]),
                        html.Td([
                            html.I(className="bi bi-arrow-right text-primary")
                        ], className="text-center"),
                        html.Td([
                            dbc.Badge(std_field, color="success")
                        ])
                    ])
                    for csv_col, std_field in list(mapped_cols.items())[:20]
                ])
            ], bordered=True, hover=True, size="sm")
        ], className="mb-4") if mapped_cols else None,
        
        # Unmapped columns section
        html.Div([
            html.H5([
                html.I(className="bi bi-exclamation-triangle text-warning me-2"),
                f"Unmapped Columns ({len(unmapped_cols)})"
            ], className="mb-3"),
            
            dbc.Alert([
                html.P("These columns couldn't be automatically mapped:", className="mb-2"),
                html.Div([
                    dbc.Badge(col, color="secondary", className="me-2 mb-2")
                    for col in unmapped_cols[:20]
                ]),
                html.Small(
                    f"+ {len(unmapped_cols) - 20} more..." if len(unmapped_cols) > 20 else "",
                    className="text-muted"
                )
            ], color="warning") if unmapped_cols else dbc.Alert(
                "All columns successfully mapped! 🎉",
                color="success"
            )
        ], className="mb-4"),
        
        # Action buttons
        html.Div([
            dbc.Button([
                html.I(className="bi bi-save me-2"),
                "Save Mapping"
            ], id="save-mapping-btn", color="success", className="me-2"),
            
            dbc.Button([
                html.I(className="bi bi-pencil me-2"),
                "Edit Manually"
            ], id="edit-mapping-btn", color="primary", outline=True, className="me-2"),
            
            dbc.Button([
                html.I(className="bi bi-x-circle me-2"),
                "Cancel"
            ], id="close-mapping-modal", color="secondary", outline=True)
        ], className="d-flex justify-content-end"),
        
        # Feedback area
        html.Div(id='save-mapping-feedback', className="mt-3")
    ])