# backend/ai_assistant.py - COMPLETE RAG IMPLEMENTATION
import google.generativeai as genai
import os
import json
import pandas as pd
import numpy as np
import re
from typing import List, Dict, Optional, Any
from difflib import SequenceMatcher
from dotenv import load_dotenv
import logging
# from google.generativeai.types import HarmCategory, HarmBlockThreshold
logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ============================================================================
# VECTOR STORE - Simple in-memory storage for data embeddings
# ============================================================================
class SimpleVectorStore:
    """
    Simple vector store that:
    1. Stores data summaries and statistics
    2. Retrieves relevant context for queries
    3. No external database needed - uses in-memory storage
    """
    
    def __init__(self):
        self.workspaces: Dict[int, Dict[str, Any]] = {}
        logger.info("✅ Vector store initialized")
    
    def store_data(self, workspace_id: int, file_type: str, df: pd.DataFrame):
        """
        Store data summary and statistics for a workspace
        
        Args:
            workspace_id: The workspace ID
            file_type: 'buyers' or 'visitors'
            df: The uploaded dataframe
        """
        if workspace_id not in self.workspaces:
            self.workspaces[workspace_id] = {'buyers': None, 'visitors': None}
        
        # Create comprehensive data summary
        summary = {
            'file_type': file_type,
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'columns': df.columns.tolist(),
            'data_types': df.dtypes.astype(str).to_dict(),
            'sample_data': df.head(10).to_dict('records'),  # First 10 rows
            'statistics': self._calculate_statistics(df),
            'column_summaries': self._get_column_summaries(df)
        }
        
        self.workspaces[workspace_id][file_type] = summary
        logger.info(f"📊 Stored {file_type} data for workspace {workspace_id}: {len(df)} rows × {len(df.columns)} columns")
    
    def _calculate_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive statistics from the dataframe"""
        stats = {
            'row_count': len(df),
            'column_count': len(df.columns)
        }
        
        # Numeric columns statistics
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            stats['numeric_columns'] = {}
            for col in numeric_cols[:10]:  # Limit to first 10 numeric columns
                stats['numeric_columns'][col] = {
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'mean': float(df[col].mean()),
                    'median': float(df[col].median()),
                    'sum': float(df[col].sum())
                }
        
        # Categorical columns
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        if categorical_cols:
            stats['categorical_columns'] = {}
            for col in categorical_cols[:10]:  # Limit to first 10
                unique_count = df[col].nunique()
                if unique_count < 50:  # Only store value counts if reasonable
                    stats['categorical_columns'][col] = {
                        'unique_count': int(unique_count),
                        'top_values': df[col].value_counts().head(5).to_dict()
                    }
        
        # Date columns
        date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        if date_cols:
            stats['date_columns'] = {}
            for col in date_cols:
                stats['date_columns'][col] = {
                    'min_date': str(df[col].min()),
                    'max_date': str(df[col].max())
                }
        
        return stats
    
    def _get_column_summaries(self, df: pd.DataFrame) -> Dict[str, str]:
        """Get human-readable summaries for each column"""
        summaries = {}
        for col in df.columns[:20]:  # Limit to first 20 columns
            col_type = str(df[col].dtype)
            unique_count = df[col].nunique()
            null_count = df[col].isnull().sum()
            
            summary = f"Column '{col}' ({col_type}): {unique_count} unique values"
            if null_count > 0:
                summary += f", {null_count} nulls"
            
            # Add sample values
            sample_values = df[col].dropna().head(3).astype(str).tolist()
            if sample_values:
                summary += f". Sample: {', '.join(sample_values[:3])}"
            
            summaries[col] = summary
        
        return summaries
    
    def get_context(self, workspace_id: int, query: str) -> str:
        """
        Retrieve relevant context for a query
        
        Args:
            workspace_id: The workspace to search in
            query: The user's question
        
        Returns:
            Formatted context string for the AI
        """
        if workspace_id not in self.workspaces:
            return "No data available for this workspace."
        
        workspace_data = self.workspaces[workspace_id]
        context_parts = []
        
        # Add buyers data context
        if workspace_data['buyers']:
            buyers = workspace_data['buyers']
            context_parts.append(self._format_data_context('Buyers', buyers))
        
        # Add visitors data context
        if workspace_data['visitors']:
            visitors = workspace_data['visitors']
            context_parts.append(self._format_data_context('Visitors', visitors))
        
        if not context_parts:
            return "No data uploaded yet."
        
        return "\n\n".join(context_parts)
    
    def _format_data_context(self, data_type: str, data: Dict[str, Any]) -> str:
        """Format data summary as context for AI"""
        context = f"=== {data_type} Data ===\n"
        context += f"Total Records: {data['total_rows']:,}\n"
        context += f"Total Columns: {data['total_columns']}\n"
        context += f"Columns: {', '.join(data['columns'][:15])}"
        if len(data['columns']) > 15:
            context += f" ... and {len(data['columns']) - 15} more"
        context += "\n\n"
        
        # Add statistics
        if 'statistics' in data:
            stats = data['statistics']
            context += "Key Statistics:\n"
            
            # Numeric columns
            if 'numeric_columns' in stats:
                context += "Numeric Columns:\n"
                for col, col_stats in list(stats['numeric_columns'].items())[:5]:
                    context += f"  - {col}: min={col_stats['min']:.2f}, max={col_stats['max']:.2f}, "
                    context += f"mean={col_stats['mean']:.2f}, sum={col_stats['sum']:.2f}\n"
            
            # Categorical columns
            if 'categorical_columns' in stats:
                context += "\nCategorical Columns:\n"
                for col, col_stats in list(stats['categorical_columns'].items())[:5]:
                    context += f"  - {col}: {col_stats['unique_count']} unique values\n"
                    if 'top_values' in col_stats:
                        top_vals = list(col_stats['top_values'].items())[:3]
                        context += f"    Top values: {', '.join([f'{k} ({v})' for k, v in top_vals])}\n"
        
        # Add sample data
        if 'sample_data' in data and data['sample_data']:
            context += "\nSample Records (first 3):\n"
            for i, record in enumerate(data['sample_data'][:3], 1):
                context += f"Record {i}: "
                # Show first 5 fields
                items = list(record.items())[:5]
                context += ", ".join([f"{k}={v}" for k, v in items])
                context += "\n"
        
        return context


# Global vector store instance
vector_store = SimpleVectorStore()


# ============================================================================
# RAG-POWERED QUERY FUNCTION
# ============================================================================
def query_ai_with_rag(query: str, workspace_id: int) -> Dict[str, Any]:
    """
    Main RAG function: Retrieves context and generates response
    
    Args:
        query: User's question
        workspace_id: The workspace to query
    
    Returns:
        Dictionary with response and metadata
    """
    if not GEMINI_API_KEY:
        return {
            'response': "⚠️ AI assistant is not configured. Please set GEMINI_API_KEY in .env file.",
            'sources': [],
            'context_used': False
        }
    
    try:
        # Step 1: Retrieve relevant context
        context = vector_store.get_context(workspace_id, query)
        logger.info(f"📚 Retrieved context ({len(context)} chars) for query: {query[:50]}...")
        
        # ✅ FIX: Limit context size to prevent safety blocks
        MAX_CONTEXT_LENGTH = 2000  # Reduced from unlimited
        if len(context) > MAX_CONTEXT_LENGTH:
            context = context[:MAX_CONTEXT_LENGTH] + "\n\n[Context truncated for safety]"
            logger.warning(f"⚠️ Context truncated from {len(context)} to {MAX_CONTEXT_LENGTH} chars")
        
        # Step 2: Build enhanced prompt with safety measures
        prompt = f"""You are a helpful data analyst assistant. Answer the user's question based on the provided data context.

USER QUESTION: {query}

DATA CONTEXT:
{context}

INSTRUCTIONS:
- Answer based ONLY on the data provided above
- Include specific numbers and statistics when relevant
- If the data doesn't contain information to answer the question, say so clearly
- Be concise but informative
- Format numbers with commas for readability

ANSWER:"""
        
        # Step 3: Generate response with safety settings
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # # ✅ FIX: Add safety settings to prevent blocks
        # safety_settings = {
        #     'HARASSMENT': 'BLOCK_NONE',
        #     'HATE_SPEECH': 'BLOCK_NONE',
        #     'SEXUALLY_EXPLICIT': 'BLOCK_NONE',
        #     'DANGEROUS_CONTENT': 'BLOCK_NONE'
        # }
        
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 1024
            }
        )
        
        # ✅ FIX: Check if response was blocked before accessing .text
        if not response.candidates:
            logger.error("❌ Gemini API blocked the response")
            return {
                'response': "⚠️ The AI response was blocked due to safety filters. Please try rephrasing your question or contact support.",
                'sources': [],
                'context_used': False,
                'error': 'blocked_by_safety_filters'
            }
        
        # ✅ FIX: Check for safety ratings
        candidate = response.candidates[0]
        if hasattr(candidate, 'finish_reason'):
            if candidate.finish_reason.name == 'SAFETY':
                logger.error(f"❌ Response blocked by safety: {candidate.safety_ratings}")
                return {
                    'response': "⚠️ Your question triggered content safety filters. Please try asking in a different way.",
                    'sources': [],
                    'context_used': False,
                    'error': 'safety_block'
                }
        
        # ✅ FIX: Safely extract text
        try:
            response_text = response.text
        except Exception as e:
            logger.error(f"❌ Failed to extract response.text: {e}")
            return {
                'response': f"⚠️ AI response error: {str(e)}. Please try a simpler question.",
                'sources': [],
                'context_used': False,
                'error': 'extraction_failed'
            }
        
        logger.info(f"✅ Generated response ({len(response_text)} chars)")
        
        return {
            'response': response_text,
            'sources': ['uploaded_data'],
            'context_used': True,
            'context_length': len(context)
        }
        
    except Exception as e:
        logger.error(f"❌ RAG query error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'response': f"❌ Error: {str(e)}\n\nPlease check:\n1. GEMINI_API_KEY is set correctly\n2. You have internet connection\n3. Data has been uploaded",
            'sources': [],
            'context_used': False,
            'error': str(e)
        }

# ============================================================================
# COLUMN MAPPING FUNCTIONS
# ============================================================================
def suggest_column_mapping(columns: List[str], file_type: str, sample_data: Optional[pd.DataFrame] = None) -> Dict[str, str]:
    """AI → Fallback mapping. No nulls. Only valid standard fields."""
    if not GEMINI_API_KEY:
        return _fallback_mapping(columns, file_type, sample_data)

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        std = _standard_fields(file_type)
        all_fields = std["required"] + std["optional"]

        prompt = _build_prompt(columns, file_type, std, sample_data)
        resp = model.generate_content(prompt, generation_config={"temperature": 0.0, "max_output_tokens": 4096})
        json_text = _extract_json(resp.text)
        ai_map = json.loads(json_text)

        # Validate + fill gaps with fallback
        final = {}
        for col in columns:
            field = ai_map.get(col)
            final[col] = field if field in all_fields else _best_match(col, all_fields, sample_data)
        return final

    except Exception as e:
        print(f"AI failed ({e}), using fallback")
        return _fallback_mapping(columns, file_type, sample_data)


def _standard_fields(file_type: str) -> dict:
    buyers = {
        "required": ["email", "name", "order_date", "revenue"],
        "optional": [
            "product", "quantity", "customer_id", "phone", "address", "city", "state", "country",
            "zip_code", "payment_method", "order_id", "status", "discount", "tax", "shipping_cost",
            "net_worth", "income", "age_range", "gender", "company_name", "company_revenue",
            "job_title", "department", "seniority_level"
        ]
    }
    visitors = {
        "required": ["email", "visit_date"],
        "optional": [
            "source", "campaign", "device", "page_url", "session_id", "referrer",
            "utm_source", "utm_medium", "utm_campaign", "browser", "os", "ip_address",
            "location", "duration", "event_type", "pixel_id", "uuid", "user_agent"
        ]
    }
    return buyers if file_type == "buyers" else visitors


def _build_prompt(columns: List[str], file_type: str, std: dict, sample: Optional[pd.DataFrame]) -> str:
    all_f = std["required"] + std["optional"]
    prompt = f"""Map CSV columns to standard fields. File type: **{file_type}**.

Columns: {columns}

Standard fields (required): {std['required']}
Standard fields (optional): {std['optional']}

Rules:
- Map by **meaning**, not exact name.
- Multiple columns → same field is allowed.
- **Never return null** – always pick a valid field.
- Use sample data to infer content.

"""
    if sample is not None and not sample.empty:
        prompt += "Sample rows (first 3):\n"
        for col in columns[:12]:
            if col in sample.columns:
                vals = sample[col].head(3).astype(str).tolist()
                vals = [v[:70] + "…" if len(v) > 70 else v for v in vals]
                prompt += f"{col}: {vals}\n"

    prompt += f"\nReturn **only JSON** mapping **all {len(columns)}** columns:\n{{ \"COL\": \"field\", ... }}\n"
    return prompt


def _extract_json(text: str) -> str:
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()


def _fallback_mapping(columns: List[str], file_type: str, sample: Optional[pd.DataFrame]) -> Dict[str, str]:
    std = _standard_fields(file_type)
    all_fields = std["required"] + std["optional"]
    return {col: _best_match(col, all_fields, sample) for col in columns}


def _best_match(col: str, fields: List[str], sample: Optional[pd.DataFrame]) -> str:
    """Semantic + fuzzy + content → always returns a field."""
    clean = re.sub(r'[^a-z0-9]', '', col.lower())

    # 1. Fuzzy similarity
    best_score, best = 0, fields[0]
    for f in fields:
        f_clean = re.sub(r'[^a-z0-9]', '', f.lower())
        score = SequenceMatcher(None, clean, f_clean).ratio()
        if score > best_score:
            best_score, best = score, f
        if score > 0.82:
            return f

    # 2. Content inference
    if sample is not None and col in sample.columns:
        inferred = _infer_content(sample[col], fields)
        if inferred:
            return inferred

    # 3. Keyword boost
    boosts = {
        "email": ["email", "mail", "sha256", "hem"],
        "phone": ["phone", "mobile", "cell", "number", "direct", "wireless", "landline"],
        "name": ["name", "first", "last", "full"],
        "address": ["address", "street", "addr"],
        "city": ["city", "town"],
        "state": ["state", "province"],
        "zip_code": ["zip", "postal", "postcode"],
        "revenue": ["revenue", "worth", "income", "amount", "price"],
        "company_name": ["company", "business", "org"],
        "job_title": ["job", "title", "role", "position"],
        "age_range": ["age", "dob"],
        "gender": ["gender", "sex"],
        "net_worth": ["net", "worth"],
        "income": ["income", "salary"],
    }
    for field, kws in boosts.items():
        if field in fields and any(k in clean for k in kws):
            return field

    return best


def _infer_content(series: pd.Series, fields: List[str]) -> Optional[str]:
    vals = series.dropna().head(5)
    if vals.empty:
        return None
    text = " ".join(str(v) for v in vals.tolist()).lower()

    if "@" in text and "email" in fields:
        return "email"
    if re.search(r"\+\d|\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", text) and "phone" in fields:
        return "phone"
    if re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", text):
        return "order_date" if "order_date" in fields else "visit_date"
    if re.search(r"\$|\d+k|\d+m", text) and "revenue" in fields:
        return "revenue"
    if "http" in text or "www." in text:
        return "page_url" if "page_url" in fields else "referrer"
    return None


# ============================================================================
# GENERAL AI QUERY FUNCTION
# ============================================================================
def query_ai_assistant(query: str, context: Optional[Dict] = None) -> str:
    """
    Handle general AI queries with optional context
    
    Args:
        query: User's question
        context: Optional dictionary with context data (total_orders, total_revenue, etc.)
    
    Returns:
        String response from the AI
    """
    if not GEMINI_API_KEY:
        return "⚠️ AI assistant is not configured. Please set GEMINI_API_KEY in .env file."
    
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Build prompt with context
        prompt = f"User question: {query}\n\n"
        
        if context:
            prompt += "Context:\n"
            if 'total_orders' in context:
                prompt += f"- Total orders: {context['total_orders']}\n"
            if 'total_revenue' in context:
                prompt += f"- Total revenue: ${context['total_revenue']:,.2f}\n"
            if 'unique_customers' in context:
                prompt += f"- Unique customers: {context['unique_customers']}\n"
            if 'total_visitors' in context:
                prompt += f"- Total visitors: {context['total_visitors']}\n"
            prompt += "\n"
        
        prompt += "Please provide a helpful, concise answer. If analyzing data, include specific numbers."
        
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 1024
            }
        )
        
        return response.text
        
    except Exception as e:
        return f"❌ Error: {str(e)}\n\nPlease check:\n1. GEMINI_API_KEY is set correctly\n2. You have internet connection\n3. API quota is not exceeded"


# ============================================================================
# QUICK TEST
# ============================================================================
if __name__ == "__main__":
    # Paste your sample data as DataFrame
    data = json.loads(open("sample.json").read())["sample_data"]
    df = pd.DataFrame(data)
    cols = json.loads(open("sample.json").read())["columns"]

    mapping = suggest_column_mapping(cols, "buyers", df)
    print(json.dumps(mapping, indent=2))