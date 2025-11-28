import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.metrics import find_column
import pandas as pd
import numpy as np
import re

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_column(df: pd.DataFrame, patterns: list) -> str:
    """Find a column matching any of the given patterns (case-insensitive)"""
    for pattern in patterns:
        # Try exact match first
        for col in df.columns:
            if pattern.lower() == col.lower():
                return col
        # Try partial match
        for col in df.columns:
            if pattern.lower() in col.lower():
                return col
    return None

def find_any_numeric_column(df: pd.DataFrame, exclude_cols: list = None) -> str:
    """Find any numeric column, excluding specified columns"""
    exclude_cols = exclude_cols or []
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        if col not in exclude_cols:
            return col
    return None

def parse_range_or_number(value):
    """Parse revenue ranges like '$100K-$500K' or single values like '$250K'"""
    if pd.isna(value):
        return 0
    
    value_str = str(value).strip()
    
    # Remove currency symbols and commas
    value_str = value_str.replace('$', '').replace(',', '').strip()
    
    # Handle ranges (e.g., "100K-500K" or "1M-5M")
    if '-' in value_str:
        parts = value_str.split('-')
        if len(parts) == 2:
            try:
                low = parse_single_value(parts[0].strip())
                high = parse_single_value(parts[1].strip())
                return (low + high) / 2  # Return average
            except:
                pass
    
    # Handle single values
    try:
        return parse_single_value(value_str)
    except:
        return 0

def parse_single_value(value_str: str) -> float:
    """Parse a single value like '100K', '5M', '1.5B', or '1000'"""
    value_str = value_str.strip().upper()
    
    # Handle K, M, B suffixes
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
    
    for suffix, multiplier in multipliers.items():
        if value_str.endswith(suffix):
            num_str = value_str[:-1].strip()
            return float(num_str) * multiplier
    
    # Plain number
    return float(value_str)

# ============================================================================
# DASH COMPONENTS
# ============================================================================

def create_kpi_card(title: str, value: str, subtitle: str = "", color: str = "primary"):
    """Create a KPI card component"""
    from dash import html
    import dash_bootstrap_components as dbc
    
    return dbc.Card([
        dbc.CardBody([
            html.H6(title, className="text-muted mb-2"),
            html.H3(value, className=f"text-{color} mb-1"),
            html.Small(subtitle, className="text-muted")
        ])
    ], className="shadow-sm")

# ============================================================================
# CHART CREATION FUNCTIONS
# ============================================================================

def create_empty_chart(message="Upload data to see insights"):
    """Create an empty placeholder chart"""
    empty_fig = go.Figure()
    empty_fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=20, color="gray")
    )
    empty_fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=400
    )
    return empty_fig

def create_conversions_chart(df: pd.DataFrame, freq: str = 'D'):
    """
    Create conversions over time chart (daily/weekly/monthly)
    Chart Type: LINE PLOT - Best for showing trends over time
    """
    if df.empty or len(df) == 0:
        return create_empty_chart("No conversion data available")
    
    print(f"\n📊 CREATING CONVERSIONS CHART")
    print(f"  Input rows: {len(df)}")
    print(f"  Columns: {df.columns.tolist()}")
    
    try:
        # Find date and conversion columns
        date_col = 'date' if 'date' in df.columns else df.columns[0]
        conv_col = 'conversions' if 'conversions' in df.columns else df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        print(f"  Using date column: {date_col}")
        print(f"  Using conversions column: {conv_col}")
        
        # Convert to datetime
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        
        if len(df) == 0:
            return create_empty_chart("No valid date data")
        
        # Sort by date
        df = df.sort_values(date_col)
        
        # Auto-detect frequency based on date range
        date_range = (df[date_col].max() - df[date_col].min()).days
        if date_range <= 7:
            freq = 'H'
            title = "Conversions Over Time (Hourly)"
        elif date_range <= 60:
            freq = 'D'
            title = "Conversions Over Time (Daily)"
        elif date_range <= 365:
            freq = 'W'
            title = "Conversions Over Time (Weekly)"
        else:
            freq = 'M'
            title = "Conversions Over Time (Monthly)"
        
        print(f"  Date range: {df[date_col].min()} to {df[date_col].max()}")
        print(f"  Auto-detected frequency: {freq}")
        print(f"  Total conversions: {df[conv_col].sum()}")
        
        # Create line chart with markers
        fig = px.line(
            df, 
            x=date_col,
            y=conv_col,
            title=title,
            labels={conv_col: 'Number of Conversions', date_col: 'Date'},
            markers=True
        )
        
        # Enhance styling
        fig.update_layout(
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=450,
            xaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                title='Date',
                tickangle=-45
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                title='Conversions',
                rangemode='tozero'
            ),
            font=dict(size=12),
            showlegend=False
        )
        
        # Style the line
        fig.update_traces(
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=6, color='#1f77b4', line=dict(width=1, color='white'))
        )
        
        # Add trend line
        if len(df) > 3:
            z = np.polyfit(range(len(df)), df[conv_col], 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=p(range(len(df))),
                mode='lines',
                name='Trend',
                line=dict(color='red', width=2, dash='dash'),
                showlegend=True
            ))
        
        return fig
    
    except Exception as e:
        print(f"❌ Error creating conversions chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Error: {str(e)[:50]}")

