import pandas as pd
import os
import glob

def generar_dashboard():
    # 1. Definir rutas relativas
    ruta_base = os.path.dirname(os.path.abspath(__file__))
    carpeta_data = os.path.join(ruta_base, 'data')
    carpeta_public = os.path.join(ruta_base, 'public')
    
    # Crear la carpeta public si no existe
    os.makedirs(carpeta_public, exist_ok=True)
    
    archivo_salida_html = os.path.join(carpeta_public, "index.html")
    
    print("Buscando archivos en la carpeta 'data'...")
    
    # 2. Buscar el archivo de datos automáticamente
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
        
        # Calcular tiempo de operación real
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
        
        # Redondear y renombrar
        dashboard_df = dashboard_df.round(2)
        dashboard_df.rename(columns={
            'fecha': 'Fecha',
            'Tan_Delta_Min': 'Tan Delta (Mínimo)',
            'Tan_Delta_Max': 'Tan Delta (Máximo)',
            'Tan_Delta_Promedio': 'Tan Delta (Promedio)',
            'Horas_Operacion': 'Horas de Operación',
            'Temp_Aceite_Promedio': 'Temp. Aceite Promedio (PSI)'
        }, inplace=True)
        
        # Generar HTML
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
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; background-color: #161b22; box-shadow: 0 2px 5px rgba(0,0,0,0.5); border-radius: 6px; overflow: hidden; }}
                th, td {{ border: 1px solid #30363d; padding: 12px; text-align: center; }}
                th {{ background-color: #21262d; color: #c9d1d9; font-weight: 600; }}
                tr:nth-child(even) {{ background-color: #1a2027; }}
                tr:hover {{ background-color: #2b313c; }}
            </style>
        </head>
        <body>
            <h1>Reporte Diario: Tan Delta, Tiempo de Operación Real y Temperatura</h1>
            {dashboard_df.to_html(index=False, classes='table', border=0)}
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
