from dotenv import load_dotenv
from dash import Input, Output, State, callback, no_update, html
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime, timedelta
import requests
import os
import plotly.graph_objects as go
from urllib.parse import urlparse
from utils.metrics import (
    calculate_total_revenue, calculate_conversion_rate, calculate_aov,
    calculate_repeat_rate, calculate_ltv_90day, calculate_gross_vs_refunded,
    get_conversions_over_time, get_new_vs_returning, get_channel_performance,
    apply_filters, find_column, find_any_categorical_column, calculate_cac,
    calculate_buyer_kpis  # ✅ NEW IMPORT
)
from components.charts import (
    create_kpi_card, create_conversions_chart,
    create_new_vs_returning_chart, create_channel_performance_chart,
    create_conversions_by_segment_chart, create_segment_box_plot
)
from components.layout import create_data_table
import logging

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=".env")
API_BASE_URL = os.getenv("API_BASE_URL")

# ============================================================================
# HELPER FUNCTIONS FOR DYNAMIC COLUMN DETECTION
# ============================================================================

def is_likely_url(text):
    """Check if text looks like a URL"""
    if not isinstance(text, str):
        return False
    text_lower = text.lower()
    return any(protocol in text_lower for protocol in ['http://', 'https://', 'www.']) or \
           any(domain in text_lower for domain in ['.com', '.org', '.net', '.io'])

def extract_domain_from_url(url_text):
    """Extract domain from URL text"""
    try:
        if '://' in url_text:
            domain = urlparse(url_text).netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        else:
            return url_text
    except:
        return url_text

def clean_gender_value(gender_str):
    """Clean and standardize gender values"""
    if not isinstance(gender_str, str):
        return str(gender_str)
    
    gender_upper = gender_str.upper().strip()
    
    gender_map = {
        'M': 'Male', 'MALE': 'Male',
        'F': 'Female', 'FEMALE': 'Female',
        'O': 'Other', 'OTHER': 'Other',
        'U': 'Unknown', 'UNKNOWN': 'Unknown',
        'NB': 'Non-Binary', 'NON-BINARY': 'Non-Binary',
        'TRANS': 'Transgender', 'TRANSGENDER': 'Transgender'
    }
    
    return gender_map.get(gender_upper, gender_str)

def get_dynamic_column_mapping(df):
    """Dynamically detect which columns correspond to which attributes"""
    column_mapping = {}
    
    attribute_patterns = {
        'gender': ['gender', 'GENDER', 'Gender', 'sex', 'SEX', 'Sex', 'customer_gender', 'user_gender', 'gender_code'],
        'age': ['age_range', 'AGE_RANGE', 'Age_Range', 'Age', 'age', 'AGE', 'age_group', 'AGE_GROUP', 'age_bracket', 'age_category', 'customer_age', 'user_age_range'],
        'income': ['income_range', 'INCOME_RANGE', 'Income_Range', 'Income', 'income', 'income_bracket', 'INCOME_BRACKET', 'salary_range', 'SALARY_RANGE', 'annual_income', 'household_income', 'income_level'],
        'networth': ['net_worth', 'NET_WORTH', 'New_Worth', 'NETWORTH', 'networth', 'wealth', 'WEALTH', 'assets', 'ASSETS', 'net_assets', 'financial_worth', 'wealth_bracket'],
        'credit': ['credit_rating', 'CREDIT_RATING', 'Credit_Rating', 'Credit', 'credit', 'credit_score', 'CREDIT_SCORE', 'fico_score', 'FICO_SCORE', 'credit_tier', 'credit_grade', 'credit_level'],
        'homeowner': ['homeowner', 'HOMEOWNER', 'Homeowner', 'home_owner', 'HOME_OWNER', 'owns_home', 'home_ownership', 'property_owner'],
        'married': ['married', 'MARRIED', 'Married', 'marital_status', 'MARITAL_STATUS', 'marital', 'MARITAL', 'relationship_status'],
        'children': ['children', 'CHILDREN', 'Children', 'has_children', 'HAS_CHILDREN', 'dependents', 'DEPENDENTS', 'kids', 'KIDS', 'number_of_children'],
        'state': ['personal_state', 'PERSONAL_STATE', 'State', 'STATE', 'state', 'location_state', 'customer_state', 'user_state', 'billing_state', 'shipping_state', 'province', 'PROVINCE', 'region', 'REGION']
    }
    
    for attribute, patterns in attribute_patterns.items():
        column_mapping[attribute] = find_column(df, patterns)
    
    return column_mapping

