# ============================================================================
# COMPLETE UPDATED FILE: callbacks/upload_callbacks.py
# ============================================================================

from dash import Input, Output, State, callback, no_update, html, dcc, callback_context
import dash_bootstrap_components as dbc
import dash
import requests
import base64
import pandas as pd
from io import StringIO, BytesIO
import logging
import jwt
import chardet
import gzip
import zipfile
import json
import os
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env")

# Get API URL from environment
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise EnvironmentError("API_BASE_URL is required in .env file")

# ============================================================================
# FILE SIZE CONFIGURATION
# ============================================================================

MAX_ROWS = 16000  # Maximum rows to store in browser
PREVIEW_ROWS = 10  # Rows to show in preview
MAX_FILE_SIZE_MB = 2048  # 2GB max file size

# Size thresholds for different handling
SMALL_FILE_MB = 10    # < 10MB: Standard processing
MEDIUM_FILE_MB = 50   # 10-50MB: Show progress
LARGE_FILE_MB = 200   # 50-200MB: Chunked reading
HUGE_FILE_MB = 500    # > 500MB: Show warning

def get_file_size_category(size_mb):
    """Categorize file size"""
    if size_mb < SMALL_FILE_MB:
        return "small", "success"
    elif size_mb < MEDIUM_FILE_MB:
        return "medium", "info"
    elif size_mb < LARGE_FILE_MB:
        return "large", "warning"
    else:
        return "huge", "danger"

def create_loading_message(filename, file_size_mb):
    """Show loading message for large files"""
    if file_size_mb > MEDIUM_FILE_MB:
        return dbc.Alert([
            dcc.Loading(
                type="circle",
                children=[
                    html.Div([
                        html.H5([
                            html.I(className="bi bi-hourglass-split me-2"),
                            "Processing Large File..."
                        ], className="mb-2"),
                        html.P(f"📁 {filename} ({file_size_mb:.1f} MB)", className="mb-2"),
                        html.Small("This may take 30-60 seconds. Using chunked reading for optimal performance.", 
                                   className="text-muted")
                    ])
                ]
            )
        ], color="info")
    return None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_column_names(df):
    """Normalize column names to lowercase and remove spaces"""
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_').str.replace('[^a-z0-9_]', '', regex=True)
    return df

def detect_separator(sample_text):
    """Detect CSV separator"""
    separators = {',': sample_text.count(','), '\t': sample_text.count('\t'), ';': sample_text.count(';'), '|': sample_text.count('|')}
    max_sep = max(separators.items(), key=lambda x: x[1])
    if max_sep[1] > 0:
        logger.debug(f"Detected separator: {repr(max_sep[0])}")
        return max_sep[0]
    return ','

def decode_with_multiple_encodings(content):
    """Try multiple encodings to decode binary content"""
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16', 'ascii']
    
    try:
        result = chardet.detect(content[:100000])
        detected = result.get('encoding')
        if detected and result.get('confidence', 0) > 0.7:
            encodings.insert(0, detected)
    except:
        pass
    
    for encoding in encodings:
        try:
            decoded = content.decode(encoding)
            logger.info(f"✅ Decoded with: {encoding}")
            return decoded, encoding
        except:
            continue
    
    decoded = content.decode('latin-1', errors='ignore')
    return decoded, 'latin-1 (with ignored errors)'

def decompress_if_needed(content, filename):
    """Decompress GZIP or ZIP files"""
    if filename.lower().endswith('.gz') or content[:2] == b'\x1f\x8b':
        try:
            decompressed = gzip.decompress(content)
            logger.info(f"✅ Decompressed GZIP")
            return decompressed
        except:
            return content
    
    if filename.lower().endswith('.zip') or content[:4] == b'PK\x03\x04':
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                csv_files = [f for f in zf.namelist() if f.lower().endswith(('.csv', '.tsv', '.txt'))]
                if csv_files:
                    return zf.read(csv_files[0])
        except:
            pass
    
    return content

