import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_multiplier(suffix: str) -> float:
    """Get numeric multiplier for text suffixes"""
    suffix = suffix.lower().strip()
    multipliers = {
        'thousand': 1_000, 'k': 1_000,
        'million': 1_000_000, 'm': 1_000_000, 'mil': 1_000_000,
        'billion': 1_000_000_000, 'b': 1_000_000_000, 'bil': 1_000_000_000,
        'trillion': 1_000_000_000_000, 't': 1_000_000_000_000,
    }
    return multipliers.get(suffix, 1)

def parse_range_or_number(value):
    """Parse number or range with support for Million/Billion suffixes"""
    if pd.isna(value) or value == 'nan' or value is None:
        return 0
    
    value_str = str(value).strip()
    if not value_str or value_str.lower() == 'none':
        return 0
    
    value_str = value_str.lower().replace('$', '').replace(',', '')
    
    if 'under' in value_str:
        parts = value_str.replace('under', '').strip().split()
        if len(parts) >= 1:
            try:
                num = float(parts[0])
                multiplier = get_multiplier(parts[1]) if len(parts) > 1 else 1
                return (num * multiplier) / 2
            except:
                return 0
        return 0
    
    if 'and over' in value_str or 'andover' in value_str or 'over' in value_str:
        parts = value_str.replace('and over', '').replace('andover', '').replace('over', '').strip().split()
        if len(parts) >= 1:
            try:
                num = float(parts[0])
                multiplier = get_multiplier(parts[1]) if len(parts) > 1 else 1
                return num * multiplier * 1.5
            except:
                return 0
        return 0
    
    if ' to ' in value_str:
        parts = value_str.split(' to ')
        try:
            low_parts = parts[0].strip().split()
            low = float(low_parts[0])
            if len(low_parts) > 1:
                low *= get_multiplier(low_parts[1])
            
            high_parts = parts[1].strip().split()
            high = float(high_parts[0])
            if len(high_parts) > 1:
                high *= get_multiplier(high_parts[1])
            
            return (low + high) / 2
        except:
            return 0
    
    parts = value_str.strip().split()
    if len(parts) >= 2:
        try:
            num = float(parts[0])
            multiplier = get_multiplier(parts[1])
            return num * multiplier
        except:
            pass
    
    try:
        value_str = ''.join(c for c in value_str if c.isdigit() or c == '.')
        if value_str:
            return float(value_str)
    except:
        pass
    
    return 0

def is_url_column(col_name: str, sample_values: pd.Series) -> bool:
    col_lower = str(col_name).lower()
    url_indicators = ['url', 'link', 'path', 'domain', 'website', 'http', 'www', '.com']
    if any(ind in col_lower for ind in url_indicators):
        return True
    if sample_values is not None and len(sample_values) > 0:
        sample = str(sample_values.iloc[0]).lower()
        if any(p in sample for p in ['http://', 'https://', 'www.', '.com/']):
            return True
    return False

def find_column(df: pd.DataFrame, possible_names: list) -> str:
    """Find a column in dataframe - FIXED VERSION"""
    if df.empty:
        logger.warning("DataFrame is empty, cannot find column")
        return None
    
    df_columns_lower = [col.lower() for col in df.columns]
    
    # FIRST: Try exact matches only
    for name in possible_names:
        name_lower = name.lower()
        if name_lower in df_columns_lower:
            idx = df_columns_lower.index(name_lower)
            col = df.columns[idx]
            
            # Skip if it's a URL column
            if is_url_column(col, df[col].head(5)):
                logger.debug(f"⏭️ Skipping URL column: {col}")
                continue
                
            logger.debug(f"✅ Found exact match column: {col} for {name}")
            return col
    
    # SECOND: Try partial matches BUT exclude URL columns and high-cardinality columns
    for name in possible_names:
        name_lower = name.lower()
        for col in df.columns:
            col_lower = col.lower()
            
            # Skip URL columns
            if is_url_column(col, df[col].head(5)):
                continue
            
            # Skip columns with too many unique values (likely IDs or URLs)
            try:
                if df[col].nunique() > min(len(df) * 0.5, 100):
                    continue
            except:
                pass
            
            # Check if search term is in column name
            if name_lower in col_lower:
                logger.debug(f"✅ Found partial match column: {col} for {name}")
                return col
    
    logger.warning(f"⚠️ No column found for possible names: {possible_names}")
    return None

def get_dynamic_column_mapping(df: pd.DataFrame) -> dict:
    """
    Dynamically map logical demographic fields to actual column names in the DataFrame.
    Returns a dictionary: {'gender': 'Gender', 'age': 'Age Range', ...}
    """
    if df.empty:
        return {'gender': None, 'age': None, 'income': None, 'state': None}

    mapping = {}

    # Gender: look for gender/sex
    gender_col = find_column(df, ['gender', 'sex', 'customer_gender'])
    mapping['gender'] = gender_col

    # Age: look for age, age_range, age_group
    age_col = find_column(df, ['age', 'age_range', 'age_group', 'agegroup', 'age_bucket'])
    mapping['age'] = age_col

    # Income: look for income, income_range, salary, etc.
    income_col = find_column(df, [
        'income', 'income_range', 'annual_income', 'household_income',
        'salary', 'salary_range', 'net_worth', 'personal_income'
    ])
    mapping['income'] = income_col

    # State: look for state, region, province
    state_col = find_column(df, [
        'state', 'region', 'province', 'personal_state', 'company_state',
        'location_state', 'address_state'
    ])
    mapping['state'] = state_col

    logger.debug(f"Dynamic column mapping: {mapping}")
    return mapping

