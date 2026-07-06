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
        
    archivos = glob.glob(os.path.join(carpeta_data, '*.*'))
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
                temp_df.columns = temp_df.columns.str.strip().str.replace('"', '').str.lower()
                lista_df.append(temp_df)
            except Exception as e:
                print(f"-> Error al leer el archivo {os.path.basename(archivo)}: {e}")
        
        df = pd.concat(lista_df, ignore_index=True)
        
        # Preparar data cruda convirtiéndola a una lista limpia para evitar saltos de línea conflictivos en JS
        data_cruda_lista = df.values.tolist()
        columnas_crudas = df.columns.tolist()
        
        df['numericvalue'] = pd.to_numeric(df['numericvalue'], errors='coerce')
        df['datetimestamp'] = pd.to_datetime(df['datetimestamp'])
        df['fecha'] = df['datetimestamp'].dt.date
        
        # 3. PROCESAR TAN DELTA (Variable 4500)
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
        
        # 4. PROCESAR TEMPERATURA (Variable 61)
        df_temp = df[df['variableid'] == 61]
        resumen_temp = df_temp.groupby('fecha')['numericvalue'].agg(
            Temp_Aceite_Promedio='mean'
        ).reset_index()
        
        # 5. UNIR RESÚMENES
        dashboard_df = pd.merge(resumen_tan, tiempo_operacion, on='fecha', how='outer')
        if not resumen_temp.empty:
            dashboard_df = pd.merge(dashboard_df, resumen_temp, on='fecha', how='outer')
        else:
            dashboard_df['Temp_Aceite_Promedio'] = 0
            
        dashboard_df = dashboard_df.sort_values('fecha').fillna(0).round(2)
        
        # Convertir datos procesados a listas nativas compatibles con JSON puro
        fechas_list = [str(f) for f in dashboard_df['fecha']]
        tan_min_list = dashboard_df['Tan_Delta_Min'].tolist()
        tan_max_list = dashboard_df['Tan_Delta_Max'].tolist()
        tan_prom_list = dashboard_df['Tan_Delta_Promedio'].tolist()
        horas_list = dashboard_df['Horas_Operacion'].tolist()
        temp_list = dashboard_df['Temp_Aceite_Promedio'].tolist()

        # 6. PLANTILLA HTML MONOLÍTICA (INMUNE A ERRORES DE RED)
        html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard ÁRTIMO - Analítica Predictiva</title>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    
    <style>
        body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 40px; background-color: #f4f5f7; color: #4a4a4a; }
        .dashboard-wrapper { max-width: 1300px; margin: 0 auto; }
        .header-container { text-align: center; margin-bottom: 35px; }
        .header-container img { max-width: 220px; margin-bottom: 12px; display: block; margin-left: auto; margin-right: auto; }
        h1 { color: #d12027; font-size: 28px; margin: 0; font-weight: 700; letter-spacing: 0.5px; }
        .control-panel { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; margin-bottom: 30px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 15px; }
        .filter-group { display: flex; align-items: center; gap: 10px; }
        .filter-group label { font-weight: 600; color: #5a5a5a; font-size: 14px; }
        .filter-group input[type="date"] { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-family: inherit; font-size: 14px; color: #334155; outline: none; }
        .filter-group input[type="date"]:focus { border-color: #d12027; }
        .button-group { display: flex; gap: 12px; }
        .btn { padding: 10px 18px; border: none; border-radius: 6px; font-weight: 600; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s ease; }
        .btn-primary { background-color: #d12027; color: #ffffff; }
        .btn-primary:hover { background-color: #b01a1f; }
        .btn-secondary { background-color: #5a5a5a; color: #ffffff; }
        .btn-secondary:hover { background-color: #454545; }
        .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(550px, 1fr)); gap: 25px; margin-bottom: 35px; }
        .chart-card { background-color: #ffffff; padding: 22px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; min-height: 340px; }
        .chart-card h3 { color: #2d3748; margin-top: 0; margin-bottom: 20px; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px; border-left: 4px solid #d12027; padding-left: 12px; }
        .table-container { background-color: #ffffff; padding: 25px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; overflow-x: auto; }
        .table-container h3 { color: #2d3748; margin-top: 0; margin-bottom: 20px; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px; border-left: 4px solid #5a5a5a; padding-left: 12px; }
        table { border-collapse: collapse; width: 100%; min-width: 800px; }
        th, td { padding: 14px; text-align: center; font-size: 14px; border-bottom: 1px solid #e2e8f0; }
        th { background-color: #f8fafc; color: #475569; font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; border-top: 1px solid #e2e8f0; }
        tr:hover { background-color: #fdf2f2; }
        .no-render { display: none !important; }
    </style>
</head>
<body>
    <div class="dashboard-wrapper" id="content-to-pdf">
        <div class="header-container">
            <img src="logo.png" alt="Logo ÁRTIMO" onerror="this.src='../logo.png'; this.onerror=null;">
            <h1>Sistema de Monitoreo Analítico - Generadores</h1>
        </div>
        
        <div class="control-panel" id="action-panel">
            <div class="filter-group">
                <label>Desde:</label>
                <input type="date" id="fechaInicio" onchange="filtrarDashboard()">
                <label style="margin-left: 10px;">Hasta:</label>
                <input type="date" id="fechaFin" onchange="filtrarDashboard()">
            </div>
            <div class="button-group">
                <button class="btn btn-secondary" onclick="descargarDataCruda()">
                    📥 Descargar Data Cruda
                </button>
                <button class="btn btn-primary" onclick="exportarPDF()">
                    📄 Exportar Reporte PDF
                </button>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-card">
                <h3>1. Análisis y Evolución de Tan Delta</h3>
                <div style="position: relative; height:280px; width:100%"><canvas id="chartTanDelta"></canvas></div>
            </div>
            <div class="chart-card">
                <h3>2. Uso Diario (Horas de Operación)</h3>
                <div style="position: relative; height:280px; width:100%"><canvas id="chartHoras"></canvas></div>
            </div>
            <div class="chart-card" style="grid-column: 1 / -1;">
                <h3>3. Diagnóstico de Correlación: Temperatura vs. Tan Delta Promedio</h3>
                <div style="position: relative; height:280px; width:100%"><canvas id="chartCorrelacion"></canvas></div>
            </div>
        </div>

        <div class="table-container">
            <h3>Historial Consolidado Filtrado</h3>
            <div id="contenedorTabla"></div>
        </div>
    </div>

    <script>
        // Arreglos puros estáticos inyectados por Python de forma segura
        const listasFechas = FECHAS_PLACEHOLDER;
        const listasTanMin = TANMIN_PLACEHOLDER;
        const listasTanMax = TANMAX_PLACEHOLDER;
        const listasTanProm = TANPROM_PLACEHOLDER;
        const listasHoras = HORAS_PLACEHOLDER;
        const listasTemp = TEMP_PLACEHOLDER;
        
        const columnasCrudas = COLUMNAS_CRUDAS_PLACEHOLDER;
        const dataCrudaFilas = FILAS_CRUDAS_PLACEHOLDER;

        let chart1, chart2, chart3;

        function inicializarDashboard() {
            if(listasFechas.length > 0) {
                document.getElementById('fechaInicio').value = listasFechas[0];
                document.getElementById('fechaFin').value = listasFechas[listasFechas.length - 1];
                filtrarDashboard();
            }
        }

        function filtrarDashboard() {
            const inicio = document.getElementById('fechaInicio').value;
            const fin = document.getElementById('fechaFin').value;
            
            if(!inicio || !fin) return;
            
            // Filtrar índices que cumplan el rango de fechas
            const indicesFiltrados = [];
            listasFechas.forEach((f, index) => {
                if(f >= inicio && f <= fin) indicesFiltrados.push(index);
            });
            
            const labels = indicesFiltrados.map(i => listasFechas[i]);
            const tanMin = indicesFiltrados.map(i => listasTanMin[i]);
            const tanMax = indicesFiltrados.map(i => listasTanMax[i]);
            const tanProm = indicesFiltrados.map(i => listasTanProm[i]);
            const horas = indicesFiltrados.map(i => listasHoras[i]);
            const temp = indicesFiltrados.map(i => listasTemp[i]);

            renderizarGraficas(labels, tanMin, tanMax, tanProm, horas, temp);
            renderizarTabla(indicesFiltrados);
        }

        function renderizarGraficas(labels, tanMin, tanMax, tanProm, horas, temp) {
            if(chart1) chart1.destroy();
            if(chart2) chart2.destroy();
            if(chart3) chart3.destroy();

            chart1 = new Chart(document.getElementById('chartTanDelta'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'Máx Tan Delta', data: tanMax, borderColor: '#d12027', backgroundColor: 'transparent', borderWidth: 2 },
                        { label: 'Promedio', data: tanProm, borderColor: '#f07d1a', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5] },
                        { label: 'Mín Tan Delta', data: tanMin, borderColor: '#5a5a5a', backgroundColor: 'transparent', borderWidth: 1.5 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            chart2 = new Chart(document.getElementById('chartHoras'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{ label: 'Horas', data: horas, backgroundColor: '#5a5a5a', hoverBackgroundColor: '#d12027', borderRadius: 4 }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            chart3 = new Chart(document.getElementById('chartCorrelacion'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        { type: 'line', label: 'Tan Delta Promedio', data: tanProm, borderColor: '#d12027', backgroundColor: 'transparent', yAxisID: 'yTan', borderWidth: 2.5 },
                        { type: 'bar', label: 'Temperatura Promedio', data: temp, backgroundColor: 'rgba(90, 90, 90, 0.15)', borderColor: '#5a5a5a', yAxisID: 'yTemp', borderRadius: 3 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        yTan: { type: 'linear', position: 'left' },
                        yTemp: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } }
                    }
                }
            });
        }

        function renderizarTabla(indices) {
            let html = `<table>
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Tan Delta (Mín)</th>
                        <th>Tan Delta (Máx)</th>
                        <th>Tan Delta (Prom)</th>
                        <th>Horas de Operación</th>
                        <th>Temp. Aceite Promedio</th>
                    </tr>
                </thead>
                <tbody>`;
            
            indices.forEach(i => {
                html += `<tr>
                    <td style="font-weight:600;">${listasFechas[i]}</td>
                    <td>${listasTanMin[i]}</td>
                    <td style="color:#d12027; font-weight:600;">${listasTanMax[i]}</td>
                    <td>${listasTanProm[i]}</td>
                    <td>${listasHoras[i]} hrs</td>
                    <td>${listasTemp[i]}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            document.getElementById('contenedorTabla').innerHTML = html;
        }

        function descargarDataCruda() {
            let csvContent = columnasCrudas.join(";") + "\\n";
            dataCrudaFilas.forEach(fila => {
                csvContent += fila.join(";") + "\\n";
            });
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            link.setAttribute("href", URL.createObjectURL(blob));
            link.setAttribute("download", "data_cruda_artimo.csv");
            link.click();
        }

        function exportarPDF() {
            document.getElementById('action-panel').classList.add('no-render');
            const elemento = document.getElementById('content-to-pdf');
            const opciones = {
                margin:       [10, 10, 10, 10],
                filename:     'reporte_monitoreo_artimo.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2, useCORS: true },
                jsPDF:        { unit: 'mm', format: 'a3', orientation: 'landscape' }
            };
            html2pdf().set(opciones).from(elemento).save().then(() => {
                document.getElementById('action-panel').classList.remove('no-render');
            });
        }

        inicializarDashboard();
    </script>
</body>
</html>"""
        
        # Reemplazar marcadores usando JSON puro libre de comillas rotas
        html_final = html_content.replace("FECHAS_PLACEHOLDER", json.dumps(fechas_list))
        html_final = html_final.replace("TANMIN_PLACEHOLDER", json.dumps(tan_min_list))
        html_final = html_final.replace("TANMAX_PLACEHOLDER", json.dumps(tan_max_list))
        html_final = html_final.replace("TANPROM_PLACEHOLDER", json.dumps(tan_prom_list))
        html_final = html_final.replace("HORAS_PLACEHOLDER", json.dumps(horas_list))
        html_final = html_final.replace("TEMP_PLACEHOLDER", json.dumps(temp_list))
        
        html_final = html_final.replace("COLUMNAS_CRUDAS_PLACEHOLDER", json.dumps(columnas_crudas))
        html_final = html_final.replace("FILAS_CRUDAS_PLACEHOLDER", json.dumps(data_cruda_lista))
        
        with open(archivo_salida_html, 'w', encoding='utf-8') as f:
            f.write(html_final)
            
        print(f"\n¡Éxito! Dashboard estático monolítico generado de forma segura.")
        
    except Exception as e:
        print(f"\nOcurrió un error inesperado al procesar los datos: {e}")

if __name__ == '__main__':
    generar_dashboard()
