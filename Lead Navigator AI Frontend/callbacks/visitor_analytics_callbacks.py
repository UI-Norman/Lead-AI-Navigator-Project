from dash import Input, Output, State, callback, no_update, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table
from components.charts import create_kpi_card
from utils.metrics import (
    find_column, calculate_total_revenue,calculate_aov, calculate_repeat_rate, calculate_ltv_90day,
    calculate_gross_vs_refunded, calculate_cac, get_channel_performance
)
from datetime import datetime, timedelta
import logging
from components.charts import create_new_vs_returning_chart
logger = logging.getLogger(__name__)

def register_visitor_analytics_callbacks(app):
    """Register callbacks for visitors analytics page with COMPLETE metrics"""
    
    # ========================================================================
    # CALLBACK 1: Show/Hide Analytics Content
    # ========================================================================
    @app.callback(
        Output('visitors-analytics-content', 'style'),
        [Input('visitors-data', 'data')]
    )
    def show_hide_visitors_analytics(visitors_data):
        """Show analytics content only when visitor data is uploaded"""
        if visitors_data:
            return {'display': 'block'}  
        return {'display': 'none'}     
    
    # ========================================================================
    # ✅ FIXED CALLBACK 2: Update REVENUE & CONVERSION KPIs
    # ========================================================================
    # @app.callback(
    #     [Output('visitor-kpi-revenue', 'children'),
    #     Output('visitor-kpi-aov', 'children'),
    #     Output('visitor-kpi-repeat', 'children'),
    #     Output('visitor-kpi-ltv', 'children'),
    #     Output('visitor-kpi-gross', 'children'),
    #     Output('visitor-kpi-cac', 'children')],  
    #     [Input('visitors-data', 'data'),
    #     Input('buyers-data', 'data')]
    # )
    # def update_visitor_revenue_kpis(visitors_data, buyers_data):
    #     """✅ FIXED: Calculate revenue metrics WITHOUT conversion rate"""
    #     if not visitors_data:
    #         logger.warning("❌ No visitors data - returning empty KPIs")
    #         return "", "", "", "", "", ""  # ✅ Now 6 outputs instead of 7
        
    #     try:
    #         visitors_df = pd.DataFrame(visitors_data)
            
    #         logger.info(f"📊 Calculating visitor revenue KPIs: {len(visitors_df)} visitor rows")
            
    #         # Calculate all metrics (EXCEPT conversion rate)
    #         total_revenue = calculate_total_revenue(visitors_df)
    #         aov = calculate_aov(visitors_df)
    #         repeat_rate = calculate_repeat_rate(visitors_df)
    #         ltv = calculate_ltv_90day(visitors_df)
    #         revenue_data = calculate_gross_vs_refunded(visitors_df)
    #         gross = revenue_data.get("gross", 0)
    #         refunded = revenue_data.get("refunded", 0)
    #         cac = calculate_cac(visitors_df, None)
            
    #         logger.info(f"✅ Visitor Revenue KPIs Calculated:")
    #         logger.info(f"   - Total Revenue: ${total_revenue:,.2f}")
    #         logger.info(f"   - AOV: ${aov:,.2f}")
    #         logger.info(f"   - Repeat Rate: {repeat_rate:.2f}%")
    #         logger.info(f"   - LTV: ${ltv:,.2f}")
    #         logger.info(f"   - CAC: ${cac:,.2f}")
            
    #         return (
    #             create_kpi_card("Total Revenue", f"${total_revenue:,.2f}", "Estimated visitor value", "success"),
    #             create_kpi_card("AOV", f"${aov:,.2f}", "Avg value per visitor", "primary"),
    #             create_kpi_card("Repeat Rate", f"{repeat_rate:.2f}%", "Returning visitors", "warning"),
    #             create_kpi_card("LTV (90d)", f"${ltv:,.2f}", "Visitor lifetime value", "danger"),
    #             create_kpi_card("Gross/Refunded", f"${gross:,.2f} / ${refunded:,.2f}", "Value breakdown", "secondary"),
    #             create_kpi_card("CAC", f"${cac:,.2f}", "Cost per visitor", "dark")
    #         )
        
    #     except Exception as e:
    #         logger.error(f"❌ Error calculating visitor KPIs: {e}")
    #         import traceback
    #         traceback.print_exc()
            
    #         # Return error cards (6 outputs)
    #         error_card = create_kpi_card("Error", "Calculation failed", "Check logs", "danger")
    #         return error_card, error_card, error_card, error_card, error_card, error_card
        
    # ========================================================================
    # CALLBACK 3: Update DEMOGRAPHIC KPIs
    # ========================================================================
    @app.callback(
        [Output('visitor-total-card', 'children'),
         Output('visitor-unique-card', 'children'),
         Output('visitor-male-card', 'children'),
         Output('visitor-female-card', 'children')],
        [Input('visitors-data', 'data')]
    )
    def update_visitor_demographic_kpis(visitors_data):
        """Update visitor demographic KPI cards"""
        if not visitors_data:
            return "", "", "", ""
        
        try:
            df = pd.DataFrame(visitors_data)
            
            total = len(df)
            
            # Unique visitors
            email_col = find_column(df, ['email', 'user_id', 'visitor_id', 'uuid'])
            unique = df[email_col].nunique() if email_col else total
            
            # Gender breakdown
            gender_col = find_column(df, ['gender', 'sex'])
            male = 0
            female = 0
            if gender_col:
                try:
                    male = len(df[df[gender_col].astype(str).str.upper().isin(['M', 'MALE'])])
                    female = len(df[df[gender_col].astype(str).str.upper().isin(['F', 'FEMALE'])])
                except Exception as e:
                    logger.error(f"Error calculating gender breakdown: {e}")
            
            logger.info(f"📊 Demographic KPIs - Total: {total}, Unique: {unique}, Male: {male}, Female: {female}")
            
            return (
                create_kpi_card("Total Visitors", f"{total:,}", "All time", "info"),
                create_kpi_card("Unique Visitors", f"{unique:,}", f"{(unique/total*100):.1f}%", "primary"),
                create_kpi_card("Male", f"{male:,}", f"{(male/total*100 if total > 0 else 0):.1f}%", "primary"),
                create_kpi_card("Female", f"{female:,}", f"{(female/total*100 if total > 0 else 0):.1f}%", "danger")
            )
        
        except Exception as e:
            logger.error(f"❌ Error calculating demographic KPIs: {e}")
            import traceback
            traceback.print_exc()
            return "", "", "", ""
    
    # ========================================================================
    # ✅ NEW CALLBACK 4: Top 15 Channels Performance Chart
    # ========================================================================
    @app.callback(
        Output('visitor-channel-performance-chart', 'figure'),
        [Input('visitors-data', 'data')]
    )
    def update_visitor_channel_chart(visitors_data):
        """✅ NEW: Create Top 15 Channels performance chart for visitors"""
        if not visitors_data:
            empty = go.Figure()
            empty.update_layout(annotations=[{"text": "Upload visitor data to see channel performance", "showarrow": False}])
            return empty
        
        try:
            df = pd.DataFrame(visitors_data)
            
            logger.info(f"📊 Creating visitor channel performance chart: {len(df)} rows")
            
            # Use the existing get_channel_performance function
            from components.charts import create_channel_performance_chart
            
            channel_df = get_channel_performance(df)
            
            if channel_df.empty:
                empty = go.Figure()
                empty.update_layout(annotations=[{"text": "No channel data available", "showarrow": False}])
                return empty
            
            # Create the chart with visitor-specific title
            fig = create_channel_performance_chart(channel_df)
            fig.update_layout(title="Top 15 Visitor Sources/Channels")
            
            logger.info(f"✅ Visitor channel chart created with {len(channel_df)} channels")
            
            return fig
        
        except Exception as e:
            logger.error(f"❌ Error creating visitor channel chart: {e}")
            import traceback
            traceback.print_exc()
            
            empty = go.Figure()
            empty.update_layout(annotations=[{"text": f"Error: {str(e)[:50]}", "showarrow": False}])
            return empty
    
    # ========================================================================
    # CALLBACK 5: Update Demographic Charts
    # ========================================================================
    @app.callback(
        [Output('visitor-gender-chart', 'figure'),
         Output('visitor-age-chart', 'figure'),
         Output('visitor-income-chart', 'figure'),
         Output('visitor-state-chart', 'figure')],
        [Input('visitors-data', 'data')]
    )
    def update_visitor_charts(visitors_data):
        """Update visitor demographic charts"""
        if not visitors_data:
            empty = go.Figure()
            empty.update_layout(annotations=[{"text": "No data", "showarrow": False}])
            return empty, empty, empty, empty
        
        df = pd.DataFrame(visitors_data)
        
        # Gender Chart
        gender_col = find_column(df, ['gender', 'sex'])
        if gender_col:
            try:
                gender_counts = df[gender_col].value_counts()
                gender_fig = px.pie(
                    values=gender_counts.values,
                    names=gender_counts.index,
                    title="Gender Distribution",
                    color_discrete_sequence=['#3498db', '#e74c3c', '#95a5a6']
                )
            except Exception as e:
                logger.error(f"Error creating gender chart: {e}")
                gender_fig = go.Figure()
                gender_fig.update_layout(annotations=[{"text": "Error loading gender data", "showarrow": False}])
        else:
            gender_fig = go.Figure()
            gender_fig.update_layout(annotations=[{"text": "No gender data", "showarrow": False}])
        
        # Age Chart
        age_col = find_column(df, ['age', 'age_range'])
        if age_col:
            try:
                age_counts = df[age_col].value_counts().sort_index()
                age_fig = px.bar(
                    x=age_counts.index,
                    y=age_counts.values,
                    title="Age Distribution",
                    labels={'x': 'Age Range', 'y': 'Count'},
                    color=age_counts.values,
                    color_continuous_scale='Blues'
                )
            except Exception as e:
                logger.error(f"Error creating age chart: {e}")
                age_fig = go.Figure()
                age_fig.update_layout(annotations=[{"text": "Error loading age data", "showarrow": False}])
        else:
            age_fig = go.Figure()
            age_fig.update_layout(annotations=[{"text": "No age data", "showarrow": False}])
        
        # Income Chart
        income_col = find_column(df, ['income', 'income_range'])
        if income_col:
            try:
                income_counts = df[income_col].value_counts().head(10)
                income_fig = px.bar(
                    x=income_counts.values,
                    y=income_counts.index,
                    orientation='h',
                    title="Top Income Ranges",
                    labels={'x': 'Count', 'y': 'Income Range'},
                    color=income_counts.values,
                    color_continuous_scale='Greens'
                )
            except Exception as e:
                logger.error(f"Error creating income chart: {e}")
                income_fig = go.Figure()
                income_fig.update_layout(annotations=[{"text": "Error loading income data", "showarrow": False}])
        else:
            income_fig = go.Figure()
            income_fig.update_layout(annotations=[{"text": "No income data", "showarrow": False}])
        
        # State Chart
        state_col = find_column(df, ['state', 'region'])
        if state_col:
            try:
                state_counts = df[state_col].value_counts().head(15)
                state_fig = px.bar(
                    x=state_counts.values,
                    y=state_counts.index,
                    orientation='h',
                    title="Top 15 States",
                    labels={'x': 'Visitors', 'y': 'State'},
                    color=state_counts.values,
                    color_continuous_scale='Reds'
                )
            except Exception as e:
                logger.error(f"Error creating state chart: {e}")
                state_fig = go.Figure()
                state_fig.update_layout(annotations=[{"text": "Error loading location data", "showarrow": False}])
        else:
            state_fig = go.Figure()
            state_fig.update_layout(annotations=[{"text": "No location data", "showarrow": False}])
        
        return gender_fig, age_fig, income_fig, state_fig
    
    # ========================================================================
    # CALLBACK 6: Display Full Visitor Data Table
    # ========================================================================
    @app.callback(
        Output('visitor-data-table', 'children'),
        [Input('visitors-data', 'data')]
    )
    def update_visitor_table(visitors_data):
        """Display FULL visitors data table"""
        if not visitors_data:
            return html.Div([
                html.I(className="bi bi-inbox text-muted", style={"fontSize": "64px"}),
                html.H5("No Visitor Data Available", className="mt-3 text-muted"),
                html.P("Upload visitor data to see the table", className="text-muted")
            ], className="text-center py-5")
        
        df = pd.DataFrame(visitors_data)
        total_rows = len(df)
        display_rows = min(100, total_rows)
        
        return html.Div([
            # Stats row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_rows:,}", className="mb-0 text-info"),
                        html.Small("Total Rows", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H4(f"{len(df.columns)}", className="mb-0 text-primary"),
                        html.Small("Columns", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H4(f"{display_rows}", className="mb-0 text-warning"),
                        html.Small("Displayed", className="text-muted")
                    ], className="text-center")
                ], width=4)
            ], className="mb-3"),
            
            html.Hr(),
            
            # Data table
            dash_table.DataTable(
                data=df.head(display_rows).to_dict('records'),
                columns=[{"name": col, "id": col} for col in df.columns],
                page_size=20,
                page_action='native',
                sort_action='native',
                filter_action='native',
                style_table={'overflowX': 'auto', 'maxHeight': '500px', 'overflowY': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '13px'},
                style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
                ]
            ),
            
            # Truncation warning
            dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                f"Showing first {display_rows} of {total_rows:,} rows for performance"
            ], color="info", className="mt-3 mb-0") if total_rows > display_rows else None
        ])
    
    # ========================================================================
    # CALLBACK 7: Populate Filter Dropdowns
    # ========================================================================
    @app.callback(
        [Output('visitor-gender-filter', 'options'),
         Output('visitor-age-filter', 'options'),
         Output('visitor-income-filter', 'options'),
         Output('visitor-state-filter', 'options')],
        [Input('visitors-data', 'data')]
    )
    def update_visitor_filter_options(visitors_data):
        """Populate filter dropdowns with unique values"""
        if not visitors_data:
            return [], [], [], []
        
        df = pd.DataFrame(visitors_data)
        
        def get_unique_options(col_name):
            col = find_column(df, [col_name])
            if col and col in df.columns:
                vals = df[col].dropna().astype(str).str.strip()
                vals = vals[~vals.str.lower().isin(['nan', 'none', 'null', '', 'n/a'])]
                unique = sorted(vals.unique().tolist())
                return [{'label': v, 'value': v} for v in unique if v]
            return []
        
        return (
            get_unique_options('gender'),
            get_unique_options('age'),
            get_unique_options('income'),
            get_unique_options('state')
        )
    
    # ========================================================================
    # CALLBACK 8: Set Default Date Range
    # ========================================================================
    @app.callback(
        [Output('visitor-date-range-picker', 'start_date'),
         Output('visitor-date-range-picker', 'end_date')],
        [Input('visitors-data', 'data')]
    )
    def set_visitor_date_range(visitors_data):
        """Set default date range for visitors"""
        if not visitors_data:
            return None, None
        
        df = pd.DataFrame(visitors_data)
        
        # Find date column
        date_col = None
        for col in df.columns:
            if any(kw in col.lower() for kw in ['date', 'time', 'timestamp']):
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    if df[col].notna().sum() > 0:
                        date_col = col
                        break
                except:
                    continue
        
        if date_col:
            try:
                min_date = df[date_col].min().date()
                max_date = df[date_col].max().date()
                return min_date, max_date
            except:
                pass
        
        # Fallback: last 30 days
        end_date = datetime.now().date()
        start_date = (datetime.now() - timedelta(days=30)).date()
        return start_date, end_date
    
    # ========================================================================
    # CALLBACK 9: Apply Filters and Show Filtered Data
    # ========================================================================
    @app.callback(
        Output('visitor-filtered-data-table', 'children'),
        [Input('visitor-apply-filters', 'n_clicks'),
         Input('visitors-data', 'data')],
        [State('visitor-date-range-picker', 'start_date'),
         State('visitor-date-range-picker', 'end_date'),
         State('visitor-gender-filter', 'value'),
         State('visitor-age-filter', 'value'),
         State('visitor-income-filter', 'value'),
         State('visitor-state-filter', 'value')],
        prevent_initial_call=True
    )
    def update_filtered_visitor_table(n_clicks, visitors_data, start_date, end_date, 
                                       gender, age, income, state):
        """Display FILTERED visitors data table"""
        if not visitors_data:
            return html.Div([
                html.I(className="bi bi-funnel text-muted", style={"fontSize": "64px"}),
                html.H5("No Data to Filter", className="mt-3 text-muted"),
                html.P("Upload visitor data first", className="text-muted")
            ], className="text-center py-5")
        
        df = pd.DataFrame(visitors_data)
        original_count = len(df)
        
        # Apply filters
        filtered_df = df.copy()
        
        # Date filter
        if start_date and end_date:
            date_col = None
            for col in df.columns:
                if any(kw in col.lower() for kw in ['date', 'time', 'timestamp']):
                    try:
                        filtered_df[col] = pd.to_datetime(filtered_df[col], errors='coerce')
                        if filtered_df[col].notna().sum() > 0:
                            date_col = col
                            break
                    except:
                        continue
            
            if date_col:
                # ✅ FIX: Convert start/end to timezone-aware if needed
                try:
                    # Convert dates to datetime
                    start = pd.to_datetime(start_date)
                    end = pd.to_datetime(end_date)
                    
                    # Check if the DataFrame column is timezone-aware
                    if hasattr(filtered_df[date_col].dtype, 'tz') and filtered_df[date_col].dtype.tz is not None:
                        # Make start/end timezone-aware (UTC)
                        start = start.tz_localize('UTC') if start.tzinfo is None else start.tz_convert('UTC')
                        end = end.tz_localize('UTC') if end.tzinfo is None else end.tz_convert('UTC')
                        logger.info(f"📅 Using timezone-aware dates: {start} to {end}")
                    else:
                        # Column is timezone-naive, remove timezone from start/end if present
                        start = start.tz_localize(None) if start.tzinfo is not None else start
                        end = end.tz_localize(None) if end.tzinfo is not None else end
                        logger.info(f"📅 Using timezone-naive dates: {start} to {end}")
                    
                    # Now comparison will work
                    filtered_df = filtered_df[
                        (filtered_df[date_col] >= start) & (filtered_df[date_col] <= end)
                    ]
                    logger.info(f"✅ Date filter applied: {len(filtered_df)} rows remaining")
                    
                except Exception as e:
                    logger.error(f"❌ Date filter error: {e}")
                    # If date filtering fails, just skip it and continue with other filters
                    pass
        
        # Gender filter
        if gender:
            gender_col = find_column(df, ['gender', 'sex'])
            if gender_col:
                filtered_df = filtered_df[filtered_df[gender_col].isin(gender)]
        
        # Age filter
        if age:
            age_col = find_column(df, ['age', 'age_range'])
            if age_col:
                filtered_df = filtered_df[filtered_df[age_col].isin(age)]
        
        # Income filter
        if income:
            income_col = find_column(df, ['income', 'income_range'])
            if income_col:
                filtered_df = filtered_df[filtered_df[income_col].isin(income)]
        
        # State filter
        if state:
            state_col = find_column(df, ['state', 'region'])
            if state_col:
                filtered_df = filtered_df[filtered_df[state_col].isin(state)]
        
        filtered_count = len(filtered_df)
        display_rows = min(100, filtered_count)
        
        # Show message if no filters applied
        if not any([start_date, end_date, gender, age, income, state]):
            return dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                html.Strong("No Filters Applied"),
                html.Br(),
                html.Small("Select filters above and click 'Apply Filters' to see filtered data")
            ], color="info", className="text-center")
        
        # Show message if filters removed all data
        if filtered_count == 0:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                html.Strong("No Results Found"),
                html.Br(),
                html.Small("Try adjusting your filters")
            ], color="warning", className="text-center")
        
        return html.Div([
            # Filter summary
            dbc.Alert([
                html.Div([
                    html.I(className="bi bi-funnel-fill me-2"),
                    html.Strong("Filtered Results: "),
                    html.Span(f"{filtered_count:,} of {original_count:,} rows ", 
                              className="text-primary fw-bold"),
                    html.Span(f"({(filtered_count/original_count*100):.1f}%)", 
                              className="text-muted")
                ], className="mb-2"),
                
                html.Hr(className="my-2"),
                
                # Active filters
                html.Div([
                    html.Small("Active Filters: ", className="fw-bold"),
                    dbc.Badge(f"Gender: {len(gender)}", color="primary", className="me-1") if gender else None,
                    dbc.Badge(f"Age: {len(age)}", color="info", className="me-1") if age else None,
                    dbc.Badge(f"Income: {len(income)}", color="success", className="me-1") if income else None,
                    dbc.Badge(f"State: {len(state)}", color="warning", className="me-1") if state else None,
                    dbc.Badge("Date Range", color="secondary") if start_date and end_date else None
                ], className="d-flex align-items-center flex-wrap")
            ], color="light", className="mb-3"),
            
            # Stats row
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(f"{filtered_count:,}", className="mb-0 text-primary"),
                        html.Small("Filtered Rows", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H4(f"{len(filtered_df.columns)}", className="mb-0 text-info"),
                        html.Small("Columns", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H4(f"{display_rows}", className="mb-0 text-success"),
                        html.Small("Displayed", className="text-muted")
                    ], className="text-center")
                ], width=4)
            ], className="mb-3"),
            
            html.Hr(),
            
            # Filtered data table
            dash_table.DataTable(
                data=filtered_df.head(display_rows).to_dict('records'),
                columns=[{"name": col, "id": col} for col in filtered_df.columns],
                page_size=20,
                page_action='native',
                sort_action='native',
                filter_action='native',
                style_table={'overflowX': 'auto', 'maxHeight': '500px', 'overflowY': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '13px'},
                style_header={
                    'backgroundColor': '#e3f2fd',
                    'fontWeight': 'bold',
                    'color': '#1976d2'
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
                ]
            ),
            
            # Truncation warning
            dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                f"Showing first {display_rows} of {filtered_count:,} filtered rows"
            ], color="info", className="mt-3 mb-0") if filtered_count > display_rows else None
        ])
    
    # ========================================================================
    # CALLBACK 10: Reset Filters
    # ========================================================================
    @app.callback(
        [Output('visitor-date-range-picker', 'start_date', allow_duplicate=True),
         Output('visitor-date-range-picker', 'end_date', allow_duplicate=True),
         Output('visitor-gender-filter', 'value'),
         Output('visitor-age-filter', 'value'),
         Output('visitor-income-filter', 'value'),
         Output('visitor-state-filter', 'value')],
        [Input('visitor-reset-filters', 'n_clicks')],
        [State('visitors-data', 'data')],
        prevent_initial_call=True
    )
    def reset_visitor_filters(n_clicks, visitors_data):
        """Reset all visitor filters to default"""
        if not n_clicks:
            return [no_update] * 6
        
        logger.info("🔄 Resetting visitor filters")
        
        # Get default date range
        if visitors_data:
            df = pd.DataFrame(visitors_data)
            date_col = None
            
            for col in df.columns:
                if any(kw in col.lower() for kw in ['date', 'time', 'timestamp']):
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
                return [min_date, max_date, None, None, None, None]
        
        # Fallback
        end_date = datetime.now().date()
        start_date = (datetime.now() - timedelta(days=30)).date()
        return [start_date, end_date, None, None, None, None]
    # --------------------------------------------------------------
    # CALLBACK: New vs Returning Visitors
    # --------------------------------------------------------------
    @app.callback(
        Output('new-vs-returning-visitors', 'figure'),
        Input('visitors-data', 'data')
    )
    def update_new_vs_returning_visitors(visitors_data):
        """Create bigger pie chart with better empty state"""
        
        # ============================================
        # EMPTY STATE - No Data Uploaded
        # ============================================
        if not visitors_data:
            fig = go.Figure()
            fig.add_annotation(
                text="📊 Upload Visitor Data to See Chart",
                xref="paper", yref="paper",
                x=0.5, y=0.5, 
                showarrow=False,
                font=dict(size=24, color="#999999", family="Arial")
            )
            fig.add_annotation(
                text="Go to the upload section above and upload your visitors CSV file",
                xref="paper", yref="paper",
                x=0.5, y=0.4, 
                showarrow=False,
                font=dict(size=14, color="#cccccc")
            )
            fig.update_layout(
                xaxis={"visible": False},
                yaxis={"visible": False},
                height=600,
                plot_bgcolor='white',
                paper_bgcolor='white',
                margin=dict(t=50, b=50, l=50, r=50)
            )
            return fig
        
        # ============================================
        # DATA EXISTS - Create Pie Chart
        # ============================================
        df = pd.DataFrame(visitors_data)
        
        # Find visitor ID column
        id_col = find_column(df, ['visitor_id', 'visitors', 'session_id', 'email', 'user_id', 'customer_id', 'hemsha256'])
        
        if not id_col:
            # Dynamically find First Name, Last Name, and State columns
            first_name_col = find_column(df, ['first name', 'First Name', 'fname', 'first_name'])
            last_name_col = find_column(df, ['last name', 'Last Name', 'lname', 'last_name'])
            state_col = find_column(df, ['state', 'State', 'state_code', 'region'])
            
            if first_name_col and last_name_col and state_col:
                # Create composite ID using found columns
                df['id_col'] = df[first_name_col].fillna('') + ' ' + df[last_name_col].fillna('') + ' ' + df[state_col].fillna('')
                df = df.dropna(subset=['id_col'])  # Remove rows where the composite ID is empty
                id_col = 'id_col'  # Use the new composite column
            else:
                fig = go.Figure()
                fig.add_annotation(
                    text="❌ No Suitable Columns Found",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, 
                    showarrow=False,
                    font=dict(size=20, color="red")
                )
                fig.add_annotation(
                    text="Data needs columns like: First Name, Last Name, and State (or variants)",
                    xref="paper", yref="paper",
                    x=0.5, y=0.4, 
                    showarrow=False,
                    font=dict(size=14, color="#999")
                )
                fig.update_layout(
                    xaxis={"visible": False}, 
                    yaxis={"visible": False}, 
                    height=600,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                return fig
        
        # Count visits per visitor
        visits = df[id_col].value_counts()
        new = (visits == 1).sum()
        returning = (visits > 1).sum()
        
        # Create BIGGER pie chart
        fig = go.Figure(
            data=[go.Pie(
                labels=['New Visitors', 'Returning Visitors'],
                values=[new, returning],
                hole=0.4,  # Donut chart
                marker=dict(colors=['#36A2EB', '#FF6384']),
                textinfo='label+percent+value',
                texttemplate='<b>%{label}</b><br>%{percent}<br>%{value:,} visitors',
                textfont=dict(size=16),
                pull=[0.05, 0.05]
            )]
        )
        
        # Make it BIGGER
        fig.update_layout(
            title={
                'text': "New vs Returning Visitors",
                'font': {'size': 24, 'color': '#2c3e50'},
                'x': 0.5,
                'xanchor': 'center'
            },
            height=500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5,
                font=dict(size=14)
            ),
            margin=dict(t=150, b=80, l=40, r=40),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return fig