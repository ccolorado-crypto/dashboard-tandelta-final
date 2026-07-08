import pandas as pd
import os
import glob
import json
from datetime import datetime
import pytz

def generar_dashboard():
    ruta_base = os.path.dirname(os.path.abspath(__file__))
    carpeta_data = os.path.join(ruta_base, 'data')
    carpeta_public = os.path.join(ruta_base, 'public')
    
    os.makedirs(carpeta_public, exist_ok=True)
    archivo_salida_html = os.path.join(carpeta_public, "index.html")
    archivo_salida_csv = os.path.join(carpeta_public, "data_cruda.csv")
    
    print("Buscando todos los archivos de datos en la carpeta 'data'...")
    
    if not os.path.exists(carpeta_data):
        print("ERROR: No existe la carpeta 'data'.")
        return
        
    archivos = glob.glob(os.path.join(carpeta_data, '*.*'))
    archivos_validos = [f for f in archivos if not f.endswith(('.py', '.html', '.bat', '.exe', '.txt', '.md'))]
    
    if not archivos_validos:
        print("ERROR: No se encontraron archivos de datos en la carpeta 'data'.")
        return

    try:
        lista_df = []
        for archivo in archivos_validos:
            try:
                temp_df = pd.read_csv(archivo, sep='\t')
                temp_df.columns = temp_df.columns.str.strip().str.replace('"', '').str.replace("'", "").str.lower()
                lista_df.append(temp_df)
            except Exception as e:
                print(f"-> Error al leer el archivo {os.path.basename(archivo)}: {e}")
        
        df = pd.concat(lista_df, ignore_index=True)
        df.to_csv(archivo_salida_csv, index=False, sep=';')
        
        df['datetimestamp'] = pd.to_datetime(df['datetimestamp'], errors='coerce')
        df['fecha_str'] = df['datetimestamp'].dt.strftime('%Y-%m-%d')
        
        df['numericvalue'] = pd.to_numeric(df['numericvalue'].astype(str).str.replace('"', '').str.replace("'", ""), errors='coerce')
        df['variableid_str'] = df['variableid'].astype(str).str.strip().str.replace('.0', '', regex=False)
        
        df = df.dropna(subset=['fecha_str', 'numericvalue'])
        
        # 3. PROCESAR TAN DELTA (4500)
        df_tan_delta = df[(df['variableid_str'] == '4500') | (df['variableid'] == 4500)].copy()
        
        if df_tan_delta.empty:
            resumen_tan = pd.DataFrame(columns=['fecha_str', 'Tan_Delta_Min', 'Tan_Delta_Max', 'Tan_Delta_Promedio'])
            tiempo_operacion = pd.DataFrame(columns=['fecha_str', 'Horas_Operacion'])
        else:
            resumen_tan = df_tan_delta.groupby('fecha_str')['numericvalue'].agg(
                Tan_Delta_Min='min',
                Tan_Delta_Max='max',
                Tan_Delta_Promedio='mean'
            ).reset_index()
            
            df_tan_delta = df_tan_delta.sort_values('datetimestamp')
            df_tan_delta['diferencia_segundos'] = df_tan_delta['datetimestamp'].diff().dt.total_seconds().fillna(0)
            df_tan_delta.loc[df_tan_delta['diferencia_segundos'] > 3600, 'diferencia_segundos'] = 0
            
            tiempo_operacion = df_tan_delta.groupby('fecha_str')['diferencia_segundos'].sum().reset_index()
            tiempo_operacion['Horas_Operacion'] = tiempo_operacion['diferencia_segundos'] / 3600
            tiempo_operacion = tiempo_operacion[['fecha_str', 'Horas_Operacion']]
        
        # 4. PROCESAR TEMPERATURA (61)
        df_temp = df[(df['variableid_str'] == '61') | (df['variableid'] == 61)].copy()
        if df_temp.empty:
            resumen_temp = pd.DataFrame(columns=['fecha_str', 'Temp_Aceite_Promedio'])
        else:
            resumen_temp = df_temp.groupby('fecha_str')['numericvalue'].agg(
                Temp_Aceite_Promedio='mean'
            ).reset_index()
        
        # 5. UNIR RESÚMENES
        dashboard_df = pd.merge(resumen_tan, tiempo_operacion, on='fecha_str', how='outer')
        dashboard_df = pd.merge(dashboard_df, resumen_temp, on='fecha_str', how='outer')
        dashboard_df = dashboard_df.sort_values('fecha_str').fillna(0).round(2)
        
        zona_horaria = pytz.timezone('America/Bogota')
        fecha_actualizacion = datetime.now(zona_horaria).strftime("%d/%m/%Y a las %I:%M %p")
        
        fechas_list = dashboard_df['fecha_str'].tolist()
        tan_min_list = dashboard_df['Tan_Delta_Min'].tolist()
        tan_max_list = dashboard_df['Tan_Delta_Max'].tolist()
        tan_prom_list = dashboard_df['Tan_Delta_Promedio'].tolist()
        horas_list = dashboard_df['Horas_Operacion'].tolist()
        temp_list = dashboard_df['Temp_Aceite_Promedio'].tolist()

        kpi_max_historico = float(dashboard_df['Tan_Delta_Max'].max()) if not dashboard_df.empty else 0.0
        kpi_prom_historico = float(dashboard_df['Tan_Delta_Promedio'].mean()) if not dashboard_df.empty else 0.0
        kpi_total_horas = float(dashboard_df['Horas_Operacion'].sum()) if not dashboard_df.empty else 0.0

        # 6. PLANTILLA HTML CON SALVAGUARDAS DE RENDERIZADO
        html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard ÁRTIMO - Analítica Predictiva</title>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Montserrat:ital,wght@1,300;1,400&display=swap');
        
        body { font-family: 'Plus Jakarta Sans', sans-serif; margin: 0; padding: 40px; background-color: #f8fafc; color: #1e293b; }
        .dashboard-wrapper { max-width: 1300px; margin: 0 auto; }
        
        .header-container { text-align: center; margin-bottom: 35px; }
        .header-container img { max-width: 200px; margin-bottom: 12px; display: block; margin-left: auto; margin-right: auto; }
        h1 { color: #d12027; font-size: 30px; margin: 0; font-weight: 700; letter-spacing: -0.5px; }
        
        .update-badge { display: inline-block; background-color: #f1f5f9; color: #64748b; font-size: 13px; font-weight: 500; padding: 6px 16px; border-radius: 20px; border: 1px solid #e2e8f0; margin-top: 10px; }
        .update-badge strong { color: #475569; }
        
        .kpi-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .kpi-card { background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.02); position: relative; overflow: hidden; }
        .kpi-card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background-color: #d12027; }
        .kpi-card.secondary::before { background-color: #64748b; }
        .kpi-card.warning::before { background-color: #f59e0b; }
        .kpi-title { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
        .kpi-value { font-size: 26px; font-weight: 700; color: #0f172a; margin-top: 5px; }
        
        .control-panel { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); border: 1px solid #e2e8f0; margin-bottom: 30px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 15px; }
        .filter-group { display: flex; align-items: center; gap: 10px; }
        .filter-group label { font-weight: 600; color: #475569; font-size: 14px; }
        .filter-group input[type="date"] { padding: 8px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-family: inherit; font-size: 14px; color: #1e293b; outline: none; transition: border 0.2s; }
        .filter-group input[type="date"]:focus { border-color: #d12027; }
        
        .button-group { display: flex; gap: 12px; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; font-weight: 600; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s ease; text-decoration: none; }
        .btn-primary { background-color: #d12027; color: #ffffff; }
        .btn-primary:hover { background-color: #b01a1f; box-shadow: 0 4px 12px rgba(209,32,39,0.2); }
        .btn-secondary { background-color: #475569; color: #ffffff; }
        .btn-secondary:hover { background-color: #334155; }
        
        .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(550px, 1fr)); gap: 25px; margin-bottom: 35px; }
        .chart-card { background-color: #ffffff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); border: 1px solid #e2e8f0; min-height: 340px; }
        .chart-card h3 { color: #0f172a; margin-top: 0; margin-bottom: 20px; font-size: 16px; font-weight: 700; border-left: 4px solid #d12027; padding-left: 12px; letter-spacing: -0.3px; }
        
        .table-container { background-color: #ffffff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); border: 1px solid #e2e8f0; overflow-x: auto; margin-bottom: 40px; }
        .table-container h3 { color: #0f172a; margin-top: 0; margin-bottom: 20px; font-size: 16px; font-weight: 700; border-left: 4px solid #475569; padding-left: 12px; }
        
        table { border-collapse: collapse; width: 100%; min-width: 800px; }
        th, td { padding: 14px; text-align: center; font-size: 14px; border-bottom: 1px solid #f1f5f9; }
        th { background-color: #f8fafc; color: #64748b; font-weight: 700; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; border-top: 1px solid #e2e8f0; }
        tr:hover { background-color: #fecaca33; }
        
        .footer-signature { text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-family: 'Montserrat', sans-serif; font-size: 14px; color: #64748b; font-weight: 400; }
        .footer-signature span { font-weight: 600; color: #1e293b; letter-spacing: 0.2px; }
        
        .no-render { display: none !important; }
    </style>
</head>
<body>
    <div class="dashboard-wrapper" id="content-to-pdf">
        <div class="header-container">
            <img src="logo.png" alt="Logo ÁRTIMO" onerror="this.src='../logo.png'; this.onerror=null;">
            <h1>Sistema de Monitoreo Analítico - Generadores</h1>
            <div class="update-badge">Última actualización: <strong>FECHA_UPDATE_PLACEHOLDER</strong></div>
        </div>

        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-title">Máximo Histórico Tan Delta</div>
                <div class="kpi-value" id="kpi-max">0.00</div>
            </div>
            <div class="kpi-card warning">
                <div class="kpi-title">Promedio General Registrado</div>
                <div class="kpi-value" id="kpi-prom">0.00</div>
            </div>
            <div class="kpi-card secondary">
                <div class="kpi-title">Total Horas de Operación</div>
                <div class="kpi-value" id="kpi-horas">0.00 hrs</div>
            </div>
        </div>
        
        <div class="control-panel" id="action-panel">
            <div class="filter-group">
                <label>Desde:</label>
                <input type="date" id="fechaInicio" onchange="filtrarDashboard()">
                <label style="margin-left: 10px;">Hasta:</label>
                <input type="date" id="fechaFin" onchange="filtrarDashboard()">
            </div>
            <div class="button-group">
                <a href="data_cruda.csv" download="data_cruda_artimo.csv" class="btn btn-secondary">
                    📥 Descargar Data Cruda
                </a>
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

        <div class="footer-signature">
            Dashboard creado por <span>Carlos Colorado</span> - Líder de Producto
        </div>
    </div>

    <script>
        const listasFechas = FECHAS_PLACEHOLDER;
        const listasTanMin = TANMIN_PLACEHOLDER;
        const listasTanMax = TANMAX_PLACEHOLDER;
        const listasTanProm = TANPROM_PLACEHOLDER;
        const listasHoras = HORAS_PLACEHOLDER;
        const listasTemp = TEMP_PLACEHOLDER;

        document.getElementById('kpi-max').innerText = parseFloat(KPI_MAX_PLACEHOLDER).toFixed(2);
        document.getElementById('kpi-prom').innerText = parseFloat(KPI_PROM_PLACEHOLDER).toFixed(2);
        document.getElementById('kpi-horas').innerText = parseFloat(KPI_HORAS_PLACEHOLDER).toFixed(1) + " hrs";

        let chart1, chart2, chart3;

        function inicializarDashboard() {
            if(listasFechas.length > 0) {
                // Intentar asignar los valores a los inputs del calendario
                document.getElementById('fechaInicio').value = listasFechas[0];
                document.getElementById('fechaFin').value = listasFechas[listasFechas.length - 1];
                
                // Ejecutar el filtrado inicial pase lo que pase
                filtrarDashboard();
            } else {
                document.getElementById('contenedorTabla').innerHTML = '<p style="text-align:center; padding: 20px; color:#64748b;">No se encontraron fechas de sensores válidas.</p>';
            }
        }

        function filtrarDashboard() {
            // SALVAGUARDA CRÍTICA: Si el input del navegador está vacío, recurrir directamente a la matriz de datos nativa
            let inicio = document.getElementById('fechaInicio').value;
            let fin = document.getElementById('fechaFin').value;
            
            if (!inicio && listasFechas.length > 0) inicio = listasFechas[0];
            if (!fin && listasFechas.length > 0) fin = listasFechas[listasFechas.length - 1];
            
            if(listasFechas.length === 0) return;
            
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

            if(labels.length === 0) return;

            chart1 = new Chart(document.getElementById('chartTanDelta'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'Máx Tan Delta', data: tanMax, borderColor: '#d12027', backgroundColor: 'transparent', borderWidth: 2.5, tension: 0.1 },
                        { label: 'Promedio', data: tanProm, borderColor: '#f07d1a', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5] },
                        { label: 'Mín Tan Delta', data: tanMin, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 1.5 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            chart2 = new Chart(document.getElementById('chartHoras'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{ label: 'Horas Operación', data: horas, backgroundColor: '#475569', hoverBackgroundColor: '#d12027', borderRadius: 6 }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            chart3 = new Chart(document.getElementById('chartCorrelacion'), {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        { type: 'line', label: 'Tan Delta Promedio', data: tanProm, borderColor: '#d12027', backgroundColor: 'transparent', yAxisID: 'yTan', borderWidth: 2.5, tension: 0.1 },
                        { type: 'bar', label: 'Temperatura Promedio', data: temp, backgroundColor: 'rgba(71, 85, 105, 0.12)', borderColor: '#475569', yAxisID: 'yTemp', borderRadius: 4 }
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
            if(indices.length === 0) {
                document.getElementById('contenedorTabla').innerHTML = '<p style="text-align:center; padding: 20px;">No hay datos para el rango seleccionado.</p>';
                return;
            }
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
                    <td style="font-weight:600; color:#475569;">${listasFechas[i]}</td>
                    <td>${listasTanMin[i]}</td>
                    <td style="color:#d12027; font-weight:700;">${listasTanMax[i]}</td>
                    <td>${listasTanProm[i]}</td>
                    <td style="font-weight:500;">${listasHoras[i]} hrs</td>
                    <td>${listasTemp[i]}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            document.getElementById('contenedorTabla').innerHTML = html;
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
        
        html_final = html_content.replace("FECHAS_PLACEHOLDER", json.dumps(fechas_list))
        html_final = html_final.replace("TANMIN_PLACEHOLDER", json.dumps(tan_min_list))
        html_final = html_final.replace("TANMAX_PLACEHOLDER", json.dumps(tan_max_list))
        html_final = html_final.replace("TANPROM_PLACEHOLDER", json.dumps(tan_prom_list))
        html_final = html_final.replace("HORAS_PLACEHOLDER", json.dumps(horas_list))
        html_final = html_final.replace("TEMP_PLACEHOLDER", json.dumps(temp_list))
        
        html_final = html_final.replace("FECHA_UPDATE_PLACEHOLDER", fecha_actualizacion)
        html_final = html_final.replace("KPI_MAX_PLACEHOLDER", str(kpi_max_historico))
        html_final = html_final.replace("KPI_PROM_PLACEHOLDER", str(kpi_prom_historico))
        html_final = html_final.replace("KPI_HORAS_PLACEHOLDER", str(kpi_total_horas))
        
        with open(archivo_salida_html, 'w', encoding='utf-8') as f:
            f.write(html_final)
            
        print(f"\n¡Compilación completada exitosamente sin fugas de zona horaria!")
        
    except Exception as e:
        print(f"\nOcurrió un error inesperado al procesar los datos: {e}")

if __name__ == '__main__':
    generar_dashboard()
