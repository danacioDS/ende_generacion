import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pathlib import Path

# Configuración de la página
st.set_page_config(page_title="Dashboard de Potencia", layout="wide")
st.title("Análisis Integral de Potencia por Tecnología")

# 1. Optimización de carga de datos con manejo de nombres de columnas
@st.cache_data
def load_and_transform_data():
    try:
        # Ruta optimizada usando Path
        current_dir = Path(__file__).parent
        file_path = current_dir.parent / "data" / "serie_potencia.xlsx"
        
        # Validación de ruta
        if not file_path.exists():
            st.error(f"Archivo no encontrado: {file_path}")
            return None
            
        # Leer todo el archivo para inspeccionar columnas
        df_full = pd.read_excel(file_path, engine="openpyxl", nrows=1)
        available_columns = df_full.columns.tolist()
        
        # Buscar columna de tecnología (manejar diferentes nombres)
        tech_col = None
        possible_names = ['TECNOLOGÍA', 'TECNOLOGIA', 'TECNOLOGÍA', 'TIPO', 'TECNOLOGIA', 'TEC']
        for name in possible_names:
            if name in available_columns:
                tech_col = name
                break
        
        if not tech_col:
            st.error(f"No se encontró columna de tecnología. Columnas disponibles: {available_columns}")
            return None
            
        # Leer solo columnas necesarias usando el nombre encontrado
        df = pd.read_excel(file_path, engine="openpyxl", 
                          usecols=lambda x: "Potencia kW" in x or x in ['CENTRAL', tech_col])
        
        if df.empty:
            st.error("El archivo está vacío")
            return None

        # 2. Transformación vectorizada
        df.columns = df.columns.str.strip()
        energy_cols = [col for col in df.columns if "Potencia kW" in col]

        # Renombrar columna de tecnología a nombre consistente
        df = df.rename(columns={tech_col: 'TECNOLOGIA'})
        
        # Crear mapeo de fechas optimizado
        date_mapping = {}
        current_date = datetime(2023, 1, 1)
        while current_date <= datetime(2025, 12, 1):
            key = current_date.strftime('%m%Y')
            date_mapping[key] = current_date.strftime('%Y-%m-01')
            # Avanzar al siguiente mes
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        # Transformación con melt
        melted = df.melt(
            id_vars=['CENTRAL', 'TECNOLOGIA'],
            value_vars=energy_cols,
            var_name='Periodo',
            value_name='Potencia kW'
        )
        
        # Extraer periodo y mapear fecha
        melted['Periodo'] = melted['Periodo'].str.split().str[-1]
        melted['FECHA'] = melted['Periodo'].apply(
            lambda x: date_mapping.get(x[:2] + x[2:], pd.NaT)
        )
        
        # Filtrar y convertir fechas
        melted = melted[melted['FECHA'].notna()]
        melted['FECHA'] = pd.to_datetime(melted['FECHA'])
        
        return melted

    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return None

# Cargar datos
df = load_and_transform_data()
if df is None:
    st.stop()

# 3. Filtros optimizados
st.sidebar.title("Filtros y Configuración")

# Manejo de fechas
if not df.empty:
    min_date = df['FECHA'].min().to_pydatetime()
    max_date = df['FECHA'].max().to_pydatetime()
    
    selected_range = st.sidebar.slider(
        "Rango de fechas",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="YYYY-MM"
    )
    
    # Filtrar DataFrame
    mask = (df['FECHA'] >= pd.Timestamp(selected_range[0])) & (df['FECHA'] <= pd.Timestamp(selected_range[1]))
    df_filtered = df[mask].copy()
else:
    df_filtered = df
    st.warning("No hay datos disponibles para filtrar")

# 4. Pre-cálculos globales
total_potencia_sistema = df_filtered['Potencia kW'].sum()
tecnologias = df_filtered['TECNOLOGIA'].unique().tolist()

# Selección de tecnología
selected_tecnologia = st.sidebar.selectbox("Seleccionar Tecnología", tecnologias)
centrales_disponibles = df_filtered[df_filtered['TECNOLOGIA'] == selected_tecnologia]['CENTRAL'].unique().tolist()
selected_central = st.sidebar.selectbox("Seleccionar Central", centrales_disponibles)

# Layout principal
tab1, tab2 = st.tabs(["Visión Detallada", "Visión de Promedios"])

# 5. Funciones para gráficos
def plot_central_energy(df_central, central_name):
    """Crea gráfico de evolución para una central"""
    if df_central.empty:
        return None
    
    fig = px.line(
        df_central,
        x='FECHA',
        y='Potencia kW',
        title=f"Potencia para {central_name}",
        markers=True
    )
    fig.update_traces(
        line=dict(width=3, color='#1f77b4'),
        marker=dict(size=8, symbol='circle', color='#1f77b4')
    )
    fig.update_layout(
        yaxis_title="Potencia (kW)", 
        xaxis_title="Fecha", 
        showlegend=False,
        template='plotly_white'
    )
    return fig

def plot_tecnologia_energy(df_tecnologia, tecnologia_name):
    """Crea gráfico de evolución para una tecnología"""
    if df_tecnologia.empty:
        return None
    
    # Agrupar por fecha
    df_grouped = df_tecnologia.groupby('FECHA', as_index=False)['Potencia kW'].sum()

    fig = px.line(
        df_grouped,
        x='FECHA',
        y='Potencia kW',
        title=f"Potencia para {tecnologia_name}",
        markers=True
    )
    fig.update_traces(
        line=dict(width=3, color='#d62728'),
        marker=dict(size=8, symbol='diamond', color='#d62728')
    )
    fig.update_layout(
        yaxis_title="Potencia (kW)", 
        xaxis_title="Fecha", 
        showlegend=False,
        template='plotly_white'
    )
    return fig

# 6. Contenido para pestañas
with tab1:
    col_left, col_right = st.columns(2)
    
    # Columna izquierda - Central
    with col_left:
        st.subheader(f"Evolución de la Central: {selected_central}")
        df_central = df_filtered[df_filtered['CENTRAL'] == selected_central]
        
        if not df_central.empty:
            # Gráfico
            fig_central = plot_central_energy(df_central, selected_central)
            st.plotly_chart(fig_central, use_container_width=True)
            
            # Métricas optimizadas
            potencia_total_central = df_central['Potencia kW'].sum()
            potencia_promedio_central = df_central['Potencia kW'].mean()
            porcentaje_central = (potencia_total_central / total_potencia_sistema) * 100
            
            col1, col2 = st.columns(2)
            col1.metric("Potencia Promedio", f"{potencia_promedio_central:,.2f} kW")
            col2.metric("Participación", f"{porcentaje_central:.2f}%")
        else:
            st.warning(f"No hay datos para: {selected_central}")
    
    # Columna derecha - Tecnología
    with col_right:
        st.subheader(f"Evolución de la Tecnología: {selected_tecnologia}")
        df_tecnologia = df_filtered[df_filtered['TECNOLOGIA'] == selected_tecnologia]
        
        if not df_tecnologia.empty:
            # Gráfico
            fig_tecnologia = plot_tecnologia_energy(df_tecnologia, selected_tecnologia)
            st.plotly_chart(fig_tecnologia, use_container_width=True)
            
            # Métricas optimizadas
            potencia_total_tecnologia = df_tecnologia['Potencia kW'].sum()
            potencia_promedio_tecnologia = df_tecnologia.groupby('FECHA')['Potencia kW'].sum().mean()
            porcentaje_tecnologia = (potencia_total_tecnologia / total_potencia_sistema) * 100
            
            col1, col2 = st.columns(2)
            col1.metric("Potencia Promedio", f"{potencia_promedio_tecnologia:,.2f} kW")
            col2.metric("Participación", f"{porcentaje_tecnologia:.2f}%")
        else:
            st.warning(f"No hay datos para: {selected_tecnologia}")
    
    # Gráfico del sistema
    st.subheader("Evolución del Sistema")

    if not df_filtered.empty:
        df_sistema = df_filtered.groupby('FECHA')['Potencia kW'].sum().reset_index()
        df_sistema['Potencia kW'] = df_sistema['Potencia kW'].round(2)
        potencia_promedio_sistema = df_sistema['Potencia kW'].mean()

        fig_sistema = px.bar(
            df_sistema,
            x='FECHA',
            y='Potencia kW',
            color='Potencia kW',
            color_continuous_scale='cividis',
            title="Evolución de la Potencia del Sistema",
            text_auto=True
        )
        
        fig_sistema.update_traces(
            textposition='inside',
            textfont=dict(size=16, color='white'))
        
        fig_sistema.update_layout(
            yaxis_title="Potencia kW", 
            xaxis_title="Fecha", 
            showlegend=False, 
            bargap=0.2
        )
        st.plotly_chart(fig_sistema, use_container_width=True)

        st.metric(label="Potencia Promedio del Sistema", value=f"{potencia_promedio_sistema:,.2f} kW")
    else:
        st.warning("No hay datos disponibles para mostrar la evolución del sistema")
    
    # Participación por tecnología
    st.subheader("Participación por Tecnología")
    if not df_filtered.empty:
        participacion = (
            df_filtered.groupby('TECNOLOGIA', as_index=False)['Potencia kW']
            .sum()
            .assign(Porcentaje=lambda x: (x['Potencia kW'] / total_potencia_sistema) * 100)
            .sort_values('Porcentaje', ascending=False)
        )
        
        fig_bar = px.bar(
            participacion,
            x='Porcentaje',
            y='TECNOLOGIA',
            orientation='h',
            color='Porcentaje',
            color_continuous_scale='Greens',
            text='Porcentaje',
            labels={'Porcentaje': 'Participación (%)', 'TECNOLOGIA': ''}
        )
        
        fig_bar.update_traces(
            texttemplate='%{x:.2f}%',
            textposition='outside',
            marker_line=dict(color='#000', width=0.5)
        )
        
        fig_bar.update_layout(
            height=600,
            xaxis_range=[0, participacion['Porcentaje'].max() * 1.15],
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("Datos insuficientes para participación")

# 7. Pestaña de comparación
with tab2:
    st.header("Análisis Comparativo")
    
    if not df_filtered.empty:
        # Gráfico comparativo de tecnologías
        st.subheader("Comparación entre Tecnologías")
        
        df_comparacion = (
            df_filtered.groupby(['FECHA', 'TECNOLOGIA'], as_index=False)
            ['Potencia kW'].sum()
        )
        
        fig_comparativo = px.line(
            df_comparacion,
            x='FECHA',
            y='Potencia kW',
            color='TECNOLOGIA',
            markers=True,
            line_shape='spline',
            title="Comparación de Potencia por Tecnología"
        )
        
        fig_comparativo.update_layout(
            yaxis_title="Potencia (kW)",
            xaxis_title="Fecha",
            legend_title="Tecnologías",
            height=500
        )
        st.plotly_chart(fig_comparativo, use_container_width=True)
        
        # Tabla de resumen
        st.subheader("Resumen Estadístico por Tecnología")

        total_por_mes = df_filtered.groupby('FECHA', as_index=False, sort=False)['Potencia kW'].sum()
        total_por_mes = total_por_mes.rename(columns={'Potencia kW': 'Total_Sistema'})

        tecnologia_por_mes = df_filtered.groupby(['FECHA', 'TECNOLOGIA'], as_index=False)['Potencia kW'].sum()

        df_participacion = pd.merge(tecnologia_por_mes, total_por_mes, on='FECHA')
        df_participacion['Participacion'] = (df_participacion['Potencia kW'] / df_participacion['Total_Sistema']) * 100

        stats = (
            df_participacion.groupby('TECNOLOGIA', as_index=False)
            .agg(
                Minimo=('Potencia kW', 'min'),
                Promedio=('Potencia kW', 'mean'),
                Maximo=('Potencia kW', 'max'),
                Participacion_Promedio=('Participacion', 'mean')
            )
        )

        stats = stats.sort_values(by='Participacion_Promedio', ascending=False)

        stats = stats.rename(columns={
            'TECNOLOGÍA': 'Tecnología',
            'Minimo': 'Mínimo (kW)',
            'Promedio': 'Promedio (kW)',
            'Maximo': 'Máximo (kW)',
            'Participacion_Promedio': 'Participación Promedio (%)'
        })

        stats['Mínimo (kW)'] = stats['Mínimo (kW)'].apply(lambda x: f"{x:,.2f}")
        stats['Promedio (kW)'] = stats['Promedio (kW)'].apply(lambda x: f"{x:,.2f}")
        stats['Máximo (kW)'] = stats['Máximo (kW)'].apply(lambda x: f"{x:,.2f}")
        stats['Participación Promedio (%)'] = stats['Participación Promedio (%)'].apply(lambda x: f"{x:.2f}%")

        st.dataframe(stats)

# 8. Panel informativo
st.sidebar.markdown("---")
st.sidebar.subheader("Métricas del Sistema")
if not df_filtered.empty:
    st.sidebar.metric("Centrales", df_filtered['CENTRAL'].nunique())
    st.sidebar.metric("Tecnologías", len(tecnologias))
    st.sidebar.metric("Potencia Total", f"{total_potencia_sistema:,.2f} kW")
    st.sidebar.caption(f"Periodo: {df_filtered['FECHA'].min().strftime('%Y-%m')} a {df_filtered['FECHA'].max().strftime('%Y-%m')}")
else:
    st.sidebar.warning("Sin datos para mostrar métricas")