def read_csv_universal(content, filename):
    """Universal CSV reader with chunked reading for large files"""
    try:
        content = decompress_if_needed(content, filename)
        text_content, encoding = decode_with_multiple_encodings(content)
        separator = detect_separator(text_content[:10000])
        file_size_mb = len(text_content) / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.2f} MB")
        use_chunks = file_size_mb > 10
        
        if use_chunks:
            logger.info(f"⚡ Using chunked reading for large file")
            chunks = []
            chunk_size = 10000
            for chunk in pd.read_csv(
                StringIO(text_content),
                sep=separator,
                chunksize=chunk_size,
                on_bad_lines='skip',
                engine='c'
            ):
                chunks.append(chunk)
                if sum(len(c) for c in chunks) >= MAX_ROWS:
                    logger.info(f"⚠️ Reached {MAX_ROWS} row limit")
                    break
            df = pd.concat(chunks, ignore_index=True)
            logger.info(f"✅ Chunked read successful: {len(df)} rows")
        else:
            read_attempts = [
                {'sep': separator, 'low_memory': False, 'on_bad_lines': 'skip', 'engine': 'c'},
                {'sep': separator, 'on_bad_lines': 'skip', 'engine': 'python'},
                {'sep': separator, 'low_memory': False, 'on_bad_lines': 'skip', 'engine': 'c', 'quoting': 3},
            ]
            last_error = None
            df = None
            for i, options in enumerate(read_attempts, 1):
                try:
                    logger.debug(f"Read attempt {i}/{len(read_attempts)}")
                    df = pd.read_csv(StringIO(text_content), **options)
                    logger.info(f"✅ Success with attempt {i}")
                    break
                except Exception as e:
                    last_error = e
                    logger.debug(f"Attempt {i} failed: {str(e)[:100]}")
                    continue
            if df is None:
                raise Exception(f"All read attempts failed. Last error: {str(last_error)}")
        
        if df.empty:
            raise Exception("DataFrame is empty after reading")
        
        original_rows = len(df)
        df = df.dropna(how='all')
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if df.empty:
            raise Exception("DataFrame is empty after cleanup")
        
        df = normalize_column_names(df)
        removed_rows = original_rows - len(df)
        if removed_rows > 0:
            logger.info(f"Removed {removed_rows} empty rows")
        
        info = {
            'encoding': encoding,
            'separator': repr(separator),
            'rows': len(df),
            'columns': len(df.columns),
            'file_size_mb': round(file_size_mb, 2),
            'used_chunks': use_chunks
        }
        logger.info(f"✅ Final: {len(df):,} rows × {len(df.columns)} columns")
        return df, info
    
    except Exception as e:
        logger.error(f"❌ Parse error: {e}")
        import traceback
        traceback.print_exc()
        raise

# ============================================================================
# REGISTER CALLBACKS
# ============================================================================

