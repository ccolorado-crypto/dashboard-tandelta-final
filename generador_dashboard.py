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
    
    print("Buscando todos los archivos de datos en la carpeta 'data'...")
    
    if not os.path.exists(carpeta_data):
        print("ERROR: No existe la carpeta 'data'.")
        return
        
    # Buscar todos los archivos dentro de la carpeta data
    archivos = glob.glob(os.path.join(carpeta_data, '*.*'))
    # Ignorar archivos del sistema o notas temporales
    archivos_validos = [f for f in archivos if not f.endswith(('.py', '.html', '.bat', '.exe', '.txt', '.md'))]
    
    if not archivos_validos:
        print("ERROR: No se encontraron archivos de datos en la carpeta 'data'.")
        return

    print(f"Se encontraron {len(archivos_validos)} archivos. Uniendo información...")

    try:
        # 2. LEER Y UNIR TODOS LOS ARCHIVOS
        lista_df = []
        for archivo in archivos_validos:
            try:
                temp_df = pd.read_csv(archivo, sep='\t')
                # Normalizar nombres de columnas inmediatamente al leer
                temp_df.columns = temp_df.columns.str.strip().str.replace('"', '').str.lower()
                lista_df.append(temp_df)
                print(f"-> Archivo cargado con éxito: {os.path.basename(archivo)}")
            except Exception as e:
                print(f"-> Error al leer el archivo {os.path.basename(archivo)}: {e}")
        
        # Consolidar todo en un solo DataFrame gigante
        df = pd.concat(lista_df, ignore_index=True)
        
        # Asegurar tipos de datos correctos
        df['numericvalue'] = pd.to_numeric(df['numericvalue'], errors='coerce')
        df['datetimestamp'] = pd.to_datetime(df['datetimestamp'])
        df['fecha'] = df['datetimestamp'].dt.date
        
        # 3. PROCESAR TAN DELTA (Variable 4500)
        df_tan_delta = df[df['variableid'] == 4500].copy()
        
        # Resumen de valores de Tan Delta por fecha
        resumen_tan = df_tan_delta.groupby('fecha')['numericvalue'].agg(
            Tan_Delta_Min='min',
            Tan_Delta_Max='max',
            Tan_Delta_Promedio='mean'
        ).reset_index()
        
        # Calcular tiempo de operación diario ordenando globalmente por timestamp
        df_tan_delta = df_tan_delta.sort_values('datetimestamp')
        df_tan_delta['diferencia_segundos'] = df_tan_delta['datetimestamp'].diff().dt.total_seconds()
        df_tan_delta['diferencia_segundos'] = df_tan_delta['diferencia_segundos'].fillna(0)
        
        # Si la diferencia entre registros es mayor a 1 hora (3600s), asumimos máquina apagada
        df_tan_delta.loc[df_tan_delta['diferencia_segundos'] > 3600, 'diferencia_segundos'] = 0
        
        tiempo_operacion = df_tan_delta.groupby('fecha')['diferencia_segundos'].sum().reset_index()
        tiempo_operacion['Horas_Operacion'] = tiempo_operacion['diferencia_segundos'] / 3600
        tiempo_operacion = tiempo_operacion[['fecha', 'Horas_Operacion']]
        
        # 4. Procesar Temperatura (Variable 61)
        df_temp = df[df['variableid'] == 61]
        resumen_temp = df_temp.groupby('fecha')['numericvalue'].agg(
            Temp_Aceite_Promedio='mean'
        ).reset_index()
        
        # 5. Unir todos los resúmenes y ordenar cronológicamente
        dashboard_df = pd.merge(resumen_tan, tiempo_operacion, on='fecha', how='outer')
        dashboard_df = pd.merge(dashboard_df, resumen_temp, on='fecha', how='outer')
        
        # Ordenar por fecha de forma ascendente para que el histórico sea correcto
        dashboard_df = dashboard_df.sort_values('fecha')
        dashboard_df = dashboard_df.round(2)
        
        # Renombrar columnas para la tabla HTML
        dashboard_df.rename(columns={
            'fecha': 'Fecha',
            'Tan_Delta_Min': 'Tan Delta (Mínimo)',
            'Tan_Delta_Max': 'Tan Delta (Máximo)',
            'Tan_Delta_Promedio': 'Tan Delta (Promedio)',
            'Horas_Operacion': 'Horas de Operación',
            'Temp_Aceite_Promedio': 'Temp. Aceite Promedio (PSI)'
        }, inplace=True)
        
        # 6. Generar HTML con diseño responsivo
        html_template = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard CFS - Sensor de Aceite</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 40px; background-color: #0d1117; color: #c9d1d9; }}
                h1 {{ color: #58a6ff; text-align: center; font-size: 24px; margin-bottom: 20px;}}
                .table-container {{ width: 100%; overflow-x: auto; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; background-color: #161b22; box-shadow: 0 2px 5px rgba(0,0,0,0.5); border-radius: 6px; overflow: hidden; }}
                th, td {{ border: 1px solid #30363d; padding: 12px; text-align: center; font-size: 14px; }}
                th {{ background-color: #21262d; color: #c9d1d9; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
                tr:nth-child(even) {{ background-color: #1a2027; }}
                tr:hover {{ background-color: #2b313c; }}
                /* Estilos para las gráficas */
                .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 25px; margin-top: 30px; margin-bottom: 40px; }}
                .chart-card {{ background-color: #ffffff; color: #333; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border: 1px solid #e0e0e0; }}
                .chart-card h3 {{ color: #333; margin-top: 0; margin-bottom: 15px; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px; border-left: 4px solid #d12027; padding-left: 10px; }}
            </style>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <div style="text-align: center; margin-bottom: 30px;">
                <img src="logo.png" alt="Logo ÁRTIMO" style="max-width: 220px; margin-bottom: 15px;">
                <h1>Tablero de Analítica Histórica - Generadores</h1>
            </div>
            
            <div class="charts-grid">
                <div class="chart-card">
                    <h3>1. Tendencia Histórica del Tan Delta</h3>
                    <canvas id="chartTanDelta"></canvas>
                </div>
                <div class="chart-card">
                    <h3>2. Horas de Operación Acumuladas</h3>
                    <canvas id="chartHoras"></canvas>
                </div>
                <div class="chart-card" style="grid-column: 1 / -1;">
                    <h3>3. Correlación: Temperatura vs. Tan Delta Promedio</h3>
                    <canvas id="chartCorrelacion" height="120"></canvas>
                </div>
            </div>

            <div class="table-container">
                <table class="table">
                    {dashboard_df.to_html(index=False, classes='table', border=0)}
                </table>
            </div>

            <script>
                const labelsFechas = {json.dumps([str(f) for f in dashboard_df['Fecha']])};
                const dataTanMin = {json.dumps(dashboard_df['Tan Delta (Mínimo)'].fillna(0).tolist())};
                const dataTanMax = {json.dumps(dashboard_df['Tan Delta (Máximo)'].fillna(0).tolist())};
                const dataTanProm = {json.dumps(dashboard_df['Tan Delta (Promedio)'].fillna(0).tolist())};
                const dataHoras = {json.dumps(dashboard_df['Horas de Operación'].fillna(0).tolist())};
                const dataTemp = {json.dumps(dashboard_df['Temp. Aceite Promedio (PSI)'].fillna(0).tolist())};

                new Chart(document.getElementById('chartTanDelta'), {{
                    type: 'line',
                    data: {{
                        labels: labelsFechas,
                        datasets: [
                            {{ label: 'Máximo', data: dataTanMax, borderColor: '#d12027', backgroundColor: 'transparent', borderWidth: 2 }},
                            {{ label: 'Promedio', data: dataTanProm, borderColor: '#f07d1a', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5] }},
                            {{ label: 'Mínimo', data: dataTanMin, borderColor: '#5a5a5a', backgroundColor: 'transparent', borderWidth: 2 }}
                        ]
                    }}
                }});

                new Chart(document.getElementById('chartHoras'), {{
                    type: 'bar',
                    data: {{
                        labels: labelsFechas,
                        datasets: [{{ label: 'Horas Operadas', data: dataHoras, backgroundColor: '#5a5a5a', hoverBackgroundColor: '#d12027' }}]
                    }}
                }});

                new Chart(document.getElementById('chartCorrelacion'), {{
                    type: 'bar',
                    data: {{
                        labels: labelsFechas,
                        datasets: [
                            {{ type: 'line', label: 'Tan Delta Promedio', data: dataTanProm, borderColor: '#d12027', backgroundColor: 'transparent', yAxisID: 'yTanDelta', borderWidth: 3 }},
                            {{ type: 'bar', label: 'Temperatura Promedio', data: dataTemp, backgroundColor: 'rgba(90, 90, 90, 0.15)', borderColor: '#5a5a5a', yAxisID: 'yTemp' }}
                        ]
                    }},
                    options: {{ scales: {{ yTanDelta: {{ position: 'left' }}, yTemp: {{ position: 'right', grid: {{ drawOnChartArea: false }} }} }} }}
                }});
            </script>
        </body>
        </html>
        """
        
        with open(archivo_salida_html, 'w', encoding='utf-8') as f:
            f.write(html_template)
            
        print(f"\n¡Éxito! Dashboard histórico consolidado.")
        
    except Exception as e:
        print(f"\nOcurrió un error inesperado al procesar los datos: {e}")

if __name__ == '__main__':
    generar_dashboard()