def apply_dynamic_filters(df, filters_dict, column_mapping):
    """âœ… FIXED: Apply filters using dynamic column mapping"""
    filtered_df = df.copy()
    
    logger.info(f"Applying filters to {len(filtered_df)} rows")
    logger.info(f"Active filters: {filters_dict}")
    
    # ===================================================================
    # STEP 1: Apply DATE filter
    # ===================================================================
    if filters_dict.get('start_date') and filters_dict.get('end_date'):
        date_col = find_column(filtered_df, ['date', 'timestamp', 'created_at', 'order_date', 'visit_date'])
        
        if date_col and date_col in filtered_df.columns:
            try:
                filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce')
                filtered_df = filtered_df.dropna(subset=[date_col])
                
                start = pd.to_datetime(filters_dict['start_date'])
                end = pd.to_datetime(filters_dict['end_date'])
                
                # Handle timezone awareness
                if hasattr(filtered_df[date_col].dtype, 'tz') and filtered_df[date_col].dtype.tz is not None:
                    start = start.tz_localize('UTC') if start.tzinfo is None else start.tz_convert('UTC')
                    end = end.tz_localize('UTC') if end.tzinfo is None else end.tz_convert('UTC')
                else:
                    start = start.tz_localize(None) if start.tzinfo is not None else start
                    end = end.tz_localize(None) if end.tzinfo is not None else end
                
                filtered_df = filtered_df[(filtered_df[date_col] >= start) & (filtered_df[date_col] <= end)]
                logger.info(f"   ✅ Date filter: {len(filtered_df)} rows remaining")
            except Exception as e:
                logger.error(f"   ❌ Date filter failed: {e}")
    
    # ===================================================================
    # STEP 2: Apply CHANNEL/SOURCE filter
    # ===================================================================
    if filters_dict.get('channels'):
        channel_col = find_column(filtered_df, [
            'source', 'utm_source', 'traffic_source', 'referrer',
            'channel', 'medium', 'utm_medium', 'acquisition_channel'
        ])
        
        if channel_col and channel_col in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[channel_col].isin(filters_dict['channels'])]
            logger.info(f"   ✅ Channel filter ({channel_col}): {len(filtered_df)} rows remaining")
    
    # ===================================================================
    # STEP 3: Apply CAMPAIGN filter
    # ===================================================================
    if filters_dict.get('campaigns'):
        campaign_col = find_column(filtered_df, [
            'campaign', 'utm_campaign', 'campaign_name', 'eventtype'
        ])
        
        if campaign_col and campaign_col in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[campaign_col].isin(filters_dict['campaigns'])]
            logger.info(f"   ✅ Campaign filter ({campaign_col}): {len(filtered_df)} rows remaining")
    
    # ===================================================================
    # STEP 4: Apply DEMOGRAPHIC filters
    # ===================================================================
    demographic_filters = {
        'gender': filters_dict.get('gender'),
        'age': filters_dict.get('age'),
        'income': filters_dict.get('income'),
        'networth': filters_dict.get('networth'),
        'credit': filters_dict.get('credit'),
        'homeowner': filters_dict.get('homeowner'),
        'married': filters_dict.get('married'),
        'children': filters_dict.get('children'),
        'state': filters_dict.get('state')
    }
    
    for attr_name, filter_values in demographic_filters.items():
        if filter_values and len(filter_values) > 0:
            col_name = column_mapping.get(attr_name)
            
            if col_name and col_name in filtered_df.columns:
                # Clean and match values (case-insensitive)
                filtered_df_clean = filtered_df[col_name].astype(str).str.strip().str.upper()
                filter_values_clean = [str(v).strip().upper() for v in filter_values]
                
                filtered_df = filtered_df[filtered_df_clean.isin(filter_values_clean)]
                logger.info(f"   ✅ {attr_name.title()} filter ({col_name}): {len(filtered_df)} rows remaining")
    
    logger.info(f"Final filtered data: {len(filtered_df)} rows")
    return filtered_df

# ============================================================================
# ✅ NEW HELPER FUNCTION: Check if data has revenue columns
# ============================================================================

def has_revenue_data(df: pd.DataFrame) -> bool:
    """Check if dataframe has any revenue-related columns"""
    if df.empty:
        return False
    
    revenue_patterns = [
        'revenue', 'amount', 'total', 'price', 'order_value',
        'purchase_amount', 'transaction_amount', 'sale_amount',
        'order_total', 'cart_value'
    ]
    
    for col in df.columns:
        col_lower = col.lower()
        if any(pattern in col_lower for pattern in revenue_patterns):
            # Check if column has actual numeric data
            try:
                test_vals = pd.to_numeric(df[col], errors='coerce')
                if (test_vals > 0).sum() > len(df) * 0.1:
                    logger.info(f"✅ Found revenue column: {col}")
                    return True
            except:
                continue
    
    logger.info("❌ No revenue columns found in data")
    return False

# ============================================================================
# MAIN CALLBACK REGISTRATION
# ============================================================================