def register_upload_callbacks(app):
    """Register upload callbacks with ENHANCED display for large files"""
    
    @app.callback(
        [Output('upload-status', 'children'),
         Output('upload-preview', 'children'),
         Output('buyers-data', 'data'),
         Output('visitors-data', 'data'),
         Output('upload-trigger', 'data'),
         Output('recent-uploads', 'data')],
        [Input('upload-data', 'contents')],
        [State('upload-data', 'filename'),
         State('file-type-dropdown', 'value'),
         State('auth-token', 'data'),
         State('current-workspace', 'data'),
         State('recent-uploads', 'data')],
        prevent_initial_call=True
    )
    def handle_file_upload(contents, filename, file_type, token, workspace_id, recent_uploads):
        """Handle file upload with ENHANCED preview and stats display"""
        if not contents:
            return "", "", no_update, no_update, no_update, no_update
        
        if not token:
            error_msg = dbc.Alert([
                html.H5("❌ Please Log In", className="alert-heading"),
                html.P("No authentication token found."),
                dbc.Button("Go to Login", href="/", color="primary", className="mt-2")
            ], color="warning")
            return error_msg, "", no_update, no_update, no_update, no_update
        
        try:
            token_response = requests.get(
                f"{API_BASE_URL}/users/me?token={token}",
                timeout=300
            )
            if token_response.status_code != 200:
                error_msg = dbc.Alert([
                    html.H5("❌ Authentication Failed", className="alert-heading"),
                    html.P("Your session has expired or is invalid."),
                    dbc.Button("Re-login", href="/", color="primary", className="mt-2")
                ], color="danger")
                return error_msg, "", no_update, no_update, no_update, no_update
            
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            # ================================================================
            # FILE SIZE VALIDATION
            # ================================================================
            file_size_mb = len(decoded) / (1024 * 1024)
            file_category, badge_color = get_file_size_category(file_size_mb)
            
            logger.info(f"📦 File size: {file_size_mb:.2f} MB ({file_category})")
            
            # Show warning for very large files
            if file_size_mb > MAX_FILE_SIZE_MB:
                error_msg = dbc.Alert([
                    html.H5("⚠️ File Too Large", className="alert-heading"),
                    html.P(f"File size: {file_size_mb:.1f} MB exceeds maximum ({MAX_FILE_SIZE_MB} MB)"),
                    html.Hr(),
                    html.H6("💡 Solutions:"),
                    html.Ul([
                        html.Li("Split file into smaller chunks (recommended < 200 MB)"),
                        html.Li("Filter data before exporting"),
                        html.Li("Use database import for files > 1 GB"),
                        html.Li("Compress with GZIP (we support .gz files)")
                    ])
                ], color="danger")
                return error_msg, "", no_update, no_update, no_update, no_update
            
            logger.info(f"File size: {len(decoded):,} bytes")
            
            df, file_info = read_csv_universal(decoded, filename)
            total_rows = len(df)
            columns = df.columns.tolist()
            
            if total_rows > MAX_ROWS:
                df = df.head(MAX_ROWS)
                logger.warning(f"⚠️ Truncated to {MAX_ROWS} rows")
            
            workspace_id = workspace_id or 1
            backend_success = False
            backend_error = None
            
            try:
                files = {'file': (filename, decoded, 'text/csv')}
                data = {'file_type': file_type}
                response = requests.post(
                    f"{API_BASE_URL}/workspaces/{workspace_id}/upload?token={token}",
                    files=files,
                    data=data,
                    timeout=300
                )
                if response.status_code == 200:
                    upload_info = response.json()
                    backend_success = True
                    logger.info("✅ Backend upload successful")
                else:
                    error_detail = response.json().get('detail', 'Unknown error') if response.text else response.text
                    backend_error = f"Backend error (Status {response.status_code}): {error_detail}"
                    logger.error(backend_error)
            
            except requests.exceptions.Timeout:
                backend_error = "Backend request timed out"
                logger.error(backend_error)
            except Exception as e:
                backend_error = f"Backend error: {str(e)}"
                logger.error(f"Backend upload failed: {e}")
            
            # Store COMPLETE data as records
            data_dict = df.to_dict('records')
            buyers_data = data_dict if file_type == 'buyers' else no_update
            visitors_data = data_dict if file_type == 'visitors' else no_update
            logger.info(f"✅ Stored {len(data_dict)} rows in {file_type}-data store")
            
            # ================================================================
            # ENHANCED STATUS MESSAGE
            # ================================================================
            
            stored_rows = len(df)
            is_truncated = total_rows > MAX_ROWS
            
            # Determine icon and color based on file type
            file_type_config = {
                'buyers': {
                    'icon': 'bi-cart-fill',
                    'color': 'success',
                    'label': 'Buyers Data',
                    'description': 'Customer purchase records'
                },
                'visitors': {
                    'icon': 'bi-people-fill',
                    'color': 'info',
                    'label': 'Visitors Data',
                    'description': 'Website visitor analytics'
                }
            }

            config = file_type_config.get(file_type, {
                'icon': 'bi-file-earmark',
                'color': 'primary',
                'label': file_type.title(),
                'description': 'Data file'
            })
            # Add visual confirmation banner
            confirmation_banner = dbc.Alert([
                html.Div([
                    html.I(className=f"{config['icon']} me-3", style={'fontSize': '48px'}),
                    html.Div([
                        html.H5(f"✅ Uploaded as {config['label']}", className="mb-1"),
                        html.P(f"Your file has been stored as {file_type} data and is ready for analysis.", 
                               className="mb-0 text-muted")
                    ])
                ], className="d-flex align-items-center")
            ], color=config['color'], className="mb-3 p-4")
            status_items = [
                html.Div([
                    # Success Header with File Type Badge
                    html.H4([
                        html.I(className="bi bi-check-circle-fill me-2 text-success"),
                        "File Processed Successfully!"
                    ], className="mb-2"),
                    
                    # File Type Badge
                    dbc.Badge([
                        html.I(className=f"{config['icon']} me-1"),
                        f"📁 {config['label']}"
                    ], color=config['color'], className="mb-3 p-2", style={'fontSize': '16px'}),
                    
                    html.P(config['description'], className="text-muted mb-3"),
                    
                    # Quick stats row
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{total_rows:,}", className="mb-0 text-primary"),
                                    html.Small("Total Rows", className="text-muted")
                                ], className="text-center py-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{len(columns)}", className="mb-0 text-info"),
                                    html.Small("Columns", className="text-muted")
                                ], className="text-center py-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{file_info.get('file_size_mb', 0):.1f} MB", className="mb-0 text-success"),
                                    html.Small("File Size", className="text-muted")
                                ], className="text-center py-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{stored_rows:,}", className="mb-0 text-warning"),
                                    html.Small("Stored", className="text-muted")
                                ], className="text-center py-2")
                            ], color="light")
                        ], width=3),
                    ], className="mb-3"),   
                    
                    # File details
                    html.Div([
                        html.Strong("📄 File: "), html.Span(filename), html.Br(),
                        html.Strong("📊 Type: "), html.Span(file_type.title()), html.Br(),
                        html.Strong("🔧 Encoding: "), html.Span(file_info['encoding']), html.Br(),
                        html.Strong("⚙️ Processing: "), 
                        html.Span('Chunked (Large File)' if file_info.get('used_chunks') else 'Standard'),
                    ], className="small text-muted")
                ])
            ]
            
            # Large file warning
            if is_truncated:
                status_items.append(
                    dbc.Alert([
                        html.I(className="bi bi-info-circle me-2"),
                        html.Strong("Info: "),
                        f"File has {total_rows:,} rows. Displaying first {MAX_ROWS:,} rows for performance. ",
                        html.A("Learn about handling large files →", href="#", className="alert-link")
                    ], color="info", className="mt-3 mb-0")
                )
            
            # Backend sync status
            if backend_success:
                status_items.append(
                    dbc.Alert([
                        html.I(className="bi bi-cloud-check me-2"),
                        "✅ Synced with backend server"
                    ], color="success", className="mt-2 mb-0")
                )
            elif backend_error:
                status_items.append(
                    dbc.Alert([
                        html.I(className="bi bi-exclamation-triangle me-2"),
                        "⚠️ Backend sync failed (data still available locally)",
                        html.Br(),
                        html.Small(backend_error, className="text-muted")
                    ], color="warning", className="mt-2 mb-0")
                )
            
            status = dbc.Alert(status_items, color="light", className="mb-3 border")
            
            # ================================================================
            # ENHANCED PREVIEW SECTION
            # ================================================================
            
            preview_rows = min(PREVIEW_ROWS, len(df))
            
            # File statistics card
            file_stats = dbc.Card([
                dbc.CardHeader([
                    html.I(className="bi bi-info-circle me-2"),
                    "File Information"
                ]),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.H3(f"{total_rows:,}", className="mb-0 text-primary"),
                                html.Small("Total Rows", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                        dbc.Col([
                            html.Div([
                                html.H3(f"{len(columns)}", className="mb-0 text-info"),
                                html.Small("Columns", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                        dbc.Col([
                            html.Div([
                                html.H3(f"{file_info.get('file_size_mb', 0):.2f} MB", className="mb-0 text-success"),
                                html.Small("File Size", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                        dbc.Col([
                            html.Div([
                                html.H3(file_info['encoding'][:8], className="mb-0 text-warning"),
                                html.Small("Encoding", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                    ]),
                    html.Hr(className="my-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.I(className="bi bi-hdd me-1"),
                                f"Stored: {stored_rows:,} rows",
                                html.Br(),
                                html.I(className="bi bi-gear me-1"),
                                f"Method: {'Chunked' if file_info.get('used_chunks') else 'Standard'}"
                            ], className="text-muted")
                        ], width=6),
                        dbc.Col([
                            html.Small([
                                html.I(className="bi bi-hash me-1"),
                                f"Separator: {file_info['separator']}",
                                html.Br(),
                                html.I(className="bi bi-calendar me-1"),
                                f"Uploaded: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                            ], className="text-muted")
                        ], width=6)
                    ])
                ])
            ], className="mb-3", color="light")
            
            # Warning if file was truncated
            truncation_warning = None
            if is_truncated:
                truncation_warning = dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    html.Strong("Large File Detected! "),
                    f"This file contains {total_rows:,} rows but only the first {MAX_ROWS:,} rows are stored and available for analysis. ",
                    html.Br(),
                    html.Small([
                        "💡 Tip: For full file analysis, consider: ",
                        html.Ul([
                            html.Li("Splitting file into smaller chunks"),
                            html.Li("Using database import for files > 1M rows"),
                            html.Li("Filtering data before upload")
                        ], className="mb-0 mt-2")
                    ])
                ], color="warning", className="mb-3")
            
            # Enhanced preview
            preview = html.Div([
                file_stats,
                truncation_warning,
                
                html.H5([
                    html.I(className="bi bi-eye me-2"),
                    f"Data Preview (First {preview_rows} of {stored_rows:,} stored rows)"
                ], className="mb-3"),
                
                # Preview table
                html.Div(dbc.Table.from_dataframe(
                    df.head(preview_rows),
                    striped=True,
                    bordered=True,
                    hover=True,
                    size='sm'
                ), className="table-responsive mb-3", style={'maxHeight': '400px', 'overflowY': 'auto'}),
                
                # Export button
                dbc.Button(
                    [
                        html.I(className="bi bi-download me-2"), 
                        f"Export All {stored_rows:,} Rows as CSV"
                    ],
                    id={'type': 'export-data-btn', 'file_type': file_type},
                    color="success",
                    size="sm",
                    className="me-2 mb-3",
                    n_clicks=0
                ),
                
                # Column viewer - expandable
                html.Details([
                    html.Summary([
                        html.I(className="bi bi-list-columns me-2"),
                        f"View All {len(columns)} Columns"
                    ], className="fw-bold mb-2 cursor-pointer"),
                    html.Div([
                        dbc.Badge(col, color="primary", className="me-2 mb-2")
                        for col in columns
                    ], className="mt-2")
                ], className="mb-3"),
                
                # Processing details - expandable
                html.Details([
                    html.Summary([
                        html.I(className="bi bi-cpu me-2"),
                        "Processing Details"
                    ], className="fw-bold mb-2 cursor-pointer text-muted"),
                    html.Div([
                        dbc.Table([
                            html.Tbody([
                                html.Tr([html.Td("Encoding", className="fw-bold"), html.Td(file_info['encoding'])]),
                                html.Tr([html.Td("Separator", className="fw-bold"), html.Td(file_info['separator'])]),
                                html.Tr([html.Td("Method", className="fw-bold"), html.Td('Chunked Reading' if file_info.get('used_chunks') else 'Standard')]),
                                html.Tr([html.Td("Original Rows", className="fw-bold"), html.Td(f"{total_rows:,}")]),
                                html.Tr([html.Td("Stored Rows", className="fw-bold"), html.Td(f"{stored_rows:,}")]),
                                html.Tr([html.Td("Columns", className="fw-bold"), html.Td(f"{len(columns)}")]),
                                html.Tr([html.Td("File Size", className="fw-bold"), html.Td(f"{file_info.get('file_size_mb', 0):.2f} MB")]),
                            ])
                        ], size='sm', bordered=True)
                    ], className="mt-2")
                ])
            ])
            
            # Update recent uploads locally
            recent_uploads = recent_uploads or {'uploads': []}
            new_upload = {
                'filename': filename,
                'file_type': file_type,
                'row_count': len(df),
                'upload_time': datetime.now().isoformat()
            }
            recent_uploads['uploads'] = [new_upload] + recent_uploads['uploads'][:4]
            
            return status, preview, buyers_data, visitors_data, filename, recent_uploads
        
        except Exception as e:
            error_msg = dbc.Alert([
                html.H5("❌ Error Processing File", className="alert-heading"),
                html.P(f"Error: {str(e)}", className="text-danger"),
                html.Hr(),
                html.H6("💡 Solutions:", className="mt-3"),
                html.Ul([
                    html.Li("Open in Excel → 'Save As' → CSV UTF-8"),
                    html.Li("Check for special characters"),
                    html.Li("Try a smaller sample first"),
                    html.Li("Remove merged cells or formatting"),
                    html.Li("Ensure it's actually CSV/TSV (not .xls)"),
                ]),
                html.Details([
                    html.Summary("🔍 Technical Details"),
                    html.Pre(str(e), className="small mt-2")
                ])
            ], color="danger")
            logger.error(f"❌ Upload error: {str(e)}")
            import traceback
            traceback.print_exc()
            return error_msg, "", no_update, no_update, no_update, no_update
    
    @app.callback(
        Output('recent-uploads-display', 'children'),
        [Input('auth-token', 'data'),
         Input('current-workspace', 'data'),
         Input('upload-trigger', 'data'),
         Input('recent-uploads', 'data')],
        prevent_initial_call=True
    )
    def load_recent_uploads(token, workspace_id, upload_trigger, recent_uploads):
        """Load recent uploads, prioritizing local data"""
        if not token:
            return html.P("Please log in", className="text-muted")
        
        uploads = recent_uploads.get('uploads', []) if recent_uploads else []
        
        try:
            workspace_id = workspace_id or 1
            response = requests.get(
                f"{API_BASE_URL}/workspaces/{workspace_id}/uploads?token={token}",
                timeout=300
            )
            if response.status_code == 200:
                backend_uploads = response.json().get('uploads', [])
                existing_filenames = {u['filename'] for u in uploads}
                for bu in backend_uploads:
                    if bu['filename'] not in existing_filenames:
                        uploads.append(bu)
                uploads = sorted(uploads, key=lambda x: x.get('upload_time', ''), reverse=True)[:5]
        except Exception as e:
            logger.error(f"Load uploads error: {e}")
        
        if not uploads:
            return html.Div([
                html.I(className="bi bi-inbox text-muted", style={"fontSize": "48px"}),
                html.P("No uploads yet", className="text-muted mt-2")
            ], className="text-center py-4")
        
        # File type icons
        file_type_icons = {
            'buyers': {'icon': 'bi-cart-fill', 'color': 'success'},
            'visitors': {'icon': 'bi-people-fill', 'color': 'info'}
        }

        items = []
        for upload in uploads:
            ftype = upload.get('file_type', 'unknown')
            icon_config = file_type_icons.get(ftype, {'icon': 'bi-file-earmark', 'color': 'secondary'})
            
            items.append(
                dbc.ListGroupItem([
                    html.Div([
                        # File Type Icon
                        html.I(className=f"{icon_config['icon']} me-2 text-{icon_config['color']}", 
                            style={'fontSize': '20px'}),
                        html.Div([
                            html.Strong(upload['filename']),
                            html.Br(),
                            html.Div([
                                dbc.Badge(
                                    ftype.title(), 
                                    color=icon_config['color'], 
                                    className="me-2"
                                ),
                                html.Small(
                                    f"{upload['row_count']:,} rows", 
                                    className="text-muted"
                                )
                            ])
                        ])
                    ], className="d-flex align-items-center")
                ])
            )
        
        return dbc.ListGroup(items)
    
    # Simplified export callback with proper pattern matching
    @app.callback(
        Output('download-data', 'data'),
        [Input({'type': 'export-data-btn', 'file_type': dash.ALL}, 'n_clicks')],
        [State('buyers-data', 'data'),
         State('visitors-data', 'data')],
        prevent_initial_call=True
    )
    def export_data(n_clicks_list, buyers_data, visitors_data):
        """✅ FIXED: Export data to CSV - Now works correctly!"""
        
        # Check if any button was clicked
        if not n_clicks_list or not any(n_clicks_list):
            return no_update
        
        # Get the triggered button's context
        ctx = callback_context
        if not ctx.triggered:
            return no_update
        
        # Parse which button was clicked
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        try:
            button_id = json.loads(triggered_id)
            file_type = button_id.get('file_type')
            
            logger.info(f"🎯 Export requested for: {file_type}")
            
            # Select correct data based on file type
            if file_type == 'buyers' and buyers_data:
                df = pd.DataFrame(buyers_data)
                filename = f'buyers_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            elif file_type == 'visitors' and visitors_data:
                df = pd.DataFrame(visitors_data)
                filename = f'visitors_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            else:
                logger.error(f"❌ No data available for {file_type}")
                return no_update
            
            # Validate DataFrame
            if df.empty:
                logger.error(f"❌ DataFrame is empty for {file_type}")
                return no_update
            
            logger.info(f"✅ Exporting {len(df)} rows to {filename}")
            # Return the download
            return dcc.send_data_frame(df.to_csv, filename, index=False)
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            import traceback
            traceback.print_exc()
            return no_update