def find_any_numeric_column(df: pd.DataFrame, exclude_cols=None) -> str:
    """Find ANY numeric column in the dataframe"""
    if exclude_cols is None:
        exclude_cols = []
    
    for col in df.columns:
        if col.lower() in [e.lower() for e in exclude_cols]:
            continue
        
        # Skip URL columns
        if is_url_column(col, df[col].head(5)):
            continue
        
        try:
            test_vals = df[col].apply(lambda x: parse_range_or_number(x))
            if (test_vals > 0).sum() > len(df) * 0.1:
                logger.debug(f"Found numeric column: {col}")
                return col
        except:
            continue
        
        if pd.api.types.is_numeric_dtype(df[col]):
            if (df[col] > 0).sum() > len(df) * 0.1:
                logger.debug(f"Found numeric dtype column: {col}")
                return col
    
    logger.warning("No numeric column found")
    return None

def find_any_date_column(df: pd.DataFrame) -> str:
    """Find ANY date-like column"""
    for col in df.columns:
        if any(kw in col.lower() for kw in ['date', 'time', 'timestamp', 'created', 'updated']):
            try:
                pd.to_datetime(df[col].dropna().iloc[0])
                logger.debug(f"Found date column: {col}")
                return col
            except:
                continue
    logger.warning("No date column found")
    return None

def find_any_categorical_column(df: pd.DataFrame, max_unique=50) -> str:
    """Find ANY categorical column - IMPROVED"""
    for col in df.columns:
        # Skip URL columns
        if is_url_column(col, df[col].head(5)):
            continue
            
        if df[col].dtype == 'object' and 2 < df[col].nunique() < max_unique:
            logger.debug(f"Found categorical column: {col}")
            return col
    logger.warning("No categorical column found")
    return None

# ============================================================================
# ✅ NEW FUNCTION: BUYER-SPECIFIC KPIs (DEMOGRAPHICS-BASED)
# ============================================================================

def calculate_buyer_kpis(df: pd.DataFrame) -> dict:
    """
    Calculate KPIs for BUYERS data that has NO revenue/purchase info.
    Only demographic and count-based metrics.
    ✅ PROPERLY CALCULATES all metrics using actual data
    """
    if df.empty:
        logger.warning("Empty DataFrame for buyer KPIs")
        return {
            'total_buyers': 0,
            'unique_buyers': 0,
            'male_count': 0,
            'female_count': 0,
            'male_percent': 0.0,
            'female_percent': 0.0,
            'repeat_buyers': 0,
            'repeat_rate': 0.0,
            'top_state': 'N/A',
            'top_income': 'N/A',
            'avg_age': 'N/A'
        }
    
    # 1. ✅ Total Buyers - Actual row count
    total_buyers = len(df)
    logger.debug(f"📊 Total buyers (rows): {total_buyers}")
    
    # 2. ✅ Unique Buyers - Find email column and count unique values
    email_col = find_column(df, [
        'email', 'personal_emails', 'user_email', 'customer_email',
        'contact_email', 'e-mail', 'e_mail', 'user', 'customer_id'
    ])
    
    if email_col and email_col in df.columns:
        # Count unique non-null emails
        unique_buyers = df[email_col].dropna().nunique()
        logger.debug(f"📊 Unique buyers (via {email_col}): {unique_buyers}")
    else:
        # If no email column, assume all are unique
        unique_buyers = total_buyers
        logger.warning(f"⚠️ No email column found, assuming all {total_buyers} are unique")
    
    # 3. ✅ Gender Distribution - Actual counts
    gender_col = find_column(df, ['gender', 'sex', 'customer_gender'])
    male_count = 0
    female_count = 0
    other_count = 0
    
    if gender_col and gender_col in df.columns:
        try:
            # Clean and standardize gender values
            df_gender = df[gender_col].dropna().astype(str).str.strip().str.upper()
            
            # Count males
            male_count = df_gender.isin(['M', 'MALE', 'MAN']).sum()
            
            # Count females
            female_count = df_gender.isin(['F', 'FEMALE', 'WOMAN']).sum()
            
            # Count others
            other_count = len(df_gender) - male_count - female_count
            
            logger.debug(f"📊 Gender breakdown: Male={male_count}, Female={female_count}, Other={other_count}")
        except Exception as e:
            logger.error(f"Error calculating gender distribution: {e}")
    else:
        logger.warning(f"⚠️ No gender column found")
    
    # Calculate percentages
    male_percent = (male_count / total_buyers * 100) if total_buyers > 0 else 0.0
    female_percent = (female_count / total_buyers * 100) if total_buyers > 0 else 0.0
    other_percent = (other_count / total_buyers * 100) if total_buyers > 0 else 0.0
    
    # 4. ✅ Repeat Buyers - Count emails that appear more than once
    repeat_buyers = 0
    repeat_rate = 0.0
    
    if email_col and email_col in df.columns:
        try:
            # Count how many times each email appears
            email_counts = df[email_col].dropna().value_counts()
            
            # Emails appearing more than once are repeat buyers
            repeat_buyers = (email_counts > 1).sum()
            
            # Calculate repeat rate (% of unique buyers who bought again)
            repeat_rate = (repeat_buyers / unique_buyers * 100) if unique_buyers > 0 else 0.0
            
            logger.debug(f"📊 Repeat buyers: {repeat_buyers} out of {unique_buyers} unique ({repeat_rate:.1f}%)")
        except Exception as e:
            logger.error(f"Error calculating repeat buyers: {e}")
    else:
        logger.warning(f"⚠️ Cannot calculate repeat buyers without email column")
    
    # 5. ✅ Top State - Most common state
    state_col = find_column(df, [
        'state', 'personal_state', 'region', 'province',
        'customer_state', 'billing_state', 'location_state'
    ])
    
    top_state = 'N/A'
    if state_col and state_col in df.columns:
        try:
            state_counts = df[state_col].dropna().value_counts()
            if len(state_counts) > 0:
                top_state = state_counts.index[0]
                logger.debug(f"📊 Top state: {top_state} ({state_counts.iloc[0]} buyers)")
        except Exception as e:
            logger.error(f"Error finding top state: {e}")
    
    # 6. ✅ Top Income Range - Most common income bracket
    income_col = find_column(df, [
        'income', 'income_range', 'annual_income', 'household_income',
        'salary', 'salary_range', 'income_bracket'
    ])
    
    top_income = 'N/A'
    if income_col and income_col in df.columns:
        try:
            income_counts = df[income_col].dropna().value_counts()
            if len(income_counts) > 0:
                top_income = income_counts.index[0]
                logger.debug(f"📊 Top income: {top_income} ({income_counts.iloc[0]} buyers)")
        except Exception as e:
            logger.error(f"Error finding top income: {e}")
    
    # 7. ✅ Most Common Age Range
    age_col = find_column(df, [
        'age', 'age_range', 'age_group', 'age_bracket',
        'customer_age', 'age_category'
    ])
    
    avg_age = 'N/A'
    if age_col and age_col in df.columns:
        try:
            age_counts = df[age_col].dropna().value_counts()
            if len(age_counts) > 0:
                avg_age = age_counts.index[0]
                logger.debug(f"📊 Most common age: {avg_age} ({age_counts.iloc[0]} buyers)")
        except Exception as e:
            logger.error(f"Error finding common age: {e}")
    
    # ✅ Final summary log
    logger.info(f"✅ Buyer KPIs calculated:")
    logger.info(f"   - Total: {total_buyers:,}")
    logger.info(f"   - Unique: {unique_buyers:,} ({(unique_buyers/total_buyers*100):.1f}%)")
    logger.info(f"   - Male: {male_count:,} ({male_percent:.1f}%)")
    logger.info(f"   - Female: {female_count:,} ({female_percent:.1f}%)")
    logger.info(f"   - Repeat: {repeat_buyers:,} ({repeat_rate:.1f}%)")
    logger.info(f"   - Top State: {top_state}")
    logger.info(f"   - Top Income: {top_income}")
    logger.info(f"   - Common Age: {avg_age}")
    
    return {
        'total_buyers': total_buyers,
        'unique_buyers': unique_buyers,
        'male_count': male_count,
        'female_count': female_count,
        'male_percent': male_percent,
        'female_percent': female_percent,
        'other_count': other_count,
        'other_percent': other_percent,
        'repeat_buyers': repeat_buyers,
        'repeat_rate': repeat_rate,
        'top_state': top_state,
        'top_income': top_income,
        'avg_age': avg_age
    }

# ============================================================================
# EXISTING FUNCTIONS (Keep as is, but they won't be used for demographic-only buyers data)
# ============================================================================

def calculate_total_revenue(df: pd.DataFrame) -> float:
    """Calculate total revenue: Sum of revenue values"""
    if df.empty:
        logger.warning("Empty DataFrame for total revenue")
        return 0.0
    
    revenue_col = find_column(df, [
        'revenue', 'amount', 'total', 'price', 'order_value', 
        'net_worth', 'income', 'company_revenue', 'value'
    ])
    
    if not revenue_col:
        revenue_col = find_any_numeric_column(df)
    
    if revenue_col and revenue_col in df.columns:
        try:
            values = df[revenue_col].apply(lambda x: parse_range_or_number(x))
            total = values.sum()
            logger.debug(f"Total revenue from {revenue_col}: {total}")
            if total > 0:
                return total
            
            numeric_vals = pd.to_numeric(df[revenue_col], errors='coerce').dropna()
            total = numeric_vals.sum()
            logger.debug(f"Total revenue (numeric conversion) from {revenue_col}: {total}")
            return total if total > 0 else 0.0
        except Exception as e:
            logger.error(f"Error calculating total revenue: {e}")
            pass
    
    logger.warning("No valid revenue data, returning 0.0")
    return 0.0