def register_dashboard_callbacks(app):
    """Register all dashboard-related callbacks with dynamic attribute filters"""
    
    # ========================================================================
    # CALLBACK 1: UPDATE KPIs - ✅ COMPLETELY REWRITTEN
    # ========================================================================
    @app.callback(
        [Output('kpi-revenue', 'children'),
         Output('kpi-conversion', 'children'),
         Output('kpi-aov', 'children'),
         Output('kpi-repeat-rate', 'children'),
         Output('kpi-ltv', 'children'),
         Output('kpi-gross', 'children'),
         Output('kpi-cac', 'children')],
        [Input('apply-filters', 'n_clicks'),
         Input('buyers-data', 'data'),
         Input('visitors-data', 'data'),
         Input('file-type-dropdown', 'value')], 
        [State('date-range-picker', 'start_date'),
         State('date-range-picker', 'end_date'),
         State('channel-filter', 'value'),
         State('campaign-filter', 'value'),
         State('gender-filter', 'value'),
         State('age-filter', 'value'),
         State('income-filter', 'value'),
         State('networth-filter', 'value'),
         State('credit-filter', 'value'),
         State('homeowner-filter', 'value'),
         State('married-filter', 'value'),
         State('children-filter', 'value'),
         State('state-filter', 'value')]
    )
    def update_kpis(n_clicks, buyers_data, visitors_data, file_type,
                    start_date, end_date, channels, campaigns, gender, age, 
                    income, networth, credit, homeowner, married, children, state):
        """✅ COMPLETE FIX: Calculate correct KPIs based on data type and available columns"""
        
        # Return empty if no data at all
        if not buyers_data and not visitors_data:
            return "", "", "", "", "", "", ""
        
        # ✅ Determine which data to use based on file_type
        if file_type == 'buyers':
            if not buyers_data:
                return "", "", "", "", "", "", ""
            primary_df = pd.DataFrame(buyers_data)
            data_type = "buyers"
        elif file_type == 'visitors':
            if not visitors_data:
                return "", "", "", "", "", "", ""
            primary_df = pd.DataFrame(visitors_data)
            data_type = "visitors"
        else:
            # Fallback
            if buyers_data:
                primary_df = pd.DataFrame(buyers_data)
                data_type = "buyers"
            elif visitors_data:
                primary_df = pd.DataFrame(visitors_data)
                data_type = "visitors"
            else:
                return "", "", "", "", "", "", ""
        
        visitors_df = pd.DataFrame(visitors_data) if visitors_data else pd.DataFrame()
        
        # Apply filters
        if not primary_df.empty:
            column_mapping = get_dynamic_column_mapping(primary_df)
            filters_dict = {
                'start_date': start_date,
                'end_date': end_date,
                'channels': channels,
                'campaigns': campaigns,
                'gender': gender,
                'age': age,
                'income': income,
                'networth': networth,
                'credit': credit,
                'homeowner': homeowner,
                'married': married,
                'children': children,
                'state': state
            }
            primary_df = apply_dynamic_filters(primary_df, filters_dict, column_mapping)
        
        logger.info(f"📊 Calculating KPIs for {data_type}: {len(primary_df)} rows")
        
        # ===================================================================
        # ✅ BUYERS KPIs - Check if revenue data exists
        # ===================================================================
        if data_type == "buyers":
            # Check if this buyers data has revenue columns
            if has_revenue_data(primary_df):
                # REVENUE-BASED KPIs (Traditional E-commerce)
                logger.info("💰 Using REVENUE-BASED KPIs for buyers")
                
                total_revenue = calculate_total_revenue(primary_df)
                conversion_rate = calculate_conversion_rate(primary_df, visitors_df)
                aov = calculate_aov(primary_df)
                repeat_rate = calculate_repeat_rate(primary_df)
                ltv = calculate_ltv_90day(primary_df)
                revenue_data = calculate_gross_vs_refunded(primary_df)
                gross = revenue_data.get("gross", 0)
                refunded = revenue_data.get("refunded", 0)
                cac = calculate_cac(primary_df, visitors_df)
                
                logger.info(f"📊 Buyers KPIs - Revenue: ${total_revenue:,.2f}, CAC: ${cac:,.2f}")
                
                return (
                    create_kpi_card("Total Revenue", f"${total_revenue:,.2f}", "All time", "success"),
                    create_kpi_card("Conversion Rate", f"{conversion_rate:.2f}%", "Visitors to buyers", "info"),
                    create_kpi_card("AOV", f"${aov:,.2f}", "Average order value", "primary"),
                    create_kpi_card("Repeat Rate", f"{repeat_rate:.2f}%", "Returning customers", "warning"),
                    create_kpi_card("LTV (90d)", f"${ltv:,.2f}", "Lifetime value", "danger"),
                    create_kpi_card("Gross/Refunded", f"${gross:,.2f} / ${refunded:,.2f}", "Revenue breakdown", "secondary"),
                    create_kpi_card("CAC", f"${cac:,.2f}", "Cost per acquisition", "dark")
                )
            else:
                # ✅ DEMOGRAPHIC-BASED KPIs (No Revenue Data)
                logger.info("👥 Using DEMOGRAPHIC-BASED KPIs for buyers (no revenue data)")
                
                buyer_kpis = calculate_buyer_kpis(primary_df)
                
                return (
                    # KPI 1: Total Buyers
                    create_kpi_card(
                        "Total Buyers", 
                        f"{buyer_kpis['total_buyers']:,}", 
                        "All tracked buyers", 
                        "success"
                    ),
                    
                    # KPI 2: Unique Buyers
                    create_kpi_card(
                        "Unique Buyers", 
                        f"{buyer_kpis['unique_buyers']:,}", 
                        f"{(buyer_kpis['unique_buyers']/buyer_kpis['total_buyers']*100):.1f}% unique" if buyer_kpis['total_buyers'] > 0 else "N/A",
                        "info"
                    ),
                    
                    # KPI 3: Gender Split
                    create_kpi_card(
                        "Gender Split", 
                        f"♂ {buyer_kpis['male_percent']:.0f}% / ♀ {buyer_kpis['female_percent']:.0f}%",
                        "Male / Female distribution",
                        "primary"
                    ),
                    
                    # KPI 4: Repeat Buyers
                    create_kpi_card(
                        "Repeat Buyers", 
                        f"{buyer_kpis['repeat_buyers']:,}",
                        f"{buyer_kpis['repeat_rate']:.1f}% repeat rate",
                        "warning"
                    ),
                    
                    # KPI 5: Top State
                    create_kpi_card(
                        "Top State", 
                        str(buyer_kpis['top_state']),
                        "Most common location",
                        "danger"
                    ),
                    
                    # KPI 6: Top Income Range
                    create_kpi_card(
                        "Top Income", 
                        str(buyer_kpis['top_income']),
                        "Most common income bracket",
                        "secondary"
                    ),
                    
                    # KPI 7: Most Common Age
                    create_kpi_card(
                        "Common Age", 
                        str(buyer_kpis['avg_age']),
                        "Most frequent age range",
                        "dark"
                    )
                )
        
        # ===================================================================
        # ✅ VISITORS KPIs - Always demographic-based
        # ===================================================================
        else:  # visitors
            logger.info("👥 Using DEMOGRAPHIC-BASED KPIs for visitors")
            
            total_visitors = len(primary_df)
            
            # 1. Unique Visitors
            email_col = find_column(primary_df, ['email', 'user_id', 'visitor_id', 'uuid'])
            unique_visitors = primary_df[email_col].nunique() if email_col else total_visitors
            
            # 2. Gender breakdown
            gender_col = find_column(primary_df, ['gender', 'sex'])
            male_count = 0
            female_count = 0
            if gender_col:
                try:
                    male_count = len(primary_df[primary_df[gender_col].astype(str).str.upper().isin(['M', 'MALE'])])
                    female_count = len(primary_df[primary_df[gender_col].astype(str).str.upper().isin(['F', 'FEMALE'])])
                except:
                    pass
            
            male_percent = (male_count / total_visitors * 100) if total_visitors > 0 else 0
            female_percent = (female_count / total_visitors * 100) if total_visitors > 0 else 0
            
            # 3. Repeat Visitor Rate
            repeat_visitor_rate = calculate_repeat_rate(primary_df)
            
            # 4. Top State
            state_col = find_column(primary_df, ['state', 'personal_state', 'region'])
            top_state = primary_df[state_col].mode()[0] if state_col and len(primary_df[state_col].mode()) > 0 else 'N/A'
            
            # 5. Top Income Range
            income_col = find_column(primary_df, ['income', 'income_range'])
            top_income = primary_df[income_col].mode()[0] if income_col and len(primary_df[income_col].mode()) > 0 else 'N/A'
            
            # 6. Top Age Range
            age_col = find_column(primary_df, ['age', 'age_range', 'age_group'])
            top_age = primary_df[age_col].mode()[0] if age_col and len(primary_df[age_col].mode()) > 0 else 'N/A'
            
            logger.info(f"📊 Visitor KPIs - Total: {total_visitors}, Unique: {unique_visitors}, Repeat: {repeat_visitor_rate:.1f}%")
            
            return (
                create_kpi_card("Total Visitors", f"{total_visitors:,}", "All tracked visits", "info"),
                create_kpi_card("Unique Visitors", f"{unique_visitors:,}", f"{(unique_visitors/total_visitors*100):.1f}% unique", "primary"),
                create_kpi_card("Gender Split", f"♂ {male_percent:.0f}% / ♀ {female_percent:.0f}%", "Male / Female", "success"),
                create_kpi_card("Repeat Visitors", f"{repeat_visitor_rate:.2f}%", "Returning visitors", "warning"),
                create_kpi_card("Top State", str(top_state), "Most common location", "danger"),
                create_kpi_card("Top Income", str(top_income), "Most common income", "secondary"),
                create_kpi_card("Common Age", str(top_age), "Most frequent age range", "dark")
            )
    
    # ========================================================================
    # CALLBACK 2: UPDATE CHARTS
    # ========================================================================
    @app.callback(
        [Output('conversions-chart', 'figure'),
        Output('channel-performance-chart', 'figure')],
        [Input('apply-filters', 'n_clicks'),
        Input('buyers-data', 'data'),
        Input('visitors-data', 'data'),
        Input('file-type-dropdown', 'value')],
        [State('date-range-picker', 'start_date'),
        State('date-range-picker', 'end_date'),
        State('channel-filter', 'value'),
        State('campaign-filter', 'value'),
        State('gender-filter', 'value'),
        State('age-filter', 'value'),
        State('income-filter', 'value'),
        State('networth-filter', 'value'),
        State('credit-filter', 'value'),
        State('homeowner-filter', 'value'),
        State('married-filter', 'value'),
        State('children-filter', 'value'),
        State('state-filter', 'value')]
    )
    def update_charts(n_clicks, buyers_data, visitors_data, file_type,
                start_date, end_date, channels, campaigns, gender, age, 
                income, networth, credit, homeowner, married, children, state):
        """✅ FIXED: Generate charts with PROPER filter application"""
        
        # ================================================================
        # STEP 1: Handle empty data
        # ================================================================
        if not buyers_data and not visitors_data:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                xaxis={"visible": False},
                yaxis={"visible": False},
                annotations=[{
                    "text": "Upload data to see charts",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20}
                }]
            )
            return empty_fig, empty_fig
        
        # ================================================================
        # STEP 2: Select correct data based on file type
        # ================================================================
        if file_type == 'buyers':
            if not buyers_data:
                empty_fig = go.Figure()
                empty_fig.update_layout(annotations=[{"text": "No buyers data", "showarrow": False}])
                return empty_fig, empty_fig
            primary_df = pd.DataFrame(buyers_data)
            data_type = "buyers"
            chart1_title = "Conversions Over Time"
            chart2_title = "Top 15 Channels Performance"
        elif file_type == 'visitors':
            if not visitors_data:
                empty_fig = go.Figure()
                empty_fig.update_layout(annotations=[{"text": "No visitors data", "showarrow": False}])
                return empty_fig, empty_fig
            primary_df = pd.DataFrame(visitors_data)
            data_type = "visitors"
            chart1_title = "Visitor Traffic Over Time"
            chart2_title = "Visitors by Channel"
        else:
            # Fallback
            if buyers_data:
                primary_df = pd.DataFrame(buyers_data)
                data_type = "buyers"
                chart1_title = "Conversions Over Time"
                chart2_title = "Top 15 Channels Performance"
            elif visitors_data:
                primary_df = pd.DataFrame(visitors_data)
                data_type = "visitors"
                chart1_title = "Visitor Traffic Over Time"
                chart2_title = "Visitors by Channel"
            else:
                empty_fig = go.Figure()
                return empty_fig, empty_fig
        
        visitors_df = pd.DataFrame(visitors_data) if visitors_data else pd.DataFrame()
        
        logger.info(f"📊 Generating charts for {data_type}: {len(primary_df)} rows BEFORE filters")
        
        # ✅ Store original count BEFORE filtering
        total_rows = len(primary_df)
        
        # ================================================================
        # ✅ STEP 3: APPLY ALL FILTERS - THIS IS THE KEY FIX!
        # ================================================================
        if not primary_df.empty:
            column_mapping = get_dynamic_column_mapping(primary_df)
            
            # Build filters dictionary
            filters_dict = {
                'start_date': start_date,
                'end_date': end_date,
                'channels': channels,
                'campaigns': campaigns,
                'gender': gender,
                'age': age,
                'income': income,
                'networth': networth,
                'credit': credit,
                'homeowner': homeowner,
                'married': married,
                'children': children,
                'state': state
            }
            
            # ✅ Apply filters to get FILTERED dataframe
            primary_df = apply_dynamic_filters(primary_df, filters_dict, column_mapping)
            
            logger.info(f"📊 After filters: {len(primary_df)} rows")
            logger.info(f"   Active filters: Channels={bool(channels)}, Campaigns={bool(campaigns)}, Gender={bool(gender)}, Age={bool(age)}, Income={bool(income)}")
        
        # ================================================================
        # ✅ STEP 4: BUILD FILTER LIST FIRST (BEFORE CREATING CHARTS)
        # ================================================================
        active_filters = []
        
        if channels:
            active_filters.append(f"Source: {', '.join(channels[:2])}" + (f" +{len(channels)-2} more" if len(channels) > 2 else ""))
        if campaigns:
            active_filters.append(f"Campaign: {', '.join(campaigns[:2])}" + (f" +{len(campaigns)-2} more" if len(campaigns) > 2 else ""))
        if gender:
            active_filters.append(f"Gender: {', '.join(gender)}")
        if age:
            active_filters.append(f"Age: {', '.join(age[:2])}" + (f" +{len(age)-2} more" if len(age) > 2 else ""))
        if income:
            active_filters.append(f"Income: {', '.join(income[:1])}" + (f" +{len(income)-1} more" if len(income) > 1 else ""))
        if networth:
            active_filters.append(f"Net Worth: {networth[0]}" + (f" +{len(networth)-1} more" if len(networth) > 1 else ""))
        if credit:
            active_filters.append(f"Credit: {credit[0]}" + (f" +{len(credit)-1} more" if len(credit) > 1 else ""))
        if homeowner:
            active_filters.append(f"Homeowner: {', '.join(homeowner)}")
        if married:
            active_filters.append(f"Married: {', '.join(married)}")
        if children:
            active_filters.append(f"Children: {', '.join(children)}")
        if state:
            active_filters.append(f"State: {', '.join(state[:3])}" + (f" +{len(state)-3} more" if len(state) > 3 else ""))
        if start_date and end_date:
            active_filters.append(f"Date: {start_date} to {end_date}")
        
        # Calculate filter count
        filter_count = len(active_filters)
        
        # ================================================================
        # STEP 5: Generate charts using FILTERED data
        # ================================================================
        
        # Chart 1: Conversions Over Time
        conversions_df = get_conversions_over_time(primary_df) if not primary_df.empty else pd.DataFrame()
        chart1 = create_conversions_chart(conversions_df)
        
        # Chart 2: Channel Performance (TOP 15) - Using FILTERED data
        channel_df = get_channel_performance(primary_df) if not primary_df.empty else pd.DataFrame()
        
        if not channel_df.empty:
            logger.info(f"📊 Channel Performance Chart:")
            logger.info(f"   Total channels found: {len(channel_df)}")
            logger.info(f"   Top 3 channels: {channel_df.head(3)['channel'].tolist() if 'channel' in channel_df.columns else 'N/A'}")
        
        chart2 = create_channel_performance_chart(channel_df)
        
        # ================================================================
        # STEP 6: Add filter information to charts
        # ================================================================
        if filter_count > 0:
            # Add custom hover template with filter info
            hover_template = (
                "<b>%{y}</b><br>"
                "Revenue: $%{x:,.0f}<br>"
                f"<i>Filtered by:</i><br>"
            )
            
            # Add each active filter to hover
            if channels:
                hover_template += f"  • Source: {', '.join(channels[:2])}<br>"
            if gender:
                hover_template += f"  • Gender: {', '.join(gender)}<br>"
            if income:
                hover_template += f"  • Income: {income[0]}<br>"
            if state:
                hover_template += f"  • State: {', '.join(state[:2])}<br>"
            
            hover_template += "<extra></extra>"
            
            # Update chart2 hover
            chart2.update_traces(hovertemplate=hover_template)
            
            # Create filter summary text
            filter_summary = " | ".join(active_filters[:3])  # Show first 3 filters
            if len(active_filters) > 3:
                filter_summary += f" +{len(active_filters)-3} more"
            
            filter_text = f"<br><sub><b>🔍 Filters Applied:</b> {filter_summary}<br>Showing {len(primary_df):,} of {total_rows:,} records ({(len(primary_df)/total_rows*100):.1f}%)</sub>"
            
            # Update both chart titles
            chart1.update_layout(
                title=chart1_title + filter_text,
                height=500
            )
            chart2.update_layout(
                title=chart2_title + filter_text,
                height=500
            )
        else:
            # No filters - show total
            chart1.update_layout(
                title=chart1_title + f"<br><sub>All {len(primary_df):,} records</sub>",
                height=500
            )
            chart2.update_layout(
                title=chart2_title + f"<br><sub>All {len(primary_df):,} records</sub>",
                height=500
            )
        
        return chart1, chart2
    
    # ========================================================================
    # CALLBACK 3: UPDATE FILTER OPTIONS
    # ========================================================================
    @app.callback(
        [Output('channel-filter', 'options'),
         Output('campaign-filter', 'options'),
         Output('gender-filter', 'options'),
         Output('age-filter', 'options'),
         Output('income-filter', 'options'),
         Output('networth-filter', 'options'),
         Output('credit-filter', 'options'),
         Output('homeowner-filter', 'options'),
         Output('married-filter', 'options'),
         Output('children-filter', 'options'),
         Output('state-filter', 'options')],
        [Input('buyers-data', 'data'),
         Input('visitors-data', 'data'),
         Input('file-type-dropdown', 'value')]
    )
    def update_filter_options(buyers_data, visitors_data, file_type):
        """✅ FIXED: Update filter options based on selected data type"""
        
        # Select data based on file_type
        if file_type == 'buyers':
            if not buyers_data:
                return [[] for _ in range(11)]
            df = pd.DataFrame(buyers_data)
        elif file_type == 'visitors':
            if not visitors_data:
                return [[] for _ in range(11)]
            df = pd.DataFrame(visitors_data)
        else:
            # Fallback
            if buyers_data:
                df = pd.DataFrame(buyers_data)
            elif visitors_data:
                df = pd.DataFrame(visitors_data)
            else:
                return [[] for _ in range(11)]
        
        if df.empty:
            return [[] for _ in range(11)]

        logger.info(f"📋 Updating filter options for {file_type}: {list(df.columns)}")

        def get_unique_options(col):
            """FIXED: Get unique values from a column, cleaned and sorted"""
            if not col or col not in df.columns:
                logger.warning(f"  Column '{col}' not found in data")
                return []
            
            try:
                # Get all non-null values
                vals = df[col].dropna().astype(str).str.strip()
                
                # Remove empty/invalid values
                vals = vals[~vals.str.lower().isin(['nan', 'none', 'null', '', 'n/a', 'unknown'])]
                
                # Remove URLs
                vals = vals[~vals.str.contains('http|www|\.com/', case=False, regex=True, na=False)]
                
                # Get unique values
                unique = vals.unique().tolist()
                
                # Sort intelligently
                try:
                    # Try numeric sorting for numbers
                    unique_sorted = sorted(unique, key=lambda x: (isinstance(x, str), x))
                except:
                    # Fallback to string sorting
                    unique_sorted = sorted(unique, key=str)
                
                # Limit to top 100 for performance
                if len(unique_sorted) > 100:
                    logger.warning(f"  Column '{col}' has {len(unique_sorted)} values, showing top 100")
                    unique_sorted = unique_sorted[:100]
                
                logger.debug(f"  Column '{col}': {len(unique_sorted)} unique options")
                
                return [{'label': v, 'value': v} for v in unique_sorted if v]
            
            except Exception as e:
                logger.error(f"  Error getting options for '{col}': {e}")
                return []

        # Detect channel/source column
        channel_col = None
        channel_patterns = [
            'source', 'utm_source', 'traffic_source', 'referrer', 
            'channel', 'medium', 'utm_medium', 'acquisition_channel',
            'marketing_channel', 'ad_source', 'campaign_source'
        ]
        
        for pattern in channel_patterns:
            matches = [c for c in df.columns if pattern.lower() == c.lower()]
            if matches:
                channel_col = matches[0]
                logger.info(f"✅ Channel column (exact match): {channel_col}")
                break
        
        if not channel_col:
            for pattern in channel_patterns:
                matches = [c for c in df.columns if pattern.lower() in c.lower()]
                if matches:
                    for match in matches:
                        sample = df[match].dropna().astype(str).head(10)
                        if sample.str.contains('http|www|\.com/', case=False, regex=True).sum() < 5:
                            channel_col = match
                            logger.info(f"✅ Channel column (partial match): {channel_col}")
                            break
                    if channel_col:
                        break
        
        if not channel_col:
            for col in df.columns:
                if df[col].dtype == 'object':
                    nunique = df[col].nunique()
                    if 2 < nunique < 50:
                        sample = df[col].dropna().astype(str).head(10)
                        if sample.str.contains('http|www|\.com/', case=False, regex=True).sum() < 5:
                            channel_col = col
                            logger.info(f"⚠️ Channel column (fallback): {channel_col}")
                            break

        # Detect campaign column
        campaign_col = None
        campaign_patterns = [
            'campaign', 'utm_campaign', 'campaign_name', 'adset', 
            'ad_campaign', 'marketing_campaign', 'promo', 'promotion',
            'campaign_id', 'eventtype'
        ]
        
        for pattern in campaign_patterns:
            matches = [c for c in df.columns if pattern.lower() == c.lower()]
            if matches:
                campaign_col = matches[0]
                logger.info(f"✅ Campaign column (exact match): {campaign_col}")
                break
        
        if not campaign_col:
            for pattern in campaign_patterns:
                matches = [c for c in df.columns if pattern.lower() in c.lower()]
                if matches:
                    campaign_col = matches[0]
                    logger.info(f"✅ Campaign column (partial match): {campaign_col}")
                    break
        
        if not campaign_col:
            for col in df.columns:
                if col == channel_col:
                    continue
                if df[col].dtype == 'object':
                    nunique = df[col].nunique()
                    if 2 < nunique < 100:
                        campaign_col = col
                        logger.info(f"⚠️ Campaign column (fallback): {campaign_col}")
                        break

        # Get demographic columns
        mapping = get_dynamic_column_mapping(df)

        # Build options
        channel_opts = get_unique_options(channel_col) if channel_col else []
        campaign_opts = get_unique_options(campaign_col) if campaign_col else []
        
        logger.info(f"📊 Filter Options Generated:")
        logger.info(f"  Channel ({channel_col}): {len(channel_opts)} options")
        logger.info(f"  Campaign ({campaign_col}): {len(campaign_opts)} options")
        
        return [
            channel_opts,
            campaign_opts,
            get_unique_options(mapping.get('gender')),
            get_unique_options(mapping.get('age')),
            get_unique_options(mapping.get('income')),
            get_unique_options(mapping.get('networth')),
            get_unique_options(mapping.get('credit')),
            get_unique_options(mapping.get('homeowner')),
            get_unique_options(mapping.get('married')),
            get_unique_options(mapping.get('children')),
            get_unique_options(mapping.get('state'))
        ]
    
    # ========================================================================
    # CALLBACK 4: SHOW/HIDE FILTERS
    # ========================================================================
    @app.callback(
        [Output('gender-filter-container', 'style'),
         Output('age-filter-container', 'style'),
         Output('income-filter-container', 'style'),
         Output('networth-filter-container', 'style'),
         Output('credit-filter-container', 'style'),
         Output('homeowner-filter-container', 'style'),
         Output('married-filter-container', 'style'),
         Output('children-filter-container', 'style'),
         Output('state-filter-container', 'style')],
        [Input('buyers-data', 'data'),
         Input('visitors-data', 'data'),
         Input('file-type-dropdown', 'value')]
    )
    def show_hide_filters(buyers_data, visitors_data, file_type):
        """✅ FIXED: Show filters based on selected data type"""
        
        hidden_style = {'display': 'none'}
        visible_style = {'display': 'block'}
        
        # Select data based on file_type
        if file_type == 'buyers':
            if not buyers_data:
                return [hidden_style] * 9
            df = pd.DataFrame(buyers_data)
        elif file_type == 'visitors':
            if not visitors_data:
                return [hidden_style] * 9
            df = pd.DataFrame(visitors_data)
        else:
            if buyers_data:
                df = pd.DataFrame(buyers_data)
            elif visitors_data:
                df = pd.DataFrame(visitors_data)
            else:
                return [hidden_style] * 9
        
        if df.empty:
            return [hidden_style] * 9
        
        # Check which columns exist
        column_mapping = get_dynamic_column_mapping(df)
        
        has_gender = bool(column_mapping.get('gender'))
        has_age = bool(column_mapping.get('age'))
        has_income = bool(column_mapping.get('income'))
        has_networth = bool(column_mapping.get('networth'))
        has_credit = bool(column_mapping.get('credit'))
        has_homeowner = bool(column_mapping.get('homeowner'))
        has_married = bool(column_mapping.get('married'))
        has_children = bool(column_mapping.get('children'))
        has_state = bool(column_mapping.get('state'))
        
        logger.info(f"👁️ Filter visibility for {file_type} - Gender: {has_gender}, Age: {has_age}, Income: {has_income}")
        
        return [
            visible_style if has_gender else hidden_style,
            visible_style if has_age else hidden_style,
            visible_style if has_income else hidden_style,
            visible_style if has_networth else hidden_style,
            visible_style if has_credit else hidden_style,
            visible_style if has_homeowner else hidden_style,
            visible_style if has_married else hidden_style,
            visible_style if has_children else hidden_style,
            visible_style if has_state else hidden_style
        ]
    
    # ========================================================================
    # CALLBACK 5: SET DEFAULT DATE RANGE
    # ========================================================================
    @app.callback(
        [Output('date-range-picker', 'start_date'),
         Output('date-range-picker', 'end_date')],
        [Input('buyers-data', 'data'),
         Input('visitors-data', 'data'),
         Input('file-type-dropdown', 'value')]
    )
    def set_default_date_range(buyers_data, visitors_data, file_type):
        """Set default date range based on data"""
        
        # Select appropriate data based on file_type
        if file_type == 'buyers' and buyers_data:
            df = pd.DataFrame(buyers_data)
        elif file_type == 'visitors' and visitors_data:
            df = pd.DataFrame(visitors_data)
        elif buyers_data:
            df = pd.DataFrame(buyers_data)
        elif visitors_data:
            df = pd.DataFrame(visitors_data)
        else:
            df = pd.DataFrame()
        
        if not df.empty:
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
                try:
                    min_date = df[date_col].min()
                    max_date = df[date_col].max()
                    logger.info(f"📅 Date range set: {min_date.date()} to {max_date.date()}")
                    return min_date.date(), max_date.date()
                except Exception as e:
                    logger.error(f"Error setting date range: {e}")
        
        # Fallback: last 30 days
        end_date = datetime.now().date()
        start_date = (datetime.now() - timedelta(days=30)).date()
        logger.info(f"📅 Using fallback date range: {start_date} to {end_date}")
        return start_date, end_date
    
    # ========================================================================
    # CALLBACK 6: SAVE USER FILTERS
    # ========================================================================
    @app.callback(
        Output('user-filters', 'data'),
        [Input('save-filters', 'n_clicks')],
        [State('date-range-picker', 'start_date'),
         State('date-range-picker', 'end_date'),
         State('channel-filter', 'value'),
         State('campaign-filter', 'value'),
         State('gender-filter', 'value'),
         State('age-filter', 'value'),
         State('income-filter', 'value'),
         State('networth-filter', 'value'),
         State('credit-filter', 'value'),
         State('homeowner-filter', 'value'),
         State('married-filter', 'value'),
         State('children-filter', 'value'),
         State('state-filter', 'value'),
         State('auth-token', 'data'),
         State('current-workspace', 'data')]
    )
    def save_user_filters(n_clicks, start_date, end_date, channels, campaigns, 
                         gender, age, income, networth, credit, homeowner, 
                         married, children, state, token, workspace_id):
        """Save user's filter preferences"""
        
        if not n_clicks or not token:
            return no_update
        
        filters = {
            'start_date': start_date,
            'end_date': end_date,
            'channels': channels,
            'campaigns': campaigns,
            'gender': gender,
            'age': age,
            'income': income,
            'networth': networth,
            'credit': credit,
            'homeowner': homeowner,
            'married': married,
            'children': children,
            'state': state
        }
        
        try:
            workspace_id = workspace_id or 1
            response = requests.post(
                f"{API_BASE_URL}/workspaces/{workspace_id}/filters?token={token}",
                json=filters,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Filters saved successfully for workspace {workspace_id}")
                return filters
            else:
                logger.warning(f"Failed to save filters: {response.status_code}")
        except Exception as e:
            logger.error(f"Error saving filters: {e}")
        
        return no_update