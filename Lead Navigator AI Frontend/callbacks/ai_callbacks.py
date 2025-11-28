from dash import Input, Output, State, callback, no_update, html, dcc
import requests
import pandas as pd
import base64
import json
import logging
import os
from dotenv import load_dotenv

# ✅ ADD THESE IMPORTS
from utils.metrics import find_column

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env")

# Get API URL from environment
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise EnvironmentError("API_BASE_URL is required in .env file")

def register_ai_callbacks(app):
    """Register all AI assistant-related callbacks"""
    
    @app.callback(
        Output('ai-modal', 'is_open'),
        [Input('open-ai-modal', 'n_clicks'),
         Input('close-ai-modal', 'n_clicks')],
        [State('ai-modal', 'is_open')]
    )
    def toggle_ai_modal(open_clicks, close_clicks, is_open):
        """Toggle AI assistant modal"""
        if open_clicks or close_clicks:
            return not is_open
        return is_open
    
    @app.callback(
        [Output('ai-chat-history', 'children'),
         Output('ai-query-input', 'value')],
        [Input('send-ai-query', 'n_clicks')],
        [State('ai-query-input', 'value'),
         State('auth-token', 'data'),
         State('current-workspace', 'data'),
         State('ai-chat-history', 'children')]
    )
    def handle_ai_query(n_clicks, query, token, workspace_id, chat_history):
        """Handle AI query"""
        if not n_clicks or not query:
            return chat_history or [], ""
        
        if not token:
            error_msg = html.Div([
                html.Strong("Error: ", style={"color": "#dc3545"}),
                html.Span("Please log in to use the AI assistant")
            ], className="mb-2")
            return (chat_history or []) + [error_msg], ""
        
        if not workspace_id:
            error_msg = html.Div([
                html.Strong("Error: ", style={"color": "#dc3545"}),
                html.Span("No workspace selected. Please select a workspace.")
            ], className="mb-2")
            return (chat_history or []) + [error_msg], ""
        
        # Add user message immediately
        user_msg = html.Div([
            html.Strong("You: ", style={"color": "#007bff"}),
            html.Span(query)
        ], className="mb-2")
        
        # Add loading indicator
        loading_msg = html.Div([
            html.Strong("AI: ", style={"color": "#28a745"}),
            dcc.Loading(
                type="circle",
                children=html.Span("Thinking...", className="text-muted")
            )
        ], className="mb-3 p-3 bg-light rounded")
        
        updated_history = (chat_history or []) + [user_msg, loading_msg]
        
        # Prepare request
        form_data = {
            'query': query,
            'workspace_id': str(workspace_id)
        }
        
        try:
            # Send request to /ai/query
            response = requests.post(
                f"{API_BASE_URL}/ai/query?token={token}",
                data=form_data,
                timeout=50
            )
            response.raise_for_status()
            
            result = response.json()
            ai_response = result['response']
            
            # Build response message
            context_info = ""
            if result.get('context_used', False):
                context_info = f"\n(Context: {result.get('context_length', 0)} chars used)"
            
            # Replace loading message with actual response
            ai_msg = html.Div([
                html.Strong("AI: ", style={"color": "#28a745"}),
                html.Span(f"{ai_response}{context_info}", style={"whiteSpace": "pre-wrap"})
            ], className="mb-3 p-3 bg-light rounded")
            
            # Remove loading message and add actual response
            final_history = (chat_history or []) + [user_msg, ai_msg]
            
            return final_history, ""
            
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json().get('detail', 'AI request failed')
            except:
                error_detail = str(e)
            logger.error(f"HTTP error: {error_detail}")
            error_msg = html.Div([
                html.Strong("Error: ", style={"color": "#dc3545"}),
                html.Span(f"AI request failed: {error_detail}")
            ], className="mb-2")
            return (chat_history or []) + [user_msg, error_msg], ""
        
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            error_msg = html.Div([
                html.Strong("Error: ", style={"color": "#dc3545"}),
                html.Span("Request timed out. Please try again.")
            ], className="mb-2")
            return (chat_history or []) + [user_msg, error_msg], ""
        
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            error_msg = html.Div([
                html.Strong("Error: ", style={"color": "#dc3545"}),
                html.Span(f"Connection error: {str(e)}")
            ], className="mb-2")
            return (chat_history or []) + [user_msg, error_msg], ""
    
    @app.callback(
        Output('ai-query-input', 'value', allow_duplicate=True),
        [Input('ai-query-input', 'n_submit')],
        [State('send-ai-query', 'n_clicks')],
        prevent_initial_call=True
    )
    def handle_enter_key(n_submit, n_clicks):
        """Clear input when Enter is pressed"""
        if n_submit:
            return ""
        return no_update
    
    # ===================================================================
    # ✅ NEW CODE FOR VISITORS PAGE AI - ADD BELOW THIS LINE
    # ===================================================================
    
    @app.callback(
        Output('ai-modal-visitors', 'is_open'),
        [Input('open-ai-modal-visitors', 'n_clicks'),
         Input('close-ai-modal-visitors', 'n_clicks')],
        [State('ai-modal-visitors', 'is_open')],
        prevent_initial_call=True
    )
    def toggle_ai_modal_visitors(open_clicks, close_clicks, is_open):
        """Toggle AI assistant modal on visitors page"""
        if open_clicks or close_clicks:
            return not is_open
        return is_open
    
    # ============================================================
    # 🔧 FIXED CODE - Replace in ai_callbacks.py
    # ============================================================

    # Replace the handle_ai_query_visitors function with this version
    @app.callback(
        [Output('ai-chat-history-visitors', 'children'),
        Output('ai-query-input-visitors', 'value')],
        [Input('send-ai-query-visitors', 'n_clicks'),
        Input('clear-ai-chat-visitors', 'n_clicks')],
        [State('ai-query-input-visitors', 'value'),
        State('auth-token', 'data'),
        State('current-workspace', 'data'),
        State('ai-chat-history-visitors', 'children'),
        State('visitors-data', 'data')],
        prevent_initial_call=True
    )
    def handle_ai_query_visitors(send_clicks, clear_clicks, query, token, workspace_id, chat_history, visitors_data):
        """✅ MINIMAL: Send only raw query"""
        from dash import callback_context
        
        ctx = callback_context
        if not ctx.triggered:
            return chat_history or [], ""
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Clear chat
        if 'clear-ai-chat-visitors' in button_id and clear_clicks:
            return [
                html.Div([
                    html.I(className="bi bi-robot text-info me-2", style={'fontSize': '20px'}),
                    html.Span([
                        html.Strong("AI Assistant: ", className="text-info"),
                        "Chat cleared!"
                    ], className="text-muted")
                ], className="mb-2")
            ], ""
        
        # Validate
        if 'send-ai-query-visitors' not in button_id or not send_clicks or not query:
            return chat_history or [], ""
        
        if not token:
            error_msg = html.Div([
                html.Span("Please log in")
            ], className="mb-2 p-2 alert alert-danger")
            return (chat_history or []) + [error_msg], ""
        
        if not visitors_data:
            error_msg = html.Div([
                html.Span("Please upload visitors data first!")
            ], className="mb-2 p-2 alert alert-warning")
            return (chat_history or []) + [error_msg], ""
        
        # User message
        user_msg = html.Div([
            html.Div([
                html.Strong("You: ", className="text-primary"),
                html.Span(query)
            ], className="mb-2 p-2 bg-light rounded")
        ])
        
        # Loading
        loading_msg = html.Div([
            html.Div([
                html.Strong("AI: ", className="text-info"),
                dcc.Loading(type="circle", children=html.Span("...", className="text-muted"))
            ], className="mb-3 p-3 bg-light rounded")
        ])
        
        updated_history = (chat_history or []) + [user_msg, loading_msg]
        
        # ✅ SEND ONLY RAW QUERY
        try:
            import pandas as pd
            df = pd.DataFrame(visitors_data)
            total = len(df)
            
            logger.info(f"📊 Query: '{query}' ({total} records)")
            
            # ✅ JUST SEND THE QUERY - NO CONTEXT
            response = requests.post(
                f"{API_BASE_URL}/ai/query?token={token}",
                data={'query': query.strip(), 'workspace_id': str(workspace_id)},
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            if 'error' in result:
                error_msg = html.Div([html.Span(result.get('response', 'Error'))], className="alert alert-danger")
                return (chat_history or []) + [user_msg, error_msg], ""
            
            ai_response = result.get('response', 'No response')
            
            # Response message
            ai_msg = html.Div([
                html.Div([
                    html.Strong("AI: ", className="text-info"),
                    html.Div([
                        html.Span(ai_response, style={"whiteSpace": "pre-wrap"}),
                        html.Br(),
                        html.Small(f"📊 {total:,} records", className="text-muted mt-2 d-block")
                    ])
                ], className="mb-3 p-3 bg-light rounded")
            ])
            
            return (chat_history or []) + [user_msg, ai_msg], ""
            
        except Exception as e:
            logger.error(f"Error: {e}")
            error_msg = html.Div([html.Span(f"Error: {str(e)}")], className="alert alert-danger")
            return (chat_history or []) + [user_msg, error_msg], ""
    
    
    def handle_enter_key_visitors(n_submit):
        """Clear input when Enter is pressed on visitors page"""
        if n_submit:
            return ""
        return no_update