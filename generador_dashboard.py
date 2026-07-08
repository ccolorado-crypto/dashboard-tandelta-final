import pandas as pd
import os
import glob
from datetime import datetime
import pytz

def generar_dashboard():
    ruta_base = os.path.dirname(os.path.abspath(__file__))
    carpeta_data = os.path.join(ruta_base, 'data')
    carpeta_public = os.path.join(ruta_base, 'public')
    
    os.makedirs(carpeta_public, exist_ok=True)
    archivo_salida_html = os.path.join(carpeta_public, "index.html")
    archivo_salida_csv = os.path.join(carpeta_public, "data_cruda.csv")
    
    print("Buscando archivos de datos en la carpeta 'data'...")
    
    if not os.path.exists(carpeta_data):
        return
        
    archivos = glob.glob(os.path.join(carpeta_data, '*.*'))
    archivos_validos = [f for f in archivos if not f.endswith(('.py', '.html', '.bat', '.exe', '.txt', '.md'))]
    
    if not archivos_validos:
        return

    try:
        lista_df = []
        for archivo in archivos_validos:
            try:
                temp_df = pd.read_csv(archivo, sep='\t')
                temp_df.columns = temp_df.columns.str.strip().str.replace('"', '').str.replace("'", "").str.lower()
                lista_df.append(temp_df)
            except:
                pass
        
        df = pd.concat(lista_df, ignore_index=True)
        df.to_csv(archivo_salida_csv, index=False, sep=';')
        
        # 1. MOTOR ORIGINAL MEJORADO: Leer fechas y números
        # dayfirst=True asegura que lea 01/07 como 1 de Julio y no como 7 de Enero
        df['datetimestamp'] = pd.to_datetime(df['datetimestamp'], errors='coerce', dayfirst=True)
        df['numericvalue'] = df['numericvalue'].astype(str).str.replace(',', '.')
        df['numericvalue'] = pd.to_numeric(df['numericvalue'], errors='coerce')
        df['variableid'] = pd.to_numeric(df['variableid'], errors='coerce').fillna(0).astype(int)
        
        df = df.dropna(subset=['datetimestamp', 'numericvalue'])
        df['fecha'] = df['datetimestamp'].dt.strftime('%Y-%m-%d')
        
        # 2. PROCESAR TAN DELTA (4500)
        df_tan = df[df['variableid'] == 4500].copy()
        if df_tan.empty:
            resumen_tan = pd.DataFrame(columns=['fecha', 'Tan_Min', 'Tan_Max', 'Tan_Prom', 'Horas'])
        else:
            resumen_tan = df_tan.groupby('fecha')['numericvalue'].agg(
                Tan_Min='min', Tan_Max='max', Tan_Prom='mean'
            ).reset_index()
            
            # Recuperamos tus horas de operación
            df_tan = df_tan.sort_values('datetimestamp')
            df_tan['diff'] = df_tan['datetimestamp'].diff().dt.total_seconds().fillna(0)
            # Si el generador se apaga por más de 4 horas, cortamos el tiempo ahí
            df_tan.loc[(df_tan['diff'] > 14400) | (df_tan['diff'] < 0), 'diff'] = 0
            
            horas = df_tan.groupby('fecha')['diff'].sum().reset_index()
            horas['Horas'] = horas['diff'] / 3600
            resumen_tan = pd.merge(resumen_tan, horas, on='fecha', how='outer')

        # 3. PROCESAR TEMPERATURA (61)
        df_temp = df[df['variableid'] == 61].copy()
        if df_temp.empty:
            resumen_temp = pd.DataFrame(columns=['fecha', 'Temp_Prom'])
        else:
            resumen_temp = df_temp.groupby('fecha')['numericvalue'].agg(Temp_Prom='mean').reset_index()
        
        # 4. UNIR DATOS
        dash = pd.merge(resumen_tan, resumen_temp, on='fecha', how='outer')
        dash = dash.sort_values('fecha').fillna(0).round(2)
        
        zona_horaria = pytz.timezone('America/Bogota')
        fecha_actualizacion = datetime.now(zona_horaria).strftime("%d/%m/%Y a las %I:%M %p")
        
        kpi_max = float(dash['Tan_Max'].max()) if not dash.empty else 0.0
        kpi_prom = float(dash['Tan_Prom'].mean()) if not dash.empty else 0.0
        kpi_horas = float(dash['Horas'].sum()) if not dash.empty else 0.0

        # Exportamos al formato infalible JSON original
        json_data = dash.to_json(orient='records')

        # 5. HTML CON LA LÓGICA ORIGINAL RESTAURADA
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
        .btn-primary:hover { background-color: #b01a1f; }
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
            <div class="kpi-card"><div class="kpi-title">Máximo Histórico Tan Delta</div><div class="kpi-value" id="kpi-max">KPI_MAX_PLACEHOLDER</div></div>
            <div class="kpi-card warning"><div class="kpi-title">Promedio General Registrado</div><div class="kpi-value" id="kpi-prom">KPI_PROM_PLACEHOLDER</div></div>
            <div class="kpi-card secondary"><div class="kpi-title">Total Horas de Operación</div><div class="kpi-value" id="kpi-horas">KPI_HORAS_PLACEHOLDER hrs</div></div>
        </div>
        <div class="control-panel" id="action-panel">
            <div class="filter-group">
                <label>Desde:</label><input type="date" id="fechaInicio" onchange="filtrarDashboard()">
                <label style="margin-left: 10px;">Hasta:</label><input type="date" id="fechaFin" onchange="filtrarDashboard()">
            </div>
            <div class="button-group">
                <a href="data_cruda.csv" download="data_cruda_artimo.csv" class="btn btn-secondary">📥 Descargar Data Cruda</a>
                <button class="btn btn-primary" onclick="exportarPDF()">📄 Exportar Reporte PDF</button>
            </div>
        </div>
        <div class="charts-grid">
            <div class="chart-card"><h3>1. Análisis y Evolución de Tan Delta</h3><div style="position: relative; height:280px; width:100%"><canvas id="chartTanDelta"></canvas></div></div>
            <div class="chart-card"><h3>2. Uso Diario (Horas de Operación)</h3><div style="position: relative; height:280px; width:100%"><canvas id="chartHoras"></canvas></div></div>
            <div class="chart-card" style="grid-column: 1 / -1;"><h3>3. Diagnóstico de Correlación: Temperatura vs. Tan Delta Promedio</h3><div style="position: relative; height:280px; width:100%"><canvas id="chartCorrelacion"></canvas></div></div>
        </div>
        <div class="table-container"><h3>Historial Consolidado Filtrado</h3><div id="contenedorTabla"></div></div>
        <div class="footer-signature">Dashboard creado por <span>Carlos Colorado</span> - Líder de Producto</div>
    </div>

    <script>
        const dbData = DATA_PLACEHOLDER;
        let chart1, chart2, chart3;

        function inicializarDashboard() {
            if(dbData && dbData.length > 0) {
                document.getElementById('fechaInicio').value = dbData[0].fecha;
                document.getElementById('fechaFin').value = dbData[dbData.length - 1].fecha;
                filtrarDashboard();
            } else {
                document.getElementById('contenedorTabla').innerHTML = '<p style="text-align:center; padding:20px;">No se encontraron datos.</p>';
            }
        }

        function filtrarDashboard() {
            if (!dbData || dbData.length === 0) return;
            
            let inicio = document.getElementById('fechaInicio').value;
            let fin = document.getElementById('fechaFin').value;
            
            let dataFiltrada = dbData;
            if (inicio && fin) {
                dataFiltrada = dbData.filter(d => d.fecha >= inicio && d.fecha <= fin);
            }

            if (dataFiltrada.length === 0) return;

            const labels = dataFiltrada.map(d => d.fecha);
            const tanMin = dataFiltrada.map(d => d.Tan_Min);
            const tanMax = dataFiltrada.map(d => d.Tan_Max);
            const tanProm = dataFiltrada.map(d => d.Tan_Prom);
            const horas = dataFiltrada.map(d => d.Horas);
            const temp = dataFiltrada.map(d => d.Temp_Prom);

            renderizarGraficas(labels, tanMin, tanMax, tanProm, horas, temp);
            renderizarTabla(dataFiltrada);
        }

        function renderizarGraficas(labels, tanMin, tanMax, tanProm, horas, temp) {
            if(chart1) chart1.destroy(); if(chart2) chart2.destroy(); if(chart3) chart3.destroy();

            chart1 = new Chart(document.getElementById('chartTanDelta'), {
                type: 'line', data: { labels: labels, datasets: [
                    { label: 'Máx Tan Delta', data: tanMax, borderColor: '#d12027', backgroundColor: 'transparent', borderWidth: 2.5, tension: 0.1 },
                    { label: 'Promedio', data: tanProm, borderColor: '#f07d1a', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5] },
                    { label: 'Mín Tan Delta', data: tanMin, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 1.5 }
                ]}, options: { responsive: true, maintainAspectRatio: false }
            });

            chart2 = new Chart(document.getElementById('chartHoras'), {
                type: 'bar', data: { labels: labels, datasets: [
                    { label: 'Horas Operación', data: horas, backgroundColor: '#475569', hoverBackgroundColor: '#d12027', borderRadius: 6 }
                ]}, options: { responsive: true, maintainAspectRatio: false }
            });

            chart3 = new Chart(document.getElementById('chartCorrelacion'), {
                type: 'bar', data: { labels: labels, datasets: [
                    { type: 'line', label: 'Tan Delta Promedio', data: tanProm, borderColor: '#d12027', backgroundColor: 'transparent', yAxisID: 'yTan', borderWidth: 2.5, tension: 0.1 },
                    { type: 'bar', label: 'Temp Promedio', data: temp, backgroundColor: 'rgba(71, 85, 105, 0.12)', borderColor: '#475569', yAxisID: 'yTemp', borderRadius: 4 }
                ]}, options: { responsive: true, maintainAspectRatio: false, scales: { yTan: { type: 'linear', position: 'left' }, yTemp: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } } } }
            });
        }

        function renderizarTabla(data) {
            let html = `<table><thead><tr><th>Fecha</th><th>Tan Delta (Mín)</th><th>Tan Delta (Máx)</th><th>Tan Delta (Prom)</th><th>Horas</th><th>Temp. Promedio</th></tr></thead><tbody>`;
            data.forEach(d => {
                html += `<tr><td style="font-weight:600; color:#475569;">${d.fecha}</td><td>${d.Tan_Min}</td><td style="color:#d12027; font-weight:700;">${d.Tan_Max}</td><td>${d.Tan_Prom}</td><td style="font-weight:500;">${d.Horas} hrs</td><td>${d.Temp_Prom}</td></tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('contenedorTabla').innerHTML = html;
        }

        function exportarPDF() {
            document.getElementById('action-panel').classList.add('no-render');
            html2pdf().set({ margin: 10, filename: 'reporte_artimo.pdf', image: { type: 'jpeg', quality: 0.98 }, html2canvas: { scale: 2, useCORS: true }, jsPDF: { unit: 'mm', format: 'a3', orientation: 'landscape' } }).from(document.getElementById('content-to-pdf')).save().then(() => { document.getElementById('action-panel').classList.remove('no-render'); });
        }

        inicializarDashboard();
    </script>
</body>
</html>"""
        
        # Reemplazos finales directos
        html_final = html_content.replace("DATA_PLACEHOLDER", json_data)
        html_final = html_final.replace("FECHA_UPDATE_PLACEHOLDER", fecha_actualizacion)
        html_final = html_final.replace("KPI_MAX_PLACEHOLDER", str(round(kpi_max, 2)))
        html_final = html_final.replace("KPI_PROM_PLACEHOLDER", str(round(kpi_prom, 2)))
        html_final = html_final.replace("KPI_HORAS_PLACEHOLDER", str(round(kpi_horas, 1)))
        
        with open(archivo_salida_html, 'w', encoding='utf-8') as f:
            f.write(html_final)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    generar_dashboard()