def create_conversions_by_segment_chart(df: pd.DataFrame, segment_col: str = 'segment'):
    """
    Create conversions over segments chart
    Chart Type: GROUPED BAR PLOT - Best for comparing conversions across segments
    """
    if df.empty or len(df) == 0:
        return create_empty_chart("No segment data available")
    
    try:
        # If segment column not provided, try to find one
        if segment_col not in df.columns:
            categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
            if categorical_cols:
                segment_col = categorical_cols[0]
            else:
                return create_empty_chart("No segment column found")
        
        # Aggregate conversions by segment
        segment_data = df.groupby(segment_col).size().reset_index(name='conversions')
        segment_data = segment_data.sort_values('conversions', ascending=False).head(15)
        
        # Create grouped bar chart
        fig = px.bar(
            segment_data,
            x=segment_col,
            y='conversions',
            title="Conversions by Segment",
            labels={'conversions': 'Number of Conversions', segment_col: 'Segment'},
            color='conversions',
            color_continuous_scale='Blues',
            text='conversions'
        )
        
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=450,
            xaxis=dict(
                showgrid=False,
                tickangle=-45,
                title=segment_col.replace('_', ' ').title()
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                title='Conversions',
                rangemode='tozero'
            ),
            showlegend=False
        )
        
        fig.update_traces(textposition='outside')
        
        return fig
    
    except Exception as e:
        print(f"❌ Error creating segment chart: {e}")
        return create_empty_chart(f"Error: {str(e)[:50]}")