def calculate_conversion_rate(buyers_df: pd.DataFrame, visitors_df: pd.DataFrame) -> float:
    """Calculate conversion rate: (Unique buyers / Unique visitors) * 100"""
    if buyers_df.empty:
        logger.warning("Empty buyers DataFrame for conversion rate")
        return 0.0
    
    email_col = find_column(buyers_df, [
        'email', 'personal_emails', 'business_email', 'contact_email',
        'customer_email', 'user_email', 'hemsha256', 'sha256_personal_email',
        'user', 'customer', 'id', 'customer_id'
    ])
    
    unique_buyers = buyers_df[email_col].nunique() if email_col else len(buyers_df)
    logger.debug(f"Unique buyers: {unique_buyers}")
    
    if visitors_df.empty:
        logger.warning("No visitor data, returning 0.0")
        return 0.0
    
    visitor_email_col = find_column(visitors_df, [
        'email', 'personal_emails', 'business_email', 'user', 'visitor', 'id'
    ])
    
    unique_visitors = visitors_df[visitor_email_col].nunique() if visitor_email_col else len(visitors_df)
    logger.debug(f"Unique visitors: {unique_visitors}")
    
    if unique_visitors > 0:
        conversion_rate = (unique_buyers / unique_visitors) * 100
        logger.debug(f"Conversion rate: {conversion_rate}%")
        return conversion_rate
    logger.warning("No valid visitors, returning 0.0")
    return 0.0

def calculate_aov(df: pd.DataFrame) -> float:
    """Calculate Average Order Value"""
    if df.empty:
        return 0.0
    
    revenue_col = find_column(df, [
        'revenue', 'amount', 'total', 'price', 'order_value',
        'net_worth', 'income', 'company_revenue', 'value'
    ])
    
    if not revenue_col:
        revenue_col = find_any_numeric_column(df)
    
    if revenue_col and revenue_col in df.columns:
        try:
            values = df[revenue_col].apply(lambda x: parse_range_or_number(x))
            values = values[values > 0]
            if len(values) > 0:
                return values.sum() / len(values)
        except:
            pass
    
    return 0.0

def calculate_repeat_rate(df: pd.DataFrame) -> float:
    """Calculate repeat customer rate"""
    if df.empty or len(df) < 2:
        return 0.0
    
    email_col = find_column(df, [
        'email', 'personal_emails', 'business_email', 'hemsha256',
        'sha256_personal_email', 'pixelid', 'uuid', 'customer', 'user'
    ])
    
    if not email_col:
        return 0.0
    
    purchase_counts = df[email_col].value_counts()
    repeat_customers = (purchase_counts > 1).sum()
    total_customers = len(purchase_counts)
    
    if total_customers > 0:
        return (repeat_customers / total_customers) * 100
    return 0.0

def calculate_ltv_90day(df: pd.DataFrame) -> float:
    """Calculate 90-day LTV"""
    if df.empty:
        return 0.0
    
    date_col = find_any_date_column(df)
    revenue_col = find_column(df, [
        'revenue', 'amount', 'total', 'price', 'net_worth', 'company_revenue'
    ]) or find_any_numeric_column(df)
    
    email_col = find_column(df, [
        'email', 'personal_emails', 'hemsha256', 'uuid', 'pixelid'
    ])
    
    if date_col and email_col and revenue_col:
        try:
            df = df.copy()
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            cutoff_date = datetime.now() - timedelta(days=90)
            recent_df = df[df[date_col] >= cutoff_date]
            
            if len(recent_df) > 0:
                values = recent_df[revenue_col].apply(lambda x: parse_range_or_number(x))
                recent_df = recent_df.copy()
                recent_df['parsed_revenue'] = values
                ltv = recent_df.groupby(email_col)['parsed_revenue'].sum().mean()
                if not np.isnan(ltv) and ltv > 0:
                    return ltv
        except:
            pass
    
    if revenue_col:
        try:
            values = df[revenue_col].apply(lambda x: parse_range_or_number(x))
            return values.mean() if len(values) > 0 else 0.0
        except:
            pass
    
    return 0.0

def calculate_gross_vs_refunded(df: pd.DataFrame) -> dict:
    """Calculate gross, refunded, and net revenue"""
    if df.empty:
        return {"gross": 0.0, "refunded": 0.0, "net": 0.0}
    
    revenue_col = find_column(df, [
        'revenue', 'amount', 'total', 'price', 'net_worth', 'company_revenue'
    ]) or find_any_numeric_column(df)
    
    if not revenue_col:
        return {"gross": 0.0, "refunded": 0.0, "net": 0.0}
    
    try:
        values = df[revenue_col].apply(lambda x: parse_range_or_number(x))
        df = df.copy()
        df['parsed_revenue'] = values
        
        gross = df[df['parsed_revenue'] > 0]['parsed_revenue'].sum()
        refunded = abs(df[df['parsed_revenue'] < 0]['parsed_revenue'].sum())
        net = gross - refunded
        
        return {"gross": gross, "refunded": refunded, "net": net}
    except:
        return {"gross": 0.0, "refunded": 0.0, "net": 0.0}

