import pandas as pd
import os
import glob

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
        
        # Generar HTML con estilo ÁRTIMO
        html_template = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard ÁRTIMO - Sensor de Aceite</title>
            <style>
                body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 40px; background-color: #f7f7f7; color: #5a5a5a; }}
                .header-container {{ text-align: center; margin-bottom: 30px; }}
                .header-container img {{ max-width: 220px; margin-bottom: 15px; }}
                h1 {{ color: #d12027; font-size: 26px; margin: 0; letter-spacing: 0.5px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; background-color: #ffffff; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden; }}
                th, td {{ border: 1px solid #e0e0e0; padding: 14px; text-align: center; font-size: 15px; }}
                th {{ background-color: #d12027; color: #ffffff; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
                tr:nth-child(even) {{ background-color: #fbfbfb; }}
                tr:hover {{ background-color: #fde8e9; }}
            </style>
        </head>
        <body>
            <div class="header-container">
                <img src="logo.png" alt="Logo ÁRTIMO">
                <h1>Monitoreo Diario - Generadores</h1>
            </div>
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
