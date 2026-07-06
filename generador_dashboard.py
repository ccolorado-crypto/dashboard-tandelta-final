import pandas as pd
import os
import glob
import json

def generar_dashboard():
    # 1. Definir rutas relativas
    ruta_base = os.path.dirname(os.path.abspath(__file__))
    carpeta_data = os.path.join(ruta_base, 'data')
    carpeta_public = os.path.join(ruta_base, 'public')
    
    os.makedirs(carpeta_public, exist_ok=True)
    archivo_salida_html = os.path.join(carpeta_public, "index.html")
    
    print("Buscando archivos en la carpeta 'data'...")
    
    if not os.path.exists(carpeta_data):
        print("ERROR: No existe la carpeta 'data'.")
        return
        
    archivos = glob.glob(os.path.join(carpeta_data, '*.*'))
    archivos_validos = [f for f in archivos if not f.endswith(('.py', '.html', '.bat', '.exe', '.txt'))]
    
    if not archivos_validos:
        print("ERROR: No se encontró ningún archivo de datos en la carpeta 'data'.")
        return

    # Tomar el archivo más reciente
    archivo_datos = max(archivos_validos, key=os.path.getmtime)
    print(f"Archivo detectado: {os.path.basename(archivo_datos)}")
    print("Procesando la información...")

    try:
        # Cargar datos
        df = pd.read_csv(archivo_datos, sep='\t')
        df.columns = df.columns.str.strip().str.replace('"', '').str.lower()
        df['numericvalue'] = pd.to_numeric(df['numericvalue'], errors='coerce')
        df['datetimestamp'] = pd.to_datetime(df['datetimestamp'])
        df['fecha'] = df['datetimestamp'].dt.date
        
        # Procesar Tan Delta (Variable 4500)
        df_tan_delta = df[df['variableid'] == 4500].copy()
        resumen_tan = df_tan_delta.groupby('fecha')['numericvalue'].agg(
            Tan_Delta_Min='min',
            Tan_Delta_Max='max',
            Tan_Delta_Promedio='mean'
        ).reset_index()
        
        # Calcular tiempo de operación real (Detección de turnos y madrugadas)
        df_tan_delta = df_tan_delta.sort_values('datetimestamp')
        df_tan_delta['diferencia_segundos'] = df_tan_delta['datetimestamp'].diff().dt.total_seconds()
        df_tan_delta['diferencia_segundos'] = df_tan_delta['diferencia_segundos'].fillna(0)
        df_tan_delta.loc[df_tan_delta['diferencia_segundos'] > 3600, 'diferencia_segundos'] = 0
        
        tiempo_operacion = df_tan_delta.groupby('fecha')['diferencia_segundos'].sum().reset_index()
        tiempo_operacion['Horas_Operacion'] = tiempo_operacion['diferencia_segundos'] / 3600
        tiempo_operacion = tiempo_operacion[['fecha', 'Horas_Operacion']]
        
        # Procesar Temperatura (Variable 61)
        df_temp = df[df['variableid'] == 61]
        resumen_temp = df_temp.groupby('fecha')['numericvalue'].agg(
            Temp_Aceite_Promedio='mean'
        ).reset_index()
        
        # Unir resúmenes
        dashboard_df = pd.merge(resumen_tan, tiempo_operacion, on='fecha', how='outer')
        dashboard_df = pd.merge(dashboard_df, resumen_temp, on='fecha', how='outer')
        
        # Redondear para la tabla
        dashboard_df = dashboard_df.round(2)
        
        # Convertir datos a listas nativas de Python/JSON para pasarlas a JavaScript de forma segura
        fechas_list = [str(f) for f in dashboard_df['fecha']]
        td_min_list = dashboard_df['Tan_Delta_Min'].fillna(0).tolist()
        td_max_list = dashboard_df['Tan_Delta_Max'].fillna(0).tolist()
        td_prom_list = dashboard_df['Tan_Delta_Promedio'].fillna(0).tolist()
        horas_list = dashboard_df['Horas_Operacion'].fillna(0).tolist()
        temp_list = dashboard_df['Temp_Aceite_Promedio'].fillna(0).tolist()
        
        # Renombrar columnas exclusivamente para la tabla HTML
        tabla_df = dashboard_df.copy()
        tabla_df.rename(columns={
            'fecha': 'Fecha',
            'Tan_Delta_Min': 'Tan Delta (Mínimo)',
            'Tan_Delta_Max': 'Tan Delta (Máximo)',
            'Tan_Delta_Promedio': 'Tan Delta (Promedio)',
            'Horas_Operacion': 'Horas de Operación',
            'Temp_Aceite_Promedio': 'Temp. Aceite Promedio (PSI)'
        }, inplace=True)
        
        # Generar HTML con estilo ÁRTIMO y Gráficas Interactivas
        html_template = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard ÁRTIMO - Analítica de Generadores</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 40px; background-color: #f7f7f7; color: #5a5a5a; }}
                .header-container {{ text-align: center; margin-bottom: 30px; }}
                .header-container img {{ max-width: 220px; margin-bottom: 15px; }}
                h1 {{ color: #d12027; font-size: 26px; margin: 0; letter-spacing: 0.5px; }}
                
                .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 25px; margin-top: 30px; margin-bottom: 40px; }}
                .chart-card {{ background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border: 1px solid #e0e0e0; }}
                .chart-card h3 {{ color: #333; margin-top: 0; margin-bottom: 15px; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px; border-left: 4px solid #d12027; padding-left: 10px; }}
                
                .table-container {{ background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border: 1px solid #e0e0e0; overflow-x: auto; }}
                .table-container h3 {{ color: #333; margin-top: 0; margin-bottom: 15px; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px; border-left: 4px solid #5a5a5a; padding-left: 10px; }}
                table {{ border-collapse: collapse; width: 100%; background-color: #ffffff; border-radius: 6px; overflow: hidden; }}
                th, td {{ border: 1px solid #e0e0e0; padding: 14px; text-align: center; font-size: 14px; }}
                th {{ background-color: #d12027; color: #ffffff; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
                tr:nth-child(even) {{ background-color: #fbfbfb; }}
                tr:hover {{ background-color: #fde8e9; }}
            </style>
        </head>
        <body>
            <div class="header-container">
                <img src="logo.png" alt="Logo ÁRTIMO">
                <h1>Tablero de Analítica Predictiva - Generadores</h1>
            </div>
            
            <div class="charts-grid">
                <div class="chart-card">
                    <h3>1. Tendencia y Degradación del Tan Delta</h3>
                    <canvas id="chartTanDelta"></canvas>
                </div>
                <div class="chart-card">
                    <h3>2. Horas de Operación Diaria (Uso)</h3>
                    <canvas id="chartHoras"></canvas>
                </div>
                <div class="chart-card" style="grid-column:  1 / -1;">
                    <h3>3. Correlación: Temperatura vs. Tan Delta Promedio</h3>
                    <canvas id="chartCorrelacion" height="120"></canvas>
                </div>
            </div>

            <div class="table-container">
                <h3>Resumen Consolidado de Datos</h3>
                {tabla_df.to_html(index=False, classes='table', border=0)}
            </div>

            <script>
                const labelsFechas = {json.dumps(fechas_list)};
                const dataTanMin = {json.dumps(td_min_list)};
                const dataTanMax = {json.dumps(td_max_list)};
                const dataTanProm = {json.dumps(td_prom_list)};
                const dataHoras = {json.dumps(horas_list)};
                const dataTemp = {json.dumps(temp_list)};

                // --- GRÁFICA 1: TENDENCIA TAN DELTA ---
                new Chart(document.getElementById('chartTanDelta'), {{
                    type: 'line',
                    data: {{
                        labels: labelsFechas,
                        datasets: [
                            {{ label: 'Máximo', data: dataTanMax, borderColor: '#d12027', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 3 }},
                            {{ label: 'Promedio', data: dataTanProm, borderColor: '#f07d1a', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], pointRadius: 3 }},
                            {{ label: 'Mínimo', data: dataTanMin, borderColor: '#5a5a5a', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 3 }}
                        ]
                    }},
                    options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }} }}
                }});

                // --- GRÁFICA 2: HORAS DE OPERACIÓN ---
                new Chart(document.getElementById('chartHoras'), {{
                    type: 'bar',
                    data: {{
                        labels: labelsFechas,
                        datasets: [{{
                            label: 'Horas Operadas',
                            data: dataHoras,
                            backgroundColor: '#5a5a5a',
                            hoverBackgroundColor: '#d12027',
                            borderRadius: 4
                        }}]
                    }},
                    options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
                }});

                // --- GRÁFICA 3: CORRELACIÓN DOBLE EJE ---
                new Chart(document.getElementById('chartCorrelacion'), {{
                    type: 'bar',
                    data: {{
                        labels: labelsFechas,
                        datasets: [
                            {{
                                type: 'line',
                                label: 'Tan Delta Promedio (Eje Izq)',
                                data: dataTanProm,
                                borderColor: '#d12027',
                                backgroundColor: 'transparent',
                                yAxisID: 'yTanDelta',
                                borderWidth: 3
                            }},
                            {{
                                type: 'bar',
                                label: 'Temperatura Promedio PSI (Eje Der)',
                                data: dataTemp,
                                backgroundColor: 'rgba(90, 90, 90, 0.2)',
                                borderColor: '#5a5a5a',
                                borderWidth: 1,
                                yAxisID: 'yTemp',
                                borderRadius: 4
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        scales: {{
                            yTanDelta: {{ type: 'linear', position: 'left', title: {{ display: true, text: 'Tan Delta' }} }},
                            yTemp: {{ type: 'linear', position: 'right', title: {{ display: true, text: 'Temperatura (PSI)' }}, grid: {{ drawOnChartArea: false }} }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        with open(archivo_salida_html, 'w', encoding='utf-8') as f:
            f.write(html_template)
            
        print(f"\n¡Éxito! Dashboard guardado en: {archivo_salida_html}")
        
    except Exception as e:
        print(f"\nOcurrió un error inesperado al procesar los datos: {e}")

if __name__ == '__main__':
    generar_dashboard()