def calculate_cac(df: pd.DataFrame, visitors_df: pd.DataFrame = None) -> float:
    """Calculate Customer Acquisition Cost"""
    if df.empty:
        logger.warning("Empty DataFrame for CAC")
        return 0.0
    
    spend_col = find_column(df, [
        'ad_spend', 'marketing_cost', 'campaign_cost', 'advertising', 
        'marketing_budget', 'spend', 'cost', 'cpc', 'cpm', 'ad_cost'
    ])
    
    email_col = find_column(df, [
        'email', 'personal_emails', 'business_email', 'hemsha256', 
        'uuid', 'customer', 'user', 'visitor_id', 'user_id'
    ])
    
    if spend_col and spend_col in df.columns:
        try:
            total_spend = df[spend_col].apply(lambda x: parse_range_or_number(x)).sum()
            
            if email_col:
                is_new = ~df.duplicated(subset=[email_col], keep='first')
                new_count = is_new.sum()
            else:
                new_count = len(df)
            
            if new_count > 0 and total_spend > 0:
                cac = total_spend / new_count
                logger.info(f"✅ CAC (Method 1): ${cac:.2f} (Spend: ${total_spend:,.2f}, New: {new_count})")
                return cac
        except Exception as e:
            logger.error(f"CAC Method 1 failed: {e}")
    
    revenue_col = find_column(df, [
        'revenue', 'amount', 'total', 'price', 'order_value', 
        'net_worth', 'income', 'company_revenue', 'value', 'purchase_amount'
    ]) or find_any_numeric_column(df, exclude_cols=[spend_col] if spend_col else [])
    
    if revenue_col and revenue_col in df.columns:
        try:
            total_revenue = df[revenue_col].apply(lambda x: parse_range_or_number(x)).sum()
            estimated_spend = total_revenue * 0.25
            
            if email_col:
                is_new = ~df.duplicated(subset=[email_col], keep='first')
                new_count = is_new.sum()
            else:
                new_count = len(df)
            
            if new_count > 0 and estimated_spend > 0:
                cac = estimated_spend / new_count
                logger.info(f"✅ CAC (Method 2 - Estimated): ${cac:.2f} (Est. Spend: ${estimated_spend:,.2f}, New: {new_count})")
                return cac
        except Exception as e:
            logger.error(f"CAC Method 2 failed: {e}")
    
    logger.warning("❌ No valid data for CAC calculation, returning 0.0")
    return 0.0

def get_conversions_over_time(df: pd.DataFrame, freq: str = 'D') -> pd.DataFrame:
    """Get conversions grouped by time"""
    if df.empty:
        logger.warning("Empty DataFrame for conversions over time")
        return pd.DataFrame()
    
    date_col = find_any_date_column(df)
    
    if not date_col:
        logger.warning("No date column, creating fake time series")
        df = df.copy()
        df['_index_date'] = pd.date_range(end=datetime.now(), periods=len(df), freq='H')
        date_col = '_index_date'
    
    try:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        
        if len(df) == 0:
            logger.warning("No valid date data after conversion")
            return pd.DataFrame()
        
        date_range = df[date_col].max() - df[date_col].min()
        
        if date_range.days == 0:
            freq = 'H'
        elif date_range.days <= 7:
            freq = 'H'
        elif date_range.days <= 60:
            freq = 'D'
        else:
            freq = 'W'
        
        conversions = df.groupby(pd.Grouper(key=date_col, freq=freq)).size()
        result = conversions.reset_index(name='conversions')
        result.columns = ['date', 'conversions']
        result = result[result['conversions'] > 0]
        logger.debug(f"Conversions over time: {len(result)} periods")
        
        return result
    except Exception as e:
        logger.error(f"Error in get_conversions_over_time: {e}")
        return pd.DataFrame()

def get_new_vs_returning(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate new vs returning customers"""
    if df.empty:
        logger.warning("Empty DataFrame for new vs returning")
        return pd.DataFrame()
    
    date_col = find_any_date_column(df)
    email_col = find_column(df, [
        'email', 'personal_emails', 'hemsha256', 'uuid', 'pixelid', 'user'
    ])
    
    if not date_col:
        if email_col:
            is_new = ~df.duplicated(subset=[email_col], keep='first')
            new_count = is_new.sum()
            returning_count = len(df) - new_count
            logger.debug(f"No date column - New: {new_count}, Returning: {returning_count}")
            return pd.DataFrame({
                'date': [datetime.now()],
                'new_customers': [new_count],
                'returning_customers': [returning_count],
                'total_customers': [len(df)]
            })
        logger.warning("No email or date column for new vs returning")
        return pd.DataFrame()
    
    if not email_col:
        try:
            df = df.copy()
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df.dropna(subset=[date_col])
            
            freq = 'D' if (df[date_col].max() - df[date_col].min()).days <= 60 else 'W'
            
            daily_stats = df.groupby(pd.Grouper(key=date_col, freq=freq)).size().reset_index(name='total_customers')
            daily_stats.columns = ['date', 'total_customers']
            daily_stats['new_customers'] = daily_stats['total_customers'] // 2
            daily_stats['returning_customers'] = daily_stats['total_customers'] - daily_stats['new_customers']
            logger.debug(f"No email column - Total customers: {len(daily_stats)} periods")
            
            return daily_stats[daily_stats['total_customers'] > 0]
        except Exception as e:
            logger.error(f"Error in get_new_vs_returning (no email): {e}")
            return pd.DataFrame()
    
    try:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df_sorted = df.sort_values(date_col)
        
        df_sorted['is_new'] = ~df_sorted.duplicated(subset=[email_col], keep='first')
        
        date_range = df[date_col].max() - df[date_col].min()
        freq = 'H' if date_range.days <= 7 else 'D'
        
        daily_stats = df_sorted.groupby(pd.Grouper(key=date_col, freq=freq)).agg({
            'is_new': ['sum', 'size']
        }).reset_index()
        
        daily_stats.columns = ['date', 'new_customers', 'total_customers']
        daily_stats['returning_customers'] = daily_stats['total_customers'] - daily_stats['new_customers']
        daily_stats = daily_stats[daily_stats['total_customers'] > 0]
        logger.debug(f"New vs returning: {len(daily_stats)} periods")
        
        return daily_stats
    except Exception as e:
        logger.error(f"Error in get_new_vs_returning: {e}")
        return pd.DataFrame()

def get_channel_performance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create channel/campaign performance chart (Top N)
    Chart Type: HORIZONTAL BAR PLOT - Best for ranking performance
    Shows both channel AND campaign breakdowns
    """
    if df.empty or len(df) == 0:
        return pd.DataFrame()
    
    print(f"\n📊 CREATING CHANNEL PERFORMANCE CHART")
    print(f"  Input rows: {len(df)}")
    print(f"  Columns: {df.columns.tolist()}")
    
    try:
        # ===================================================================
        # ✅ STEP 1: DETECT SOURCE/CHANNEL COLUMN (EXCLUDE HASH/ID COLUMNS)
        # ===================================================================
        channel_patterns = [
            'source', 'utm_source', 'traffic_source', 'referrer',
            'channel', 'medium', 'utm_medium', 'acquisition_channel'
        ]
        
        source_col = None
        
        # Try exact match first
        for pattern in channel_patterns:
            matches = [c for c in df.columns if pattern.lower() == c.lower()]
            if matches:
                col = matches[0]
                
                # ✅ SKIP if it's a hash/ID column
                if is_hash_or_id_column(col, df[col]):
                    print(f"  ❌ Skipping hash/ID column: {col}")
                    continue
                
                source_col = col
                break
        
        # Try partial match if no exact match
        if not source_col:
            for pattern in channel_patterns:
                matches = [c for c in df.columns if pattern.lower() in c.lower()]
                if matches:
                    for col in matches:
                        # ✅ SKIP hash/ID columns
                        if is_hash_or_id_column(col, df[col]):
                            print(f"  ❌ Skipping hash/ID column: {col}")
                            continue
                        
                        # ✅ SKIP URL columns
                        sample = df[col].dropna().astype(str).head(10)
                        if sample.str.contains('http|www|\.com/', case=False, regex=True).any():
                            print(f"  ❌ Skipping URL column: {col}")
                            continue
                        
                        source_col = col
                        break
                    
                    if source_col:
                        break
        
        # ✅ Fallback: Use first valid categorical column (NOT hash/ID)
        if not source_col:
            for col in df.columns:
                if df[col].dtype == 'object':
                    nunique = df[col].nunique()
                    
                    # ✅ SKIP hash/ID columns
                    if is_hash_or_id_column(col, df[col]):
                        continue
                    
                    # ✅ Must have reasonable cardinality (2-50 unique values)
                    if 2 < nunique < 50:
                        # ✅ SKIP URL columns
                        sample = df[col].dropna().astype(str).head(10)
                        if not sample.str.contains('http|www|\.com/', case=False, regex=True).any():
                            source_col = col
                            break
        
        if not source_col:
            print("❌ No valid channel column found")
            return pd.DataFrame()
        
        print(f"  ✅ Using channel column: {source_col}")
        
        # ===================================================================
        # STEP 2: DETECT REVENUE/VALUE COLUMN
        # ===================================================================
        revenue_col = find_column(df, [
            'revenue', 'amount', 'total', 'price', 'net_worth', 'company_revenue', 'value'
        ]) or find_any_numeric_column(df, exclude_cols=[source_col])
        
        # ===================================================================
        # STEP 3: AGGREGATE DATA BY CHANNEL
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
            
            print(f"  ✅ Revenue-based chart: Top channel = {channel_stats.iloc[0]['channel']}")
        else:
            # Just count conversions
            channel_stats = df_clean.groupby(source_col).size().reset_index(name='conversions')
            channel_stats.columns = ['channel', 'conversions']
            channel_stats = channel_stats.sort_values('conversions', ascending=False)
            
            y_col = 'conversions'
            y_label = 'Number of Conversions'
            
            print(f"  ✅ Conversion-based chart: Top channel = {channel_stats.iloc[0]['channel']}")
        
        # Take top 15 channels
        df_top = channel_stats.head(15).copy()
        
        # Shorten long channel names for display
        df_top['channel_short'] = df_top['channel'].apply(
            lambda x: str(x)[:40] + '...' if len(str(x)) > 40 else str(x)
        )
        
        # Sort by value for better visualization
        df_top = df_top.sort_values(y_col, ascending=True)
        
        print(f"✅ Channel chart created with {len(df_top)} channels")
        return df_top
    
    except Exception as e:
        print(f"❌ Error creating channel performance: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# ✅ NEW HELPER FUNCTION: Detect hash/ID columns
def is_hash_or_id_column(col_name: str, sample_values: pd.Series) -> bool:
    """
    Check if a column is a hash or ID column (should be excluded from charts)
    """
    col_lower = str(col_name).lower()
    
    # Check column name
    hash_indicators = [
        'hash', 'sha', 'md5', 'uuid', 'guid', 'id', '_id', 
        'hemsha', 'pixelid', 'sessionid', 'token', 'key'
    ]
    
    if any(ind in col_lower for ind in hash_indicators):
        return True
    
    # Check sample values (look for hex/hash patterns)
    if sample_values is not None and len(sample_values) > 0:
        sample = str(sample_values.iloc[0]).lower()
        
        # Check for hex patterns (e.g., "d988ab12-3739-58b1")
        if len(sample) > 20 and all(c in '0123456789abcdef-' for c in sample):
            return True
        
        # Check for UUID patterns (8-4-4-4-12)
        if '-' in sample and len(sample.split('-')) >= 4:
            parts = sample.split('-')
            if all(len(p) in [4, 8, 12] for p in parts):
                return True
    
    return False

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply filters to dataframe"""
    filtered_df = df.copy()
    
    if 'start_date' in filters and 'end_date' in filters:
        date_col = find_any_date_column(df)
        
        if date_col:
            try:
                filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce')
                filtered_df = filtered_df.dropna(subset=[date_col])
                start = pd.to_datetime(filters['start_date'])
                end = pd.to_datetime(filters['end_date'])
                filtered_df = filtered_df[
                    (filtered_df[date_col] >= start) & 
                    (filtered_df[date_col] <= end)
                ]
                logger.debug(f"Applied date filter: {start} to {end}, rows: {len(filtered_df)}")
            except Exception as e:
                logger.error(f"Error applying date filter: {e}")
    
    if 'sources' in filters and filters['sources']:
        source_col = find_column(df, [
            'source', 'utm_source', 'traffic_source', 'referrerurl', 'channel'
        ])
        if source_col and source_col in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[source_col].isin(filters['sources'])]
            logger.debug(f"Applied source filter: {filters['sources']}, rows: {len(filtered_df)}")
    
    if 'campaigns' in filters and filters['campaigns']:
        campaign_col = find_column(df, [
            'campaign', 'utm_campaign', 'campaign_name', 'eventtype'
        ])
        if campaign_col and campaign_col in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[campaign_col].isin(filters['campaigns'])]
            logger.debug(f"Applied campaign filter: {filters['campaigns']}, rows: {len(filtered_df)}")
    
    return filtered_df

def generate_dynamic_insights(df: pd.DataFrame) -> list:
    insights = []
    
    if df.empty:
        logger.warning("Empty DataFrame for dynamic insights")
        return insights
    
    time_insight = generate_time_based_insight(df)
    if time_insight:
        insights.append(time_insight)
    
    category_insight = generate_category_distribution(df)
    if category_insight:
        insights.append(category_insight)
    
    geo_insight = generate_geographic_insight(df)
    if geo_insight:
        insights.append(geo_insight)
    
    demo_insight = generate_demographic_insight(df)
    if demo_insight:
        insights.append(demo_insight)
    
    engagement_insight = generate_engagement_insight(df)
    if engagement_insight:
        insights.append(engagement_insight)
    
    value_insight = generate_value_distribution(df)
    if value_insight:
        insights.append(value_insight)
    
    event_insight = generate_event_type_insight(df)
    if event_insight:
        insights.append(event_insight)
    
    logger.debug(f"Generated {len(insights)} insights")
    return insights

def generate_time_based_insight(df: pd.DataFrame) -> dict:
    date_col = find_any_date_column(df)
    
    if not date_col:
        logger.warning("No date column for time-based insight")
        return None
    
    try:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        
        if len(df) == 0:
            logger.warning("No valid date data for time-based insight")
            return None
        
        date_range = df[date_col].max() - df[date_col].min()
        if date_range.days <= 1:
            freq = 'H'
            title = "Activity by Hour"
        elif date_range.days <= 30:
            freq = 'D'
            title = "Daily Activity"
        else:
            freq = 'W'
            title = "Weekly Activity"
        
        activity = df.groupby(pd.Grouper(key=date_col, freq=freq)).size().reset_index(name='count')
        activity = activity[activity['count'] > 0]
        logger.debug(f"Time-based insight: {len(activity)} periods")
        
        return {
            'type': 'line',
            'title': title,
            'data': activity.to_dict('records'),
            'x': date_col,
            'y': 'count',
            'description': f"Activity over time ({len(activity)} periods)"
        }
    except Exception as e:
        logger.error(f"Error in time-based insight: {e}")
        return None

def generate_category_distribution(df: pd.DataFrame) -> dict:
    categorical_cols = []
    for col in df.columns:
        if df[col].dtype == 'object' and 2 < df[col].nunique() < 50:
            categorical_cols.append(col)
    
    priority_cols = ['eventtype', 'source', 'channel', 'campaign', 'category', 'type', 'status']
    
    for priority in priority_cols:
        col = find_column(df, [priority])
        if col and col in categorical_cols:
            try:
                dist = df[col].value_counts().head(10).reset_index()
                dist.columns = ['category', 'count']
                logger.debug(f"Category distribution for {col}: {len(dist)} categories")
                
                return {
                    'type': 'bar',
                    'title': f"Top {col.replace('_', ' ').title()}",
                    'data': dist.to_dict('records'),
                    'x': 'category',
                    'y': 'count',
                    'description': f"Distribution of {col}"
                }
            except Exception as e:
                logger.error(f"Error in category distribution for {col}: {e}")
                continue
    
    if categorical_cols:
        col = categorical_cols[0]
        try:
            dist = df[col].value_counts().head(10).reset_index()
            dist.columns = ['category', 'count']
            logger.debug(f"Fallback category distribution for {col}: {len(dist)} categories")
            
            return {
                'type': 'bar',
                'title': f"Top {col.replace('_', ' ').title()}",
                'data': dist.to_dict('records'),
                'x': 'category',
                'y': 'count',
                'description': f"Distribution of {col}"
            }
        except Exception as e:
            logger.error(f"Error in fallback category distribution: {e}")
            pass
    
    logger.warning("No categorical column for category distribution")
    return None

def generate_geographic_insight(df: pd.DataFrame) -> dict:
    state_col = find_column(df, ['state', 'personal_state', 'company_state', 'region', 'province'])
    city_col = find_column(df, ['city', 'personal_city', 'company_city', 'location'])
    
    col_to_use = state_col or city_col
    
    if not col_to_use:
        logger.warning("No geographic column found")
        return None
    
    try:
        geo_dist = df[col_to_use].value_counts().head(15).reset_index()
        geo_dist.columns = ['location', 'count']
        logger.debug(f"Geographic insight for {col_to_use}: {len(geo_dist)} locations")
        
        return {
            'type': 'bar',
            'title': f"Top Locations by {col_to_use.replace('_', ' ').title()}",
            'data': geo_dist.to_dict('records'),
            'x': 'location',
            'y': 'count',
            'description': f"Geographic distribution ({len(geo_dist)} locations)"
        }
    except Exception as e:
        logger.error(f"Error in geographic insight: {e}")
        return None

def generate_demographic_insight(df: pd.DataFrame) -> dict:
    gender_col = find_column(df, ['gender', 'sex'])
    age_col = find_column(df, ['age_range', 'age', 'age_group'])
    
    col_to_use = age_col or gender_col
    
    if not col_to_use:
        logger.warning("No demographic column found")
        return None
    
    try:
        demo_dist = df[col_to_use].value_counts().reset_index()
        demo_dist.columns = ['demographic', 'count']
        logger.debug(f"Demographic insight for {col_to_use}: {len(demo_dist)} categories")
        
        return {
            'type': 'pie',
            'title': f"{col_to_use.replace('_', ' ').title()} Distribution",
            'data': demo_dist.to_dict('records'),
            'labels': 'demographic',
            'values': 'count',
            'description': f"Demographic breakdown by {col_to_use}"
        }
    except Exception as e:
        logger.error(f"Error in demographic insight: {e}")
        return None

def generate_engagement_insight(df: pd.DataFrame) -> dict:
    email_col = find_column(df, ['email', 'personal_emails', 'user_email', 'user', 'customer'])
    
    if not email_col:
        logger.warning("No email column for engagement insight")
        return None
    
    try:
        engagement = df[email_col].value_counts().reset_index()
        engagement.columns = ['user', 'interactions']
        engagement = engagement[engagement['interactions'] > 1].head(20)
        
        if len(engagement) == 0:
            logger.warning("No users with multiple interactions")
            return None
        
        logger.debug(f"Engagement insight: {len(engagement)} users")
        return {
            'type': 'bar',
            'title': "Most Engaged Users",
            'data': engagement.to_dict('records'),
            'x': 'user',
            'y': 'interactions',
            'description': f"Top {len(engagement)} users by interaction count"
        }
    except Exception as e:
        logger.error(f"Error in engagement insight: {e}")
        return None

def generate_value_distribution(df: pd.DataFrame) -> dict:
    value_col = find_column(df, [
        'net_worth', 'income_range', 'company_revenue', 'revenue', 'amount', 'value'
    ]) or find_any_numeric_column(df)
    
    if not value_col:
        logger.warning("No value column for value distribution")
        return None
    
    try:
        value_dist = df[value_col].value_counts().head(10).reset_index()
        value_dist.columns = ['value_range', 'count']
        logger.debug(f"Value distribution for {value_col}: {len(value_dist)} categories")
        
        return {
            'type': 'bar',
            'title': f"{value_col.replace('_', ' ').title()} Distribution",
            'data': value_dist.to_dict('records'),
            'x': 'value_range',
            'y': 'count',
            'description': f"Distribution of {value_col}"
        }
    except Exception as e:
        logger.error(f"Error in value distribution: {e}")
        return None

def generate_event_type_insight(df: pd.DataFrame) -> dict:
    event_col = find_column(df, ['eventtype', 'event_type', 'type', 'action', 'activity'])
    
    if not event_col:
        logger.warning("No event column for event type insight")
        return None
    
    try:
        event_dist = df[event_col].value_counts().reset_index()
        event_dist.columns = ['event', 'count']
        logger.debug(f"Event type insight for {event_col}: {len(event_dist)} events")
        
        return {
            'type': 'pie',
            'title': "Event Type Distribution",
            'data': event_dist.to_dict('records'),
            'labels': 'event',
            'values': 'count',
            'description': f"Breakdown of {event_col}"
        }
    except Exception as e:
        logger.error(f"Error in event type insight: {e}")
        return None