import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from pathlib import Path

# Configuración de la página
st.set_page_config(page_title="Dashboard de Energía", layout="wide")
st.title("Análisis Integral de Energía")

# 1. Optimización de carga de datos
@st.cache_data
def load_and_transform_data():
    try:
        # Ruta optimizada usando Path
        current_dir = Path(__file__).parent
        file_path = current_dir.parent / "data" / "serie_energia.xlsx"
        
        # Validación de ruta
        if not file_path.exists():
            st.error(f"Archivo no encontrado: {file_path}")
            return None
            
        # Leer solo columnas necesarias
        df = pd.read_excel(file_path, engine="openpyxl", 
                          usecols=lambda x: "Energía kWh" in x or x in ['CENTRAL', 'GENERADOR'])
        
        if df.empty:
            st.error("El archivo está vacío")
            return None

        # 2. Transformación vectorizada
        df.columns = df.columns.str.strip()
        energy_cols = [col for col in df.columns if "Energía kWh" in col]
        
        # Crear mapeo de fechas optimizado
        date_mapping = {}
        current_date = datetime(2023, 1, 1)
        while current_date <= datetime(2025, 12, 1):
            key = current_date.strftime('%m%Y')
            date_mapping[key] = current_date.strftime('%Y-%m-01')
            current_date = current_date.replace(month=current_date.month + 1) if current_date.month < 12 else current_date.replace(year=current_date.year + 1, month=1)

        # Transformación con melt
        melted = df.melt(
            id_vars=['CENTRAL', 'GENERADOR'],
            value_vars=energy_cols,
            var_name='Periodo',
            value_name='Energía kWh'
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
total_energia_sistema = df_filtered['Energía kWh'].sum()
generadores = df_filtered['GENERADOR'].unique().tolist()

# Selección de generador
selected_generador = st.sidebar.selectbox("Seleccionar Generador", generadores)
centrales_disponibles = df_filtered[df_filtered['GENERADOR'] == selected_generador]['CENTRAL'].unique().tolist()
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
        y='Energía kWh',
        title=f"Energía para {central_name}",
        markers=True
    )
    fig.update_traces(
        line=dict(width=3, color='#1f77b4'),
        marker=dict(size=8, symbol='circle', color='#1f77b4')
    )
    fig.update_layout(
        yaxis_title="Energía (kWh)", 
        xaxis_title="Fecha", 
        showlegend=False,
        template='plotly_white'
    )
    return fig

def plot_generador_energy(df_generador, generador_name):
    """Crea gráfico de evolución para un generador"""
    if df_generador.empty:
        return None
    
    # Agrupar por fecha
    df_grouped = df_generador.groupby('FECHA', as_index=False)['Energía kWh'].sum()
    
    fig = px.line(
        df_grouped,
        x='FECHA',
        y='Energía kWh',
        title=f"Energía para {generador_name}",
        markers=True
    )
    fig.update_traces(
        line=dict(width=3, color='#d62728'),
        marker=dict(size=8, symbol='diamond', color='#d62728')
    )
    fig.update_layout(
        yaxis_title="Energía (kWh)", 
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
            energia_total_central = df_central['Energía kWh'].sum()
            energia_promedio_central = df_central['Energía kWh'].mean()
            porcentaje_central = (energia_total_central / total_energia_sistema) * 100
            
            col1, col2 = st.columns(2)
            col1.metric("Energía Promedio", f"{energia_promedio_central:,.2f} kWh")
            col2.metric("Participación", f"{porcentaje_central:.2f}%")
        else:
            st.warning(f"No hay datos para: {selected_central}")
    
    # Columna derecha - Generador
    with col_right:
        st.subheader(f"Evolución del Generador: {selected_generador}")
        df_generador = df_filtered[df_filtered['GENERADOR'] == selected_generador]
        
        if not df_generador.empty:
            # Gráfico
            fig_generador = plot_generador_energy(df_generador, selected_generador)
            st.plotly_chart(fig_generador, use_container_width=True)
            
            # Métricas optimizadas
            energia_total_generador = df_generador['Energía kWh'].sum()
            energia_promedio_generador = df_generador.groupby('FECHA')['Energía kWh'].sum().mean()
            porcentaje_generador = (energia_total_generador / total_energia_sistema) * 100
            
            col1, col2 = st.columns(2)
            col1.metric("Energía Promedio", f"{energia_promedio_generador:,.2f} kWh")
            col2.metric("Participación", f"{porcentaje_generador:.2f}%")
        else:
            st.warning(f"No hay datos para: {selected_generador}")
    
    # Gráfico del sistema - ÁREA HORIZONTAL MANTENIDA
    st.subheader("Evolución del Sistema")

    # Evolución del sistema
    if not df_filtered.empty:
        st.subheader("Evolución de la Energía Móvil del Sistema")
        df_sistema = df_filtered.groupby('FECHA')['Energía kWh'].sum().reset_index()
        df_sistema['Energía kWh'] = df_sistema['Energía kWh'].round(2)
        energia_promedio_sistema = df_sistema['Energía kWh'].mean()

        fig_sistema = px.bar(
            df_sistema,
            x='FECHA',
            y='Energía kWh',
            color='Energía kWh',  # blues Mapea valores a colores
            color_continuous_scale='Viridis',  # Escala de colores
            title="Evolución de la Energía Móvil del Sistema",
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

        st.metric(label="Energía Promedio del Sistema", value=f"{energia_promedio_sistema:,.2f} kWh")
    else:
        st.warning("No hay datos disponibles para mostrar la evolución del sistema")
    
    
    # Participación por generador (barras horizontales)
    st.subheader("Participación por Generador")
    if not df_filtered.empty:
        # Cálculo optimizado
        participacion = (
            df_filtered.groupby('GENERADOR', as_index=False)['Energía kWh']
            .sum()
            .assign(Porcentaje=lambda x: (x['Energía kWh'] / total_energia_sistema) * 100)
            .sort_values('Porcentaje', ascending=False)
        )
        
        fig_bar = px.bar(
            participacion,
            x='Porcentaje',
            y='GENERADOR',
            orientation='h',
            color='Porcentaje',
            color_continuous_scale='Blues',
            text='Porcentaje',
            labels={'Porcentaje': 'Participación (%)', 'GENERADOR': ''}
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

# 7. Pestaña de comparación con PARTICIPACIÓN PROMEDIO
with tab2:
    st.header("Análisis Comparativo")
    
    if not df_filtered.empty:
        # Gráfico comparativo de generadores
        st.subheader("Comparación entre Generadores")
        
        # Agrupación eficiente
        df_comparacion = (
            df_filtered.groupby(['FECHA', 'GENERADOR'], as_index=False)
            ['Energía kWh'].sum()
        )
        
        fig_comparativo = px.line(
            df_comparacion,
            x='FECHA',
            y='Energía kWh',
            color='GENERADOR',
            markers=True,
            line_shape='spline',
            title="Comparación de Energía por Generador"
        )
        
        fig_comparativo.update_layout(
            yaxis_title="Energía (kWh)",
            xaxis_title="Fecha",
            legend_title="Generadores",
            height=500
        )
        st.plotly_chart(fig_comparativo, use_container_width=True)
        
        # Tabla de resumen
        st.subheader("Resumen de Energía por Generador")
        st.subheader("Resumen Estadístico")

        # Calcular total del sistema por fecha
        total_por_mes = df_filtered.groupby('FECHA', as_index=False, sort=False)['Energía kWh'].sum()
        total_por_mes = total_por_mes.rename(columns={'Energía kWh': 'Total_Sistema'})

        # Calcular energía por generador por fecha
        generador_por_mes = df_filtered.groupby(['FECHA', 'GENERADOR'], as_index=False)['Energía kWh'].sum()

        # Combinar y calcular participación mensual
        df_participacion = pd.merge(generador_por_mes, total_por_mes, on='FECHA')
        df_participacion['Participacion'] = (df_participacion['Energía kWh'] / df_participacion['Total_Sistema']) * 100

        # Calcular estadísticas (manteniendo valores numéricos)
        stats = (
            df_participacion.groupby('GENERADOR', as_index=False)
            .agg(
                Minimo=('Energía kWh', 'min'),
                Promedio=('Energía kWh', 'mean'),
                Maximo=('Energía kWh', 'max'),
                Participacion_Promedio=('Participacion', 'mean')
            )
        )

        # ORDENAR por participación promedio DESCENDENTE (usando columna numérica)
        stats = stats.sort_values(by='Participacion_Promedio', ascending=False)

        # Renombrar columnas
        stats = stats.rename(columns={
            'GENERADOR': 'Generador',
            'Minimo': 'Mínimo (kWh)',
            'Promedio': 'Promedio (kWh)',
            'Maximo': 'Máximo (kWh)',
            'Participacion_Promedio': 'Participación Promedio (%)'
        })

        # Formatear valores (después del ordenamiento)
        stats['Mínimo (kWh)'] = stats['Mínimo (kWh)'].apply(lambda x: f"{x:,.2f}")
        stats['Promedio (kWh)'] = stats['Promedio (kWh)'].apply(lambda x: f"{x:,.2f}")
        stats['Máximo (kWh)'] = stats['Máximo (kWh)'].apply(lambda x: f"{x:,.2f}")
        stats['Participación Promedio (%)'] = stats['Participación Promedio (%)'].apply(lambda x: f"{x:.2f}%")

# Mostrar tabla ordenada
st.dataframe(stats)

# 8. Panel informativo optimizado
st.sidebar.markdown("---")
st.sidebar.subheader("Métricas del Sistema")
if not df_filtered.empty:
    st.sidebar.metric("Centrales", df_filtered['CENTRAL'].nunique())
    st.sidebar.metric("Generadores", df_filtered['GENERADOR'].nunique())
    st.sidebar.metric("Energía Total", f"{total_energia_sistema:,.2f} MWh")
    st.sidebar.caption(f"Periodo: {df_filtered['FECHA'].min().strftime('%Y-%m')} a {df_filtered['FECHA'].max().strftime('%Y-%m')}")
else:
    st.sidebar.warning("Sin datos para mostrar métricas")