# --------------------------------------------------------------
# 1. NEW vs RETURNING VISITORS (Visitors page)
# --------------------------------------------------------------
def create_new_vs_returning_chart(visitors_df: pd.DataFrame):
    """Pie chart: first-time vs returning visitors."""
    if visitors_df.empty:
        return create_empty_chart("No visitor data")

    # Find a column that uniquely identifies a visitor
    id_col = find_column(visitors_df, ['visitor_id', 'session_id', 'email', 'user_id', 'customer_id'])
    if not id_col:
        return create_empty_chart("No visitor ID column found")

    # Count how many times each ID appears
    visits = visitors_df[id_col].value_counts()
    new = (visits == 1).sum()
    returning = (visits > 1).sum()

    fig = go.Figure(
        data=[go.Pie(
            labels=['New Visitors', 'Returning Visitors'],
            values=[new, returning],
            hole=0.4,
            marker=dict(colors=['#36A2EB', '#FF6384']),
            textinfo='label+percent+value',
            texttemplate='%{label}<br>%{percent}<br>%{value:,}'
        )]
    )
    fig.update_layout(
        title="New vs Returning Visitors",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig


# --------------------------------------------------------------
# 2. ✅ FIXED: CONVERSION OVER TIME (Visitors → Buyers)
# --------------------------------------------------------------
def create_conversion_over_time_chart(visitors_df: pd.DataFrame, buyers_df: pd.DataFrame):
    """Line chart: daily visitor count vs buyer count - COMPLETELY FIXED"""
    
    # 🔍 DEBUG: Print column names
    print("=" * 60)
    print("DEBUG: Visitor DataFrame Columns:")
    print(visitors_df.columns.tolist())
    print("=" * 60)
    
    if visitors_df.empty:
        return create_empty_chart("No visitor data")

    # ✅ FIX: Find the date column dynamically
    date_col_v = find_column(visitors_df, ['date', 'visit_date', 'timestamp', 'created_at', 'visited_at', 'time'])
    
    if not date_col_v:
        return create_empty_chart("No date column found in visitors data")

    print(f"✅ Found visitor date column: {date_col_v}")

    # Find date column in buyers (if any)
    date_col_b = None
    if not buyers_df.empty:
        date_col_b = find_column(buyers_df, ['date', 'purchase_date', 'order_date', 'created_at', 'timestamp'])
        if date_col_b:
            print(f"✅ Found buyer date column: {date_col_b}")

    try:
        # ✅ STEP 1: Prepare daily visitor counts
        visitors = visitors_df.copy()
        visitors[date_col_v] = pd.to_datetime(visitors[date_col_v], errors='coerce')
        visitors = visitors.dropna(subset=[date_col_v])
        
        if len(visitors) == 0:
            return create_empty_chart("No valid date data in visitors")
        
        # Create a standardized 'date' column for grouping
        visitors['date'] = visitors[date_col_v].dt.date
        daily_visits = visitors.groupby('date').size().reset_index(name='visitors')
        daily_visits['date'] = pd.to_datetime(daily_visits['date'])
        
        print(f"✅ Processed {len(daily_visits)} days of visitor data")

        # ✅ STEP 2: Prepare daily buyer counts (if buyers exist)
        if not buyers_df.empty and date_col_b:
            buyers = buyers_df.copy()
            buyers[date_col_b] = pd.to_datetime(buyers[date_col_b], errors='coerce')
            buyers = buyers.dropna(subset=[date_col_b])
            buyers['date'] = buyers[date_col_b].dt.date
            daily_buyers = buyers.groupby('date').size().reset_index(name='buyers')
            daily_buyers['date'] = pd.to_datetime(daily_buyers['date'])
            
            # Merge visitors and buyers
            df = pd.merge(daily_visits, daily_buyers, on='date', how='outer')
            print(f"✅ Processed {len(daily_buyers)} days of buyer data")
        else:
            df = daily_visits.copy()
            df['buyers'] = 0
            print("⚠️ No buyer data available")

        df = df.fillna(0)
        df = df.sort_values('date')

        # ✅ STEP 3: Create the chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'], 
            y=df['visitors'],
            mode='lines+markers', 
            name='Visitors',
            line=dict(color='#36A2EB', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df['date'], 
            y=df['buyers'],
            mode='lines+markers', 
            name='Buyers',
            line=dict(color='#FF6384', width=2)
        ))

        fig.update_layout(
            title="Visitor → Buyer Conversion Over Time",
            xaxis_title="Date",
            yaxis_title="Count",
            height=420,
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        
        print("✅ Chart created successfully")
        return fig
    
    except Exception as e:
        print(f"❌ ERROR in create_conversion_over_time_chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Error: {str(e)[:50]}")


def create_new_vs_returning_area_chart(df: pd.DataFrame):
    """
    Create a stacked area chart for new vs returning customers over time
    Chart Type: STACKED AREA PLOT - Best for showing cumulative trends and relative contributions
    """
    if df.empty or len(df) == 0:
        return create_empty_chart("No customer data available")
    
    print(f"\n📊 CREATING NEW VS RETURNING AREA CHART")
    print(f"  Input rows: {len(df)}")
    print(f"  Columns: {df.columns.tolist()}")
    
    try:
        # Ensure datetime
        if 'date' in df.columns:
            df = df.copy()
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date'])
        
        if len(df) == 0:
            return create_empty_chart("No valid date data")
        
        # Sort by date
        df = df.sort_values('date')
        
        # Create figure
        fig = go.Figure()
        
        # Add area trace for new customers
        if 'new_customers' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['new_customers'],
                    name='New Customers',
                    mode='lines',
                    stackgroup='one',
                    line=dict(width=2, color='#2ecc71'),
                    fill='tonexty',
                    fillcolor='rgba(46, 204, 113, 0.7)'
                )
            )
        
        # Add area trace for returning customers
        if 'returning_customers' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['returning_customers'],
                    name='Returning Customers',
                    mode='lines',
                    stackgroup='one',
                    line=dict(width=2, color='#e74c3c'),
                    fill='tonexty',
                    fillcolor='rgba(231, 76, 60, 0.7)'
                )
            )
        
        # Fallback for total customers if specific columns are missing
        if 'new_customers' not in df.columns and 'returning_customers' not in df.columns and 'total_customers' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['total_customers'],
                    name='Total Customers',
                    mode='lines',
                    stackgroup='one',
                    line=dict(width=2, color='#3498db'),
                    fill='tozeroy',
                    fillcolor='rgba(52, 152, 219, 0.7)'
                )
            )
        
        # If no relevant columns, return empty chart
        if not fig.data:
            return create_empty_chart("No relevant customer data columns found")
        
        # Update layout
        fig.update_layout(
            title="New vs Returning Customers Over Time (Area Chart)",
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=450,
            xaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                title='Date',
                tickangle=-45
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                title='Number of Customers',
                rangemode='tozero'
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            showlegend=True
        )
        
        return fig
    
    except Exception as e:
        print(f"❌ Error creating new vs returning area chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Error: {str(e)[:50]}")

def create_channel_performance_chart(df: pd.DataFrame):
    """
    Create channel/campaign performance chart (Top N)
    Chart Type: HORIZONTAL BAR PLOT - Best for ranking performance
    Shows both channel AND campaign breakdowns
    """
    if df.empty or len(df) == 0:
        return create_empty_chart("No channel data available")
    
    print(f"\n📊 CREATING CHANNEL PERFORMANCE CHART")
    print(f"  Input rows: {len(df)}")
    print(f"  Columns: {df.columns.tolist()}")
    
    try:
        # ===================================================================
        # DETECT SOURCE/CHANNEL COLUMN
        # ===================================================================
        channel_patterns = [
            'source', 'utm_source', 'traffic_source', 'referrer',
            'channel', 'medium', 'utm_medium', 'acquisition_channel'
        ]
        
        source_col = None
        for pattern in channel_patterns:
            # Try exact match
            matches = [c for c in df.columns if pattern.lower() == c.lower()]
            if matches:
                source_col = matches[0]
                break
            # Try partial match
            matches = [c for c in df.columns if pattern.lower() in c.lower()]
            if matches:
                # Verify it's not a URL column
                sample = df[matches[0]].dropna().astype(str).head(10)
                if not sample.str.contains('http|www|\.com/', case=False, regex=True).any():
                    source_col = matches[0]
                    break
        
        # Fallback to first categorical column
        if not source_col:
            for col in df.columns:
                if df[col].dtype == 'object' and 2 < df[col].nunique() < 50:
                    sample = df[col].dropna().astype(str).head(10)
                    if not sample.str.contains('http|www|\.com/', case=False, regex=True).any():
                        source_col = col
                        break
        
        if not source_col:
            print("❌ No channel column found")
            return create_empty_chart("No channel column detected in data")
        
        print(f"  Using channel column: {source_col}")
        
        # ===================================================================
        # DETECT REVENUE/VALUE COLUMN
        # ===================================================================
        revenue_col = find_column(df, [
            'revenue', 'amount', 'total', 'price', 'net_worth', 'company_revenue', 'value'
        ]) or find_any_numeric_column(df, exclude_cols=[source_col])
        
        # ===================================================================
        # AGGREGATE DATA BY CHANNEL
        # ===================================================================
        df_clean = df.copy()
        
        if revenue_col and revenue_col in df.columns:
            # Parse revenue values
            df_clean['parsed_revenue'] = df_clean[revenue_col].apply(
                lambda x: parse_range_or_number(x) if pd.notna(x) else 0
            )
            
            channel_stats = df_clean.groupby(source_col).agg({
                'parsed_revenue': ['sum', 'count', 'mean']
            }).reset_index()
            
            channel_stats.columns = ['channel', 'total_revenue', 'conversions', 'avg_order_value']
            channel_stats = channel_stats.sort_values('total_revenue', ascending=False)
            
            y_col = 'total_revenue'
            y_label = 'Total Revenue ($)'
            
            print(f"  Revenue-based chart: Top channel = {channel_stats.iloc[0]['channel']}")
        else:
            # Just count conversions
            channel_stats = df_clean.groupby(source_col).size().reset_index(name='conversions')
            channel_stats.columns = ['channel', 'conversions']
            channel_stats = channel_stats.sort_values('conversions', ascending=False)
            
            y_col = 'conversions'
            y_label = 'Number of Conversions'
            
            print(f"  Conversion-based chart: Top channel = {channel_stats.iloc[0]['channel']}")
        
        # Take top 15 channels
        df_top = channel_stats.head(15).copy()
        
        # Shorten long channel names for display
        df_top['channel_short'] = df_top['channel'].apply(
            lambda x: str(x)[:40] + '...' if len(str(x)) > 40 else str(x)
        )
        
        # Sort by value for better visualization
        df_top = df_top.sort_values(y_col, ascending=True)
        
        # ===================================================================
        # CREATE CHART
        # ===================================================================
        fig = px.bar(
            df_top,
            y='channel_short',
            x=y_col,
            orientation='h',
            title=f"Top {len(df_top)} {source_col.replace('_', ' ').title()}s by Performance",
            labels={y_col: y_label, 'channel_short': source_col.replace('_', ' ').title()},
            color=y_col,
            color_continuous_scale='RdYlGn',
            text=y_col
        )
        
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=max(400, len(df_top) * 35),
            xaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                title=y_label,
                rangemode='tozero'
            ),
            yaxis=dict(
                showgrid=False,
                title=source_col.replace('_', ' ').title()
            ),
            showlegend=False,
            hovermode='y unified'
        )
        
        # Format text on bars
        if 'revenue' in y_col.lower():
            fig.update_traces(
                texttemplate='$%{x:,.0f}',
                textposition='outside',
                hovertemplate=f'<b>%{{y}}</b><br>{y_label}: $%{{x:,.2f}}<extra></extra>'
            )
        else:
            fig.update_traces(
                texttemplate='%{x:,.0f}',
                textposition='outside',
                hovertemplate=f'<b>%{{y}}</b><br>{y_label}: %{{x:,.0f}}<extra></extra>'
            )
        
        print(f"✅ Channel chart created with {len(df_top)} channels")
        return fig
    
    except Exception as e:
        print(f"❌ Error creating channel chart: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_chart(f"Error: {str(e)[:50]}")

def create_revenue_pie_chart(gross: float, refunded: float):
    """Create gross vs refunded revenue pie chart"""
    if gross == 0 and refunded == 0:
        return create_empty_chart("No revenue data")
    
    fig = go.Figure(data=[go.Pie(
        labels=['Gross Revenue', 'Refunded'],
        values=[gross, refunded],
        hole=.3,
        marker=dict(colors=['#2ecc71', '#e74c3c']),
        textinfo='label+percent+value',
        texttemplate='%{label}<br>$%{value:,.0f}<br>(%{percent})'
    )])
    
    fig.update_layout(
        title="Revenue Breakdown",
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

def create_segment_box_plot(df: pd.DataFrame, segment_col: str, value_col: str):
    """
    Create box plot for conversion distribution across segments
    Chart Type: BOX PLOT - Shows distribution and spread within segments
    """
    if df.empty:
        return create_empty_chart("No data available")
    
    try:
        fig = px.box(
            df,
            x=segment_col,
            y=value_col,
            title=f"Distribution of {value_col.replace('_', ' ').title()} by Segment",
            color=segment_col,
            points="outliers"
        )
        
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=450,
            xaxis=dict(tickangle=-45),
            showlegend=False
        )
        
        return fig
    
    except Exception as e:
        print(f"❌ Error creating box plot: {e}")
        return create_empty_chart(f"Error: {str(e)[:50]}")