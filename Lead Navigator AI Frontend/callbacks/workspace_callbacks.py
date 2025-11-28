from dash import Input, Output, State, callback, no_update, html, ALL, callback_context
import dash_bootstrap_components as dbc
import requests
from datetime import datetime
import json
import os
import logging
import jwt
from dotenv import load_dotenv
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env")

# Get API URL from environment
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise EnvironmentError("API_BASE_URL is required in .env file")

def register_workspace_callbacks(app):
    """Register all workspace and admin-related callbacks"""
    
    @app.callback(
        Output('current-workspace', 'data'),
        [Input('auth-token', 'data')]
    )
    def load_default_workspace(token):
        """Load user's default workspace"""
        if not token:
            return None
        
        try:
            response = requests.get(
                f"{API_BASE_URL}/workspaces?token={token}",
                timeout=50
            )
            
            if response.status_code == 200:
                workspaces = response.json()
                if workspaces:
                    return workspaces[0]['id']
                return 1
            else:
                error_detail = response.json().get('detail', f'Status: {response.status_code}')
                logger.error(f"Load default workspace failed: {response.status_code} - {error_detail}")
                return 1
        except Exception as e:
            logger.error(f"Load default workspace error: {str(e)}")
            return 1
    
    @app.callback(
        [Output('workspace-list', 'children'),
         Output('workspace-selector', 'options')],
        [Input('auth-token', 'data'),
         Input('save-workspace-feedback', 'children'),  # âœ… Refresh when workspace renamed
         Input('create-workspace-feedback', 'children')]  # âœ… Refresh when workspace created
    )
    def load_workspaces(token, save_feedback, create_feedback):
        """Load all workspaces for the user - Auto-refreshes after changes"""
        if not token:
            return html.P("Please log in", className="text-muted"), []
        
        try:
            response = requests.get(
                f"{API_BASE_URL}/workspaces?token={token}",
                timeout=50
            )
            
            if response.status_code == 200:
                workspaces = response.json()
                
                if not workspaces:
                    return html.P("No workspaces found", className="text-muted"), []
                
                items = []
                options = []
                
                for ws in workspaces:
                    items.append(
                        dbc.Card([
                            dbc.CardBody([
                                html.H5(ws['name'], className="mb-2"),
                                html.Small(
                                    f"Created: {ws['created_at'][:10]}", 
                                    className="text-muted"
                                ),
                                html.Br(),
                                dbc.Button(
                                    "Select", 
                                    size="sm", 
                                    color="primary",
                                    className="mt-2",
                                    id={'type': 'select-workspace', 'index': ws['id']}
                                )
                            ])
                        ], className="mb-3")
                    )
                    
                    options.append({
                        'label': ws['name'],
                        'value': ws['id']
                    })
                
                logger.info(f"âœ… Loaded {len(workspaces)} workspaces")
                return items, options
            
            error_detail = response.json().get('detail', f'Status: {response.status_code}')
            logger.error(f"Load workspaces failed: {response.status_code} - {error_detail}")
            return html.P(f"Failed to load workspaces: {error_detail}. Please re-login.", className="text-muted"), []
        except Exception as e:
            logger.error(f"Load workspaces error: {str(e)}")
            return html.P(f"Error: {str(e)}. Please re-login.", className="text-muted"), []
    
    @app.callback(
        Output('workspace-selector', 'value'),
        [Input({'type': 'select-workspace', 'index': ALL}, 'n_clicks')],
        [State({'type': 'select-workspace', 'index': ALL}, 'id')]
    )
    def select_workspace(n_clicks, ids):
        """Select workspace from list"""
        ctx = callback_context
        if not ctx.triggered:
            return no_update
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        button_index = json.loads(button_id)['index']
        
        return button_index
    
    @app.callback(
        [Output('workspace-settings', 'children'),
         Output('delete-workspace-modal', 'is_open')],
        [Input('workspace-selector', 'value')],
        [State('auth-token', 'data')]
    )
    def load_workspace_settings(workspace_id, token):
        """Load workspace settings"""
        if not workspace_id or not token:
            return html.P("Select a workspace", className="text-muted"), False
        
        try:
            response = requests.get(
                f"{API_BASE_URL}/workspaces/{workspace_id}?token={token}",
                timeout=50
            )
            
            if response.status_code == 200:
                ws = response.json()
                
                settings_content = [
                    dbc.InputGroup([
                        dbc.InputGroupText("Name"),
                        dbc.Input(
                            id="workspace-name",
                            value=ws['name'],
                            type="text"
                        )
                    ], className="mb-3"),
                    
                    dbc.Button("Save Changes", id="save-workspace-settings", color="primary", n_clicks=0),
                    
                    html.Hr(className="my-4"),
                    
                    html.H5("Danger Zone", className="text-danger"),
                    dbc.Button(
                        "Delete Workspace", 
                        id="delete-workspace-btn", 
                        color="danger", 
                        outline=True,
                        n_clicks=0
                    )
                ]
                
                return settings_content, False
            
            error_detail = response.json().get('detail', f'Status: {response.status_code}')
            logger.error(f"Load workspace settings failed: {response.status_code} - {error_detail}")
            return html.P(f"Failed to load settings: {error_detail}. Please re-login.", className="text-muted"), False
        except Exception as e:
            logger.error(f"Load workspace settings error: {str(e)}")
            return html.P(f"Error loading settings: {str(e)}. Please re-login.", className="text-muted"), False
    
    @app.callback(
        Output('save-workspace-feedback', 'children'),
        [Input('save-workspace-settings', 'n_clicks')],
        [State('workspace-name', 'value'),
         State('workspace-selector', 'value'),
         State('auth-token', 'data')],
        prevent_initial_call=True
    )
    def save_workspace_settings(n_clicks, workspace_name, workspace_id, token):
        """Save workspace settings - This triggers workspace list refresh"""
        if not n_clicks:
            return ""
        
        if not workspace_name or not workspace_name.strip():
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Workspace name cannot be empty"
                ], 
                color="warning", 
                dismissable=True,
                duration=4000
            )
        
        if not workspace_id or not token:
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Please select a workspace first"
                ], 
                color="warning", 
                dismissable=True,
                duration=4000
            )
        
        try:
            response = requests.put(
                f"{API_BASE_URL}/workspaces/{workspace_id}?token={token}",
                json={"name": workspace_name.strip()},
                timeout=50
            )
            
            if response.status_code == 200:
                logger.info(f"âœ… Workspace {workspace_id} renamed to '{workspace_name.strip()}'")
                
                # âœ… Returning this triggers workspace list refresh
                return dbc.Alert(
                    [
                        html.I(className="bi bi-check-circle me-2"),
                        html.Strong("Success! "),
                        f"Workspace renamed to '{workspace_name.strip()}'"
                    ],
                    color="success",
                    dismissable=True,
                    duration=4000
                )
            else:
                error = response.json().get('detail', 'Failed to save settings')
                logger.error(f"Save workspace failed: {response.status_code} - {error}")
                return dbc.Alert(
                    [
                        html.I(className="bi bi-x-circle me-2"),
                        html.Strong("Error: "),
                        f"{error}. Please try again or re-login."
                    ],
                    color="danger",
                    dismissable=True,
                    duration=5000
                )
        except requests.exceptions.Timeout:
            return dbc.Alert(
                [
                    html.I(className="bi bi-clock me-2"),
                    html.Strong("Timeout: "),
                    "Request took too long. Please check your connection and try again."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            )
        except Exception as e:
            logger.error(f"Save workspace error: {str(e)}")
            return dbc.Alert(
                [
                    html.I(className="bi bi-x-circle me-2"),
                    html.Strong("Connection Error: "),
                    "Unable to save changes. Please check your connection."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            )
    
    @app.callback(
        Output('delete-workspace-modal', 'is_open', allow_duplicate=True),
        [Input('delete-workspace-btn', 'n_clicks'),
         Input('cancel-delete-workspace', 'n_clicks')],
        [State('delete-workspace-modal', 'is_open')],
        prevent_initial_call=True
    )
    def toggle_delete_modal(delete_clicks, cancel_clicks, is_open):
        """Toggle delete workspace confirmation modal"""
        ctx = callback_context
        if not ctx.triggered:
            return no_update
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if 'delete-workspace-btn' in button_id and delete_clicks:
            return True
        elif 'cancel-delete-workspace' in button_id and cancel_clicks:
            return False
        
        return is_open
    
    @app.callback(
        [Output('delete-workspace-modal', 'is_open', allow_duplicate=True),
         Output('delete-workspace-feedback', 'children'),
         Output('workspace-selector', 'value', allow_duplicate=True)],
        [Input('confirm-delete-workspace', 'n_clicks')],
        [State('workspace-selector', 'value'),
         State('auth-token', 'data')],
        prevent_initial_call=True
    )
    def delete_workspace(n_clicks, workspace_id, token):
        """Delete current workspace with confirmation message"""
        if not n_clicks:
            return no_update, "", no_update
        
        if not workspace_id or not token:
            return False, dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Invalid workspace selection"
                ],
                color="danger",
                dismissable=True,
                duration=4000
            ), no_update
        
        try:
            response = requests.delete(
                f"{API_BASE_URL}/workspaces/{workspace_id}?token={token}",
                timeout=50
            )
            
            if response.status_code == 200:
                logger.info(f"âœ… Workspace {workspace_id} deleted")
                return False, dbc.Alert(
                    [
                        html.I(className="bi bi-check-circle me-2"),
                        html.Strong("Deleted! "),
                        "Workspace has been permanently deleted."
                    ],
                    color="success",
                    dismissable=True,
                    duration=4000
                ), None
            else:
                error = response.json().get('detail', 'Failed to delete workspace')
                logger.error(f"Delete workspace failed: {response.status_code} - {error}")
                return False, dbc.Alert(
                    [
                        html.I(className="bi bi-x-circle me-2"),
                        html.Strong("Error: "),
                        f"{error}. Please try again."
                    ],
                    color="danger",
                    dismissable=True,
                    duration=5000
                ), no_update
        except requests.exceptions.Timeout:
            return False, dbc.Alert(
                [
                    html.I(className="bi bi-clock me-2"),
                    html.Strong("Timeout: "),
                    "Request took too long. Please try again."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            ), no_update
        except Exception as e:
            logger.error(f"Delete workspace error: {str(e)}")
            return False, dbc.Alert(
                [
                    html.I(className="bi bi-x-circle me-2"),
                    html.Strong("Connection Error: "),
                    "Unable to delete workspace. Please check your connection."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            ), no_update
    
    @app.callback(
        Output('invite-feedback', 'children'),
        [Input('invite-btn', 'n_clicks')],
        [State('invite-email', 'value'),
         State('workspace-selector', 'value'),
         State('auth-token', 'data')],
        prevent_initial_call=True
    )
    def invite_user_to_workspace(n_clicks, email, workspace_id, token):
        """Invite user to workspace - Backend will save in audit logs"""
        if not n_clicks:
            return ""
        
        if not email or not email.strip():
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Please enter an email address"
                ],
                color="warning",
                dismissable=True,
                duration=4000
            )
        
        if '@' not in email or '.' not in email.split('@')[1]:
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Please enter a valid email address"
                ],
                color="warning",
                dismissable=True,
                duration=4000
            )
        
        if not workspace_id or not token:
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Please select a workspace first"
                ],
                color="warning",
                dismissable=True,
                duration=4000
            )
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/workspaces/{workspace_id}/invite?token={token}",
                json={"email": email.strip(), "role": "Viewer"},
                timeout=50
            )
            
            if response.status_code == 200:
                data = response.json()
                invite_link = data.get('invite_link', '')
                
                logger.info(f"âœ… Invitation sent to {email.strip()}")
                
                return dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    html.Strong("Invitation Sent! "),
                    html.Br(),
                    html.Small([
                        f"Invited {email.strip()} to workspace. Invitation saved in audit logs.",
                        html.Br(),
                        html.A("Copy invite link", href=invite_link, target="_blank", className="alert-link") if invite_link else None
                    ])
                ], color="success", dismissable=True, duration=6000)
            else:
                error = response.json().get('detail', 'Failed to send invitation')
                logger.error(f"Invite failed: {response.status_code} - {error}")
                
                if 'already' in error.lower():
                    return dbc.Alert(
                        [
                            html.I(className="bi bi-info-circle me-2"),
                            html.Strong("Already Member: "),
                            f"{email.strip()} is already in this workspace"
                        ],
                        color="info",
                        dismissable=True,
                        duration=4000
                    )
                elif 'not found' in error.lower():
                    return dbc.Alert(
                        [
                            html.I(className="bi bi-exclamation-triangle me-2"),
                            html.Strong("User Not Found: "),
                            f"{email.strip()} is not registered. They need to create an account first."
                        ],
                        color="warning",
                        dismissable=True,
                        duration=5000
                    )
                else:
                    return dbc.Alert(
                        [
                            html.I(className="bi bi-x-circle me-2"),
                            html.Strong("Error: "),
                            f"{error}"
                        ],
                        color="danger",
                        dismissable=True,
                        duration=5000
                    )
        except requests.exceptions.Timeout:
            return dbc.Alert(
                [
                    html.I(className="bi bi-clock me-2"),
                    html.Strong("Timeout: "),
                    "Request took too long. Please try again."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            )
        except Exception as e:
            logger.error(f"Invite error: {str(e)}")
            return dbc.Alert(
                [
                    html.I(className="bi bi-x-circle me-2"),
                    html.Strong("Connection Error: "),
                    "Unable to send invitation. Please check your connection."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            )
    
    @app.callback(
        [Output('create-workspace-feedback', 'children'),
         Output('new-workspace-name', 'value')],
        [Input('create-workspace-btn', 'n_clicks')],
        [State('new-workspace-name', 'value'),
         State('auth-token', 'data')],
        prevent_initial_call=True
    )
    def create_new_workspace(n_clicks, workspace_name, token):
        """Create new workspace - Triggers workspace list refresh"""
        if not n_clicks:
            return "", no_update
        
        if not workspace_name or not workspace_name.strip():
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Please enter a workspace name"
                ],
                color="warning",
                dismissable=True,
                duration=4000
            ), no_update
        
        if not token:
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Authentication required"
                ],
                color="warning",
                dismissable=True,
                duration=4000
            ), no_update
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/workspaces?token={token}",
                json={"name": workspace_name.strip()},
                timeout=50
            )
            
            if response.status_code == 200:
                logger.info(f"âœ… Workspace '{workspace_name.strip()}' created")
                
                # âœ… Returning this triggers workspace list refresh
                return dbc.Alert(
                    [
                        html.I(className="bi bi-check-circle me-2"),
                        html.Strong("Created! "),
                        f"Workspace '{workspace_name.strip()}' has been created successfully."
                    ],
                    color="success",
                    dismissable=True,
                    duration=4000
                ), ""  # Clear input field
            else:
                error = response.json().get('detail', 'Failed to create workspace')
                logger.error(f"Create workspace failed: {response.status_code} - {error}")
                return dbc.Alert(
                    [
                        html.I(className="bi bi-x-circle me-2"),
                        html.Strong("Error: "),
                        f"{error}"
                    ],
                    color="danger",
                    dismissable=True,
                    duration=5000
                ), no_update
        except requests.exceptions.Timeout:
            return dbc.Alert(
                [
                    html.I(className="bi bi-clock me-2"),
                    html.Strong("Timeout: "),
                    "Request took too long. Please try again."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            ), no_update
        except Exception as e:
            logger.error(f"Create workspace error: {str(e)}")
            return dbc.Alert(
                [
                    html.I(className="bi bi-x-circle me-2"),
                    html.Strong("Connection Error: "),
                    "Unable to create workspace. Please check your connection."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            ), no_update
    
    @app.callback(
        Output('create-workspace-modal', 'is_open'),
        [Input('open-create-workspace-modal', 'n_clicks'),
         Input('close-create-workspace-modal', 'n_clicks'),
         Input('confirm-create-workspace', 'n_clicks')],
        [State('create-workspace-modal', 'is_open'),
         State('new-workspace-name-modal', 'value')],
        prevent_initial_call=True
    )
    def toggle_create_workspace_modal(open_clicks, close_clicks, confirm_clicks, is_open, workspace_name):
        """Toggle create workspace modal"""
        ctx = callback_context
        if not ctx.triggered:
            return no_update
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'open-create-workspace-modal':
            return True
        
        if button_id == 'close-create-workspace-modal':
            return False
        
        if button_id == 'confirm-create-workspace':
            if workspace_name and workspace_name.strip():
                return False
            return True
        
        return is_open
    
    @app.callback(
        [Output('create-workspace-modal-feedback', 'children'),
         Output('new-workspace-name-modal', 'value'),
         Output('current-workspace', 'data', allow_duplicate=True)],
        [Input('confirm-create-workspace', 'n_clicks')],
        [State('new-workspace-name-modal', 'value'),
         State('auth-token', 'data')],
        prevent_initial_call=True
    )
    def create_workspace_from_modal(n_clicks, workspace_name, token):
        """Create workspace from dashboard modal"""
        if not n_clicks:
            return "", no_update, no_update
        
        if not workspace_name or not workspace_name.strip():
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Please enter a workspace name"
                ],
                color="warning",
                dismissable=True,
                duration=4000
            ), no_update, no_update
        
        if not token:
            return dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Authentication required. Please log in again."
                ],
                color="warning",
                dismissable=True,
                duration=4000
            ), no_update, no_update
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/workspaces?token={token}",
                json={"name": workspace_name.strip()},
                timeout=50
            )
            
            if response.status_code == 200:
                new_workspace = response.json()
                new_workspace_id = new_workspace.get('id')
                
                logger.info(f"âœ… Workspace '{workspace_name.strip()}' created from modal")
                
                return dbc.Alert(
                    [
                        html.I(className="bi bi-check-circle me-2"),
                        html.Strong("Success! "),
                        f"Workspace '{workspace_name.strip()}' created. Switching to it now..."
                    ],
                    color="success",
                    dismissable=True,
                    duration=3000
                ), "", new_workspace_id
            else:
                error = response.json().get('detail', 'Failed to create workspace')
                logger.error(f"Create workspace from modal failed: {response.status_code} - {error}")
                return dbc.Alert(
                    [
                        html.I(className="bi bi-x-circle me-2"),
                        html.Strong("Error: "),
                        f"{error}"
                    ],
                    color="danger",
                    dismissable=True,
                    duration=5000
                ), no_update, no_update
        except requests.exceptions.Timeout:
            return dbc.Alert(
                [
                    html.I(className="bi bi-clock me-2"),
                    html.Strong("Timeout: "),
                    "Request took too long. Please try again."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            ), no_update, no_update
        except Exception as e:
            logger.error(f"Create workspace from modal error: {str(e)}")
            return dbc.Alert(
                [
                    html.I(className="bi bi-x-circle me-2"),
                    html.Strong("Connection Error: "),
                    "Unable to create workspace. Please check your connection."
                ],
                color="danger",
                dismissable=True,
                duration=5000
            ), no_update, no_update