import pandas as pd
import chardet
import gzip
from typing import Optional, Tuple

def detect_encoding(file_path: str) -> str:
    """Detect file encoding"""
    with open(file_path, 'rb') as f:
        raw = f.read(10000)
        result = chardet.detect(raw)
        return result['encoding'] or 'utf-8'

def read_csv_file(file_path: str, encoding: Optional[str] = None) -> pd.DataFrame:
    """Read CSV file with auto-detection"""
    if not encoding:
        encoding = detect_encoding(file_path)
    
    # Handle gzip files
    if file_path.endswith('.gz'):
        with gzip.open(file_path, 'rt', encoding=encoding) as f:
            df = pd.read_csv(f)
    else:
        # Try different delimiters
        try:
            df = pd.read_csv(file_path, encoding=encoding)
        except:
            try:
                df = pd.read_csv(file_path, encoding=encoding, sep='\t')
            except:
                df = pd.read_csv(file_path, encoding=encoding, sep=';')
    
    return df

def get_csv_preview(file_path: str, n_rows: int = 50) -> Tuple[pd.DataFrame, list]:
    """Get preview of CSV file"""
    df = read_csv_file(file_path)
    preview = df.head(n_rows)
    columns = df.columns.tolist()
    return preview, columns

def validate_csv_columns(df: pd.DataFrame, required_columns: list) -> dict:
    """Validate that required columns exist"""
    missing = [col for col in required_columns if col not in df.columns]
    return {
        "valid": len(missing) == 0,
        "missing_columns": missing
    }

def apply_column_mapping(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Apply column mapping to dataframe"""
    rename_map = {k: v for k, v in mapping.items() if v}
    df_mapped = df.rename(columns=rename_map)
    return df_mapped

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Basic cleaning operations"""
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # Strip whitespace from string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].str.strip() if df[col].dtype == 'object' else df[col]
    
    return df