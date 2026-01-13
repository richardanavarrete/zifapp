import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import StringIO
import re
from datetime import datetime

# Set page config
st.set_page_config(page_title="ZIF Usage Dashboard", layout="wide")

# Title
st.title("🍕 ZIF Usage Dashboard")

# Initialize session state for file uploads
if 'zif_file' not in st.session_state:
    st.session_state.zif_file = None
if 'sales_mix_file' not in st.session_state:
    st.session_state.sales_mix_file = None

def parse_zif_csv(uploaded_file):
    """Parse ZIF CSV file and return DataFrame"""
    try:
        # Read the CSV file
        content = uploaded_file.getvalue().decode('utf-8')
        df = pd.read_csv(StringIO(content))
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        st.error(f"Error parsing ZIF file: {e}")
        return None

def parse_sales_mix_csv(uploaded_file):
    """Parse Sales Mix CSV file and return DataFrame"""
    try:
        # Read the CSV file
        content = uploaded_file.getvalue().decode('utf-8')
        df = pd.read_csv(StringIO(content))
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        st.error(f"Error parsing Sales Mix file: {e}")
        return None

def extract_item_number(menu_item):
    """Extract item number from menu item string"""
    if pd.isna(menu_item):
        return None
    # Look for pattern like "14 inch" or "12 inch" at the start
    match = re.search(r'^(\d+)\s*inch', str(menu_item), re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def aggregate_usage(df):
    """Aggregate usage by dough type"""
    usage = {}
    
    for _, row in df.iterrows():
        menu_item = row.get('Menu Item', '')
        quantity = row.get('Quantity', 0)
        
        if pd.isna(menu_item) or pd.isna(quantity):
            continue
            
        # Extract size from menu item
        size = extract_item_number(menu_item)
        if size:
            if size not in usage:
                usage[size] = 0
            usage[size] += float(quantity)
    
    return usage

def aggregate_all_usage(df):
    """Aggregate usage for all dough types"""
    dough_usage = {}
    gluten_free_usage = {}
    cauliflower_usage = {}
    
    for _, row in df.iterrows():
        menu_item = str(row.get('Menu Item', '')).lower()
        quantity = row.get('Quantity', 0)
        
        if pd.isna(quantity):
            continue
        
        quantity = float(quantity)
        
        # Extract size
        size = extract_item_number(row.get('Menu Item', ''))
        
        if size:
            # Check for gluten free
            if 'gluten free' in menu_item or 'gf' in menu_item:
                if size not in gluten_free_usage:
                    gluten_free_usage[size] = 0
                gluten_free_usage[size] += quantity
            # Check for cauliflower
            elif 'cauliflower' in menu_item or 'cauli' in menu_item:
                if size not in cauliflower_usage:
                    cauliflower_usage[size] = 0
                cauliflower_usage[size] += quantity
            # Regular dough
            else:
                if size not in dough_usage:
                    dough_usage[size] = 0
                dough_usage[size] += quantity
    
    return dough_usage, gluten_free_usage, cauliflower_usage

def create_usage_chart(usage_dict, title):
    """Create a bar chart for usage data"""
    if not usage_dict:
        return None
    
    # Sort by size
    sizes = sorted(usage_dict.keys(), key=lambda x: int(x))
    quantities = [usage_dict[size] for size in sizes]
    
    fig = go.Figure(data=[
        go.Bar(
            x=[f"{size} inch" for size in sizes],
            y=quantities,
            text=quantities,
            textposition='auto',
            marker_color='#FF6B6B'
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Size",
        yaxis_title="Quantity",
        height=400,
        showlegend=False
    )
    
    return fig

def create_comparison_chart(zif_usage, sales_mix_usage, title):
    """Create a grouped bar chart comparing ZIF and Sales Mix data"""
    if not zif_usage and not sales_mix_usage:
        return None
    
    # Get all sizes from both datasets
    all_sizes = sorted(set(list(zif_usage.keys()) + list(sales_mix_usage.keys())), 
                       key=lambda x: int(x))
    
    zif_quantities = [zif_usage.get(size, 0) for size in all_sizes]
    sales_quantities = [sales_mix_usage.get(size, 0) for size in all_sizes]
    
    fig = go.Figure(data=[
        go.Bar(name='ZIF Usage', x=[f"{size} inch" for size in all_sizes], 
               y=zif_quantities, marker_color='#FF6B6B'),
        go.Bar(name='Sales Mix', x=[f"{size} inch" for size in all_sizes], 
               y=sales_quantities, marker_color='#4ECDC4')
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Size",
        yaxis_title="Quantity",
        barmode='group',
        height=400
    )
    
    return fig

def create_variance_chart(zif_usage, sales_mix_usage, title):
    """Create a chart showing variance between ZIF and Sales Mix"""
    if not zif_usage and not sales_mix_usage:
        return None
    
    # Get all sizes from both datasets
    all_sizes = sorted(set(list(zif_usage.keys()) + list(sales_mix_usage.keys())), 
                       key=lambda x: int(x))
    
    variances = []
    for size in all_sizes:
        zif_qty = zif_usage.get(size, 0)
        sales_qty = sales_mix_usage.get(size, 0)
        variance = sales_qty - zif_qty
        variances.append(variance)
    
    # Color code: red for negative (under), green for positive (over)
    colors = ['red' if v < 0 else 'green' for v in variances]
    
    fig = go.Figure(data=[
        go.Bar(
            x=[f"{size} inch" for size in all_sizes],
            y=variances,
            marker_color=colors,
            text=variances,
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Size",
        yaxis_title="Variance (Sales - ZIF)",
        height=400,
        showlegend=False
    )
    
    return fig

# File upload section
st.header("📁 Upload Files")

col1, col2 = st.columns(2)

with col1:
    zif_upload = st.file_uploader("Upload ZIF CSV", type=['csv'], key='zif_uploader')
    if zif_upload is not None:
        st.session_state.zif_file = zif_upload
        st.success("✅ ZIF file uploaded successfully!")

with col2:
    sales_mix_upload = st.file_uploader("Upload Sales Mix CSV", type=['csv'], key='sales_mix_uploader')
    if sales_mix_upload is not None:
        st.session_state.sales_mix_file = sales_mix_upload
        st.success("✅ Sales Mix file uploaded successfully!")

# Display data and charts
if st.session_state.zif_file is not None or st.session_state.sales_mix_file is not None:
    st.header("📊 Usage Analysis")
    
    # Parse ZIF data
    zif_dough_usage = {}
    zif_gf_usage = {}
    zif_cauli_usage = {}
    
    if st.session_state.zif_file is not None:
        try:
            # Reset file pointer to beginning before reading
            st.session_state.zif_file.seek(0)
            zif_df = parse_zif_csv(st.session_state.zif_file)
            if zif_df is not None and not zif_df.empty:
                # Show raw data preview
                with st.expander("📋 View ZIF Raw Data"):
                    st.dataframe(zif_df)
                
                # Aggregate usage
                zif_dough_usage, zif_gf_usage, zif_cauli_usage = aggregate_all_usage(zif_df)
        except Exception as e:
            st.warning(f"⚠️ Could not parse ZIF file: {e}")
    
    # Parse Sales Mix data
    sales_mix_usage = None
    if st.session_state.sales_mix_file is not None:
        try:
            # Reset file pointer to beginning before reading
            st.session_state.sales_mix_file.seek(0)
            sales_df = parse_sales_mix_csv(st.session_state.sales_mix_file)
            if sales_df is not None and not sales_df.empty:
                sales_mix_usage, _, _ = aggregate_all_usage(sales_df)
        except Exception as e:
            st.warning(f"⚠️ Could not parse sales mix file: {e}")
    
    # Display charts in tabs
    if zif_dough_usage or zif_gf_usage or zif_cauli_usage or sales_mix_usage:
        tab1, tab2, tab3, tab4 = st.tabs(["Regular Dough", "Gluten Free", "Cauliflower", "Comparison"])
        
        with tab1:
            st.subheader("Regular Dough Usage")
            if zif_dough_usage and sales_mix_usage:
                # Show comparison
                col1, col2 = st.columns(2)
                with col1:
                    fig_zif = create_usage_chart(zif_dough_usage, "ZIF Regular Dough Usage")
                    if fig_zif:
                        st.plotly_chart(fig_zif, use_container_width=True)
                
                with col2:
                    fig_sales = create_usage_chart(sales_mix_usage, "Sales Mix Regular Dough Usage")
                    if fig_sales:
                        st.plotly_chart(fig_sales, use_container_width=True)
                
                # Show side-by-side comparison
                fig_comp = create_comparison_chart(zif_dough_usage, sales_mix_usage, 
                                                   "Regular Dough: ZIF vs Sales Mix")
                if fig_comp:
                    st.plotly_chart(fig_comp, use_container_width=True)
                
                # Show variance
                fig_var = create_variance_chart(zif_dough_usage, sales_mix_usage,
                                               "Regular Dough Variance (Sales - ZIF)")
                if fig_var:
                    st.plotly_chart(fig_var, use_container_width=True)
            elif zif_dough_usage:
                fig = create_usage_chart(zif_dough_usage, "Regular Dough Usage")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No regular dough usage data available")
        
        with tab2:
            st.subheader("Gluten Free Dough Usage")
            if zif_gf_usage:
                fig = create_usage_chart(zif_gf_usage, "Gluten Free Dough Usage")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No gluten free dough usage data available")
        
        with tab3:
            st.subheader("Cauliflower Dough Usage")
            if zif_cauli_usage:
                fig = create_usage_chart(zif_cauli_usage, "Cauliflower Dough Usage")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No cauliflower dough usage data available")
        
        with tab4:
            st.subheader("Overall Comparison")
            if zif_dough_usage and sales_mix_usage:
                # Create summary table
                all_sizes = sorted(set(list(zif_dough_usage.keys()) + list(sales_mix_usage.keys())), 
                                 key=lambda x: int(x))
                
                summary_data = []
                for size in all_sizes:
                    zif_qty = zif_dough_usage.get(size, 0)
                    sales_qty = sales_mix_usage.get(size, 0)
                    variance = sales_qty - zif_qty
                    variance_pct = (variance / zif_qty * 100) if zif_qty > 0 else 0
                    
                    summary_data.append({
                        'Size': f"{size} inch",
                        'ZIF Usage': zif_qty,
                        'Sales Mix': sales_qty,
                        'Variance': variance,
                        'Variance %': f"{variance_pct:.1f}%"
                    })
                
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True)
            else:
                st.info("Upload both ZIF and Sales Mix files to see comparison")

# Footer
st.markdown("---")
st.markdown("*Upload your ZIF and Sales Mix CSV files to analyze dough usage*")
