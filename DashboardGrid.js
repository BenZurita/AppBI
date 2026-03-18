const DashboardGrid = {
    components: {
        'kpi-card': KPICard
    },
    props: ['kpis', 'secondaryMetrics', 'charts', 'loading', 'tableData', 'tableColumns', 'isTableMode', 'isHoursMode', 'hoursData', 'isSalesByRegisterMode'],
    data() {
        return {
            sortKey: '',
            sortOrder: 'asc',
            _charts: {},
            _renderTimer: null
        }
    },
    template: `
        <div>
            <div v-if="loading" class="loading-overlay">
                <i class="fas fa-spinner fa-spin"></i> Cargando datos...
            </div>
            
            <!-- MODO PRODUCT MIX -->
            <div v-if="isTableMode" class="product-mix-wrapper">
                <div class="pm-header">
                    <h3><i class="fas fa-chart-pie" style="color: #f59e0b;"></i> Product Mix</h3>
                    <div class="pm-stats" v-if="tableData && tableData.length > 0">
                        <span class="pm-stat">
                            <strong>{{ totalProducts }}</strong> productos
                        </span>
                        <span class="pm-stat total">
                            Total: <strong>{{ formatCurrency(totalSales) }}</strong>
                        </span>
                    </div>
                </div>
                
                <div class="table-responsive">
                    <table class="pm-table" v-if="sortedTableData && sortedTableData.length > 0">
                        <thead>
                            <tr>
                                <th @click="sortBy('product_name')">
                                    Producto <i class="fas" :class="getSortIcon('product_name')"></i>
                                </th>
                                <th @click="sortBy('category_name')">
                                    Categoría <i class="fas" :class="getSortIcon('category_name')"></i>
                                </th>
                                <th class="text-right" @click="sortBy('cantidad')">
                                    Unidades <i class="fas" :class="getSortIcon('cantidad')"></i>
                                </th>
                                <th class="text-right" @click="sortBy('total_usd')">
                                    Ventas USD <i class="fas" :class="getSortIcon('total_usd')"></i>
                                </th>
                                <th @click="sortBy('pct_weight')">
                                    % del Mix <i class="fas" :class="getSortIcon('pct_weight')"></i>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(row, index) in sortedTableData" 
                                :key="index"
                                :class="{ 'pm-total': row.isTotal, 'pm-top3': index < 3 && !row.isTotal }">
                                
                                <td>
                                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                                        <i v-if="index === 0 && !row.isTotal" class="fas fa-crown" style="color: #eab308;"></i>
                                        <i v-else-if="index === 1 && !row.isTotal" class="fas fa-medal" style="color: #9ca3af;"></i>
                                        <i v-else-if="index === 2 && !row.isTotal" class="fas fa-medal" style="color: #b45309;"></i>
                                        <span :style="row.isTotal ? 'font-weight: 700; font-size: 1.1rem;' : 'font-weight: 500;'">
                                            {{ row.product_name }}
                                        </span>
                                    </div>
                                </td>
                                
                                <td>
                                    <span class="pm-category" :style="getCategoryColor(row.category_name)">
                                        {{ row.category_name || '-' }}
                                    </span>
                                </td>
                                
                                <td class="text-right">
                                    <span style="font-weight: 600; color: #475569;">
                                        {{ formatNumber(row.cantidad) }}
                                    </span>
                                </td>
                                
                                <td class="text-right">
                                    <span style="font-weight: 700; color: #059669; font-family: monospace;">
                                        {{ formatCurrency(row.total_usd) }}
                                    </span>
                                </td>
                                
                                <td>
                                    <div class="pm-mix-bar">
                                        <div class="pm-bar-bg">
                                            <div class="pm-bar-fill" 
                                                 :class="'pm-bar-' + getBarType(row.pct_weight)"
                                                 :style="{ width: Math.min(row.pct_weight, 100) + '%' }">
                                            </div>
                                        </div>
                                        <span class="pm-bar-text">{{ row.pct_weight.toFixed(1) }}%</span>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <div v-if="!tableData || tableData.length === 0" class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <p>No hay datos para el período seleccionado</p>
                </div>
            </div>

            <!-- MODO HORAS (Ventas por Hora) -->
            <div v-else-if="isHoursMode" class="hours-wrapper">
                <div class="pm-header" style="background: linear-gradient(135deg, #4c1d95 0%, #6d28d9 100%);">
                    <h3><i class="fas fa-clock" style="color: #fbbf24;"></i> Ventas por Hora</h3>
                    <div class="pm-stats" v-if="hoursData.periods && hoursData.periods.length > 0">
                        <span class="pm-stat" style="background: rgba(255,255,255,0.15);">
                            <strong>{{ hoursData.periods.filter(p => !p.isTotal).length }}</strong> períodos
                        </span>
                        <span class="pm-stat total" style="background: rgba(251, 191, 36, 0.3);">
                            Total: <strong>{{ formatCurrency(totalHoursSales) }}</strong>
                        </span>
                    </div>
                </div>

                <div class="hours-chart-section" v-if="hoursData.chart">
                    <div class="chart-container">
                        <div class="chart-header">
                            <i class="fas fa-chart-line"></i> Ventas por Hora del Día
                        </div>
                        <div class="chart-wrapper-secure" style="height: 300px;">
                            <canvas id="hoursChart" width="800" height="300"></canvas>
                        </div>
                    </div>
                </div>

                <div class="hours-table-section">
                    <h4 class="section-subtitle">
                        <i class="fas fa-th-large"></i> Resumen por Período del Día
                    </h4>
                    <div class="table-responsive">
                        <table class="pm-table hours-table" v-if="hoursData.periods && hoursData.periods.length > 0">
                            <thead>
                                <tr>
                                    <th>Período</th>
                                    <th>Horario</th>
                                    <th class="text-right">Órdenes</th>
                                    <th class="text-right">Ventas USD</th>
                                    <th class="text-right">Prom. Diario</th>
                                    <th>% del Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, index) in hoursData.periods" 
                                    :key="index"
                                    :class="{ 'pm-total': row.isTotal }"
                                    :style="!row.isTotal ? 'border-left: 4px solid ' + row.color : ''">
                                    
                                    <td>
                                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                                            <span class="period-dot" :style="'background: ' + row.color"></span>
                                            <span :style="row.isTotal ? 'font-weight: 700; font-size: 1.1rem;' : 'font-weight: 600;'">
                                                {{ row.periodo }}
                                            </span>
                                        </div>
                                    </td>
                                    
                                    <td>
                                        <span class="hours-badge" :style="'background: ' + row.color + '20; color: ' + row.color + '; border: 1px solid ' + row.color">
                                            {{ row.horario }}
                                        </span>
                                    </td>
                                    
                                    <td class="text-right">
                                        <span style="font-weight: 600; color: #170303;">
                                            {{ formatNumber(row.total_ordenes) }}
                                        </span>
                                    </td>
                                    
                                    <td class="text-right">
                                        <span style="font-weight: 700; color: #0c6b4d; font-family: monospace;">
                                            {{ formatCurrency(row.total_ventas_usd) }}
                                        </span>
                                    </td>
                                    
                                    <td class="text-right">
                                        <span style="font-weight: 500; color: #170303;">
                                            {{ formatCurrency(row.promedio_diario) }}
                                        </span>
                                    </td>
                                    
                                    <td>
                                        <div class="pm-mix-bar">
                                            <div class="pm-bar-bg">
                                                <div class="pm-bar-fill" 
                                                     :style="{ width: Math.min(row.pct_del_total, 100) + '%', background: row.color }">
                                                </div>
                                            </div>
                                            <span class="pm-bar-text">{{ row.pct_del_total.toFixed(1) }}%</span>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div v-if="!hoursData.periods || hoursData.periods.length === 0" class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <p>No hay datos de ventas por hora para el período seleccionado</p>
                </div>
            </div>

            <!-- MODO VENTA POR CAJA -->
            <div v-else-if="isSalesByRegisterMode" class="sales-by-register-wrapper">
                <div class="sbr-header">
                    <h3><i class="fas fa-cash-register" style="color: #fbbf24;"></i> Venta por Caja</h3>
                </div>

                <!-- KPIs por categoría de caja -->
                <div class="category-kpi-grid" v-if="secondaryMetrics && secondaryMetrics.length">
                    <div v-for="(cat, index) in secondaryMetrics" :key="index"
                         class="category-kpi-card"
                         :style="{ borderTop: '4px solid ' + (cat.color || '#3b82f6') }">
                        <div class="cat-kpi-header">
                            <span class="cat-kpi-dot" :style="{ background: cat.color || '#3b82f6' }"></span>
                            <h4 class="cat-kpi-title">{{ cat.category }}</h4>
                        </div>
                        <div class="cat-kpi-metrics">
                            <div class="cat-kpi-metric">
                                <span class="cat-kpi-label">GMV</span>
                                <span class="cat-kpi-value">&#36;{{ formatNumber(cat.gmv) }}</span>
                                <span class="cat-kpi-trend" :class="cat.gmv_trend">
                                    <i :class="cat.gmv_trend === 'up' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                                    {{ Math.abs(cat.gmv_diff_pct) }}%
                                </span>
                            </div>
                            <div class="cat-kpi-metric">
                                <span class="cat-kpi-label">TRX</span>
                                <span class="cat-kpi-value">{{ formatNumber(cat.trx) }}</span>
                                <span class="cat-kpi-trend" :class="cat.trx_trend">
                                    <i :class="cat.trx_trend === 'up' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                                    {{ Math.abs(cat.trx_diff_pct) }}%
                                </span>
                            </div>
                            <div class="cat-kpi-metric">
                                <span class="cat-kpi-label">AOV</span>
                                <span class="cat-kpi-value">&#36;{{ formatNumber(cat.aov) }}</span>
                            </div>
                            <div class="cat-kpi-metric">
                                <span class="cat-kpi-label">% GMV</span>
                                <span class="cat-kpi-value" style="color: #6366f1;">{{ cat.pct_gmv }}%</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="sbr-table-section">
                    <h4 class="section-subtitle">
                        <i class="fas fa-th-list"></i> Detalle por Caja
                    </h4>
                    <div class="table-responsive">
                        <table class="pm-table sbr-table" v-if="tableData && tableData.length > 0">
                            <thead>
                                <tr>
                                    <th>Caja</th>
                                    <th>Categoría</th>
                                    <th class="text-right">GMV</th>
                                    <th class="text-right">vs Ayer</th>
                                    <th class="text-right">TRX</th>
                                    <th class="text-right">vs Ayer</th>
                                    <th class="text-right">AOV</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, index) in tableData" :key="index">
                                    <td>
                                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                                            <i class="fas fa-desktop" style="color: #3b82f6;"></i>
                                            <strong>{{ row.caja }}</strong>
                                        </div>
                                    </td>
                                    <td>
                                        <span class="pm-category" :style="getCategoryStyle(row.category)">
                                            {{ row.category }}
                                        </span>
                                    </td>
                                    <td class="text-right" style="font-weight: 700; color: #059669;">
                                        &#36;{{ formatNumber(row.gmv) }}
                                    </td>
                                    <td class="text-right">
                                        <span :class="['trend-badge', row.gmv_trend]">
                                            <i :class="row.gmv_trend === 'up' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                                            &#36;{{ formatNumber(Math.abs(row.gmv_diff)) }}
                                        </span>
                                    </td>
                                    <td class="text-right" style="font-weight: 600;">
                                        {{ formatNumber(row.trx) }}
                                    </td>
                                    <td class="text-right">
                                        <span :class="['trend-badge', row.trx_trend]">
                                            <i :class="row.trx_trend === 'up' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                                            {{ formatNumber(Math.abs(row.trx_diff)) }}
                                        </span>
                                    </td>
                                    <td class="text-right" style="font-family: monospace;">
                                        &#36;{{ formatNumber(row.aov) }}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div v-if="!tableData || tableData.length === 0" class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <p>No hay datos de ventas por caja para el período seleccionado</p>
                </div>
            </div>

            <!-- MODO NORMAL (Dashboard con KPIs) -->
            <template v-else>
                <div class="dashboard-grid">
                    <kpi-card 
                        v-for="(kpi, index) in kpis" 
                        :key="index"
                        :kpi="kpi">
                    </kpi-card>
                </div>

                <div class="secondary-metrics-section" v-if="secondaryMetrics && secondaryMetrics.length">
                    <h3 class="section-title">
                        <i class="fas fa-percentage"></i>
                        Métricas de Producto
                    </h3>
                    <div class="secondary-metrics-grid">
                        <div 
                            v-for="(metric, index) in secondaryMetrics" 
                            :key="index"
                            class="secondary-metric-card"
                            :class="metric.color">
                            <div class="metric-header">
                                <div class="metric-icon" :class="metric.color">
                                    <i :class="metric.icon"></i>
                                </div>
                                <h4 class="metric-title">{{ metric.title }}</h4>
                            </div>
                            
                            <div class="metric-periods">
                                <div class="metric-period" v-for="(period, idx) in metric.periodos" :key="idx">
                                    <span class="period-label">{{ period.nombre }}</span>
                                    <span class="period-value">{{ period.valor }}</span>
                                    <div class="period-trend" :class="period.trend">
                                        <i :class="period.trend === 'up' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                                        <span>{{ period.diff_pct }}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="charts-section" v-if="charts && charts.length">
                    <div class="chart-container" v-for="(chart, index) in charts" :key="index">
                        <div class="chart-header">{{ chart.title }}</div>
                        <div class="chart-wrapper-secure">
                            <canvas :id="'chart-' + index" width="800" height="300"></canvas>
                        </div>
                    </div>
                </div>
            </template>
        </div>
    `,
    computed: {
        sortedTableData() {
            if (!this.tableData) return [];
            const normalData = this.tableData.filter(row => !row.isTotal);
            const totalRow = this.tableData.find(row => row.isTotal);
            if (!this.sortKey) return totalRow ? [...normalData, totalRow] : normalData;
            const sorted = [...normalData].sort((a, b) => {
                if (this.sortKey === 'product_name' || this.sortKey === 'category_name') {
                    return this.sortOrder === 'asc'
                        ? (a[this.sortKey]||'').localeCompare(b[this.sortKey]||'')
                        : (b[this.sortKey]||'').localeCompare(a[this.sortKey]||'');
                }
                const va = parseFloat(a[this.sortKey]) || 0;
                const vb = parseFloat(b[this.sortKey]) || 0;
                return this.sortOrder === 'asc' ? va - vb : vb - va;
            });
            if (totalRow) sorted.push(totalRow);
            return sorted;
        },
        totalProducts() { return this.tableData ? this.tableData.filter(r => !r.isTotal).length : 0; },
        totalSales() { const t = this.tableData && this.tableData.find(r => r.isTotal); return t ? t.total_usd : 0; },
        totalHoursSales() { const t = this.hoursData && this.hoursData.periods && this.hoursData.periods.find(r => r.isTotal); return t ? t.total_ventas_usd : 0; },
        hasSecondaryMetrics() { return Array.isArray(this.secondaryMetrics) && this.secondaryMetrics.length > 0; },
        safeSecondaryMetrics() {
            if (!this.hasSecondaryMetrics) return [];
            return this.secondaryMetrics.filter(cat => cat && typeof cat === 'object');
        }
    },

    mounted() {
        this.$nextTick(() => setTimeout(() => this._renderAll(), 200));
    },

    beforeUnmount() {
        this._destroyAll();
    },

    watch: {
        hoursData(newVal) {
            if (newVal && newVal.chart) this._scheduleRender();
        },
        isHoursMode() { this._scheduleRender(); },
        isTableMode(v) { if (v) this._destroyAll(); }
    },

    methods: {

        // ── Utilidades de canvas ──────────────────────────────────────────

        /** Destruye cualquier chart en un canvas por id, y devuelve un canvas nuevo limpio */
        _freshCanvas(canvasId, parentSelector) {
            // 1. Destruir instancia guardada
            if (this._charts[canvasId]) {
                try { this._charts[canvasId].destroy(); } catch(e) {}
                this._charts[canvasId] = null;
            }
            // 2. Destruir instancia huérfana registrada en Chart.js
            const old = document.getElementById(canvasId);
            if (old) {
                const orphan = Chart.getChart(old);
                if (orphan) { try { orphan.destroy(); } catch(e) {} }
                old.remove();
            }
            // 3. Crear canvas nuevo en el padre
            const parent = document.querySelector(parentSelector);
            if (!parent) return null;
            const canvas = document.createElement('canvas');
            canvas.id = canvasId;
            parent.appendChild(canvas);
            return canvas;
        },

        _destroyAll() {
            Object.keys(this._charts || {}).forEach(k => {
                if (this._charts[k]) {
                    try { this._charts[k].destroy(); } catch(e) {}
                    this._charts[k] = null;
                }
            });
            this._charts = {};
        },

        _scheduleRender() {
            if (this._renderTimer) { clearTimeout(this._renderTimer); this._renderTimer = null; }
            this._renderTimer = setTimeout(() => {
                this.$nextTick(() => {
                    this._renderAll();
                    this._renderTimer = null;
                });
            }, 80);
        },

        _renderAll() {
            if (this.isHoursMode) {
                if (this.hoursData && this.hoursData.chart) this._renderHoursChart();
            } else if (!this.isTableMode && !this.isSalesByRegisterMode) {
                this._renderDailyCharts();
            }
        },

        // ── Hours ─────────────────────────────────────────────────────────

        _renderHoursChart() {
            if (!this.hoursData || !this.hoursData.chart) return;
            const canvas = this._freshCanvas('hoursChart', '.hours-chart-section .chart-wrapper-secure');
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            const data = this.hoursData.chart;
            const gradient = ctx.createLinearGradient(0,0,0,300);
            gradient.addColorStop(0,'rgba(139,92,246,0.3)');
            gradient.addColorStop(1,'rgba(139,92,246,0.05)');

            this._charts['hoursChart'] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.hours,
                    datasets: [
                        { label:'Ventas USD', data:data.sales, borderColor:'#8b5cf6', backgroundColor:gradient,
                          borderWidth:3, fill:true, tension:0.4,
                          pointBackgroundColor:'#8b5cf6', pointBorderColor:'#fff', pointBorderWidth:2, pointRadius:4, pointHoverRadius:6 },
                        { label:'Órdenes', data:data.orders, borderColor:'#f59e0b', backgroundColor:'transparent',
                          borderWidth:2, borderDash:[5,5], fill:false, tension:0.4,
                          pointBackgroundColor:'#f59e0b', pointBorderColor:'#fff', pointBorderWidth:2, pointRadius:3, yAxisID:'y1' }
                    ]
                },
                options: {
                    responsive:true, maintainAspectRatio:false,
                    interaction:{ mode:'index', intersect:false },
                    plugins: {
                        legend:{ position:'top', labels:{usePointStyle:true, padding:15} },
                        tooltip:{ backgroundColor:'rgba(30,41,59,0.95)', padding:12, cornerRadius:8,
                            callbacks:{ label: ctx => {
                                let l = (ctx.dataset.label||'')+': ';
                                return l + (ctx.dataset.label==='Ventas USD' ? '$'+ctx.parsed.y.toLocaleString() : ctx.parsed.y.toLocaleString());
                            }}}
                    },
                    scales: {
                        x:{ grid:{display:false}, ticks:{ maxRotation:45, callback: function(v){ const h=parseInt(this.getLabelForValue(v)); return h%3===0?this.getLabelForValue(v):''; }}},
                        y:{ beginAtZero:true, grid:{color:'rgba(0,0,0,0.05)'}, ticks:{callback: v=>'$'+(v/1000).toFixed(0)+'k'} },
                        y1:{ type:'linear', display:false, position:'right', beginAtZero:true, grid:{drawOnChartArea:false} }
                    }
                }
            });
        },

        // ── Daily charts ──────────────────────────────────────────────────

        _renderDailyCharts() {
            if (!this.charts) return;
            const valid = this.charts.filter(c => c && c.data && Array.isArray(c.data.datasets) && c.data.datasets.length > 0);
            valid.forEach((chartData, index) => {
                const id = 'chart-' + index;
                const canvas = this._freshCanvas(id, '.chart-wrapper-secure');
                if (!canvas) return;
                try {
                    this._charts[id] = new Chart(canvas.getContext('2d'), {
                        type: chartData.type || 'line',
                        data: chartData.data,
                        options: {
                            responsive:true, maintainAspectRatio:false,
                            plugins: {
                                legend:{ display:true, position:'top', labels:{usePointStyle:true, padding:15, font:{size:12}} },
                                tooltip:{ enabled:true, backgroundColor:'rgba(30,41,59,0.95)', padding:12, cornerRadius:8,
                                    callbacks:{ label: ctx => { let l=(ctx.dataset.label||'')+': '; if(ctx.parsed.y!=null) l+='$'+ctx.parsed.y.toLocaleString(); return l; }}}
                            },
                            scales: {
                                y:{ beginAtZero:true, grid:{color:'rgba(0,0,0,0.05)'}, ticks:{callback: v=>'$'+v.toLocaleString(), maxTicksLimit:6} },
                                x:{ grid:{display:false} }
                            },
                            interaction:{ mode:'index', intersect:false }
                        }
                    });
                } catch(e) { console.error('Error creando chart '+id+':', e); }
            });
        },

        // ── Helpers de UI ─────────────────────────────────────────────────

        getDonutCardStyle(cat) {
            if (!cat||typeof cat!=='object') return { borderTop:'4px solid #ccc' };
            return { borderTop:'4px solid '+(cat.color||'#ccc') };
        },
        getCatName(cat) { return (cat&&cat.category)||'Sin categoría'; },
        getCatPct(cat) { if(!cat) return 0; const p=cat.pct_gmv; return (p!=null&&!isNaN(p))?p:0; },
        getCatGmv(cat) { if(!cat||isNaN(cat.gmv)) return '0'; return cat.gmv.toLocaleString('es-ES'); },
        getCatTrx(cat) { if(!cat||isNaN(cat.trx)) return '0'; return cat.trx.toLocaleString('es-ES'); },

        sortBy(key) {
            if (this.sortKey===key) { this.sortOrder = this.sortOrder==='asc'?'desc':'asc'; }
            else { this.sortKey=key; this.sortOrder='desc'; }
        },
        getSortIcon(key) { if(this.sortKey!==key) return 'fa-sort'; return this.sortOrder==='asc'?'fa-sort-up':'fa-sort-down'; },
        formatNumber(n) { if(n==null||isNaN(n)) return '0'; return Number(n).toLocaleString('es-ES'); },
        formatCurrency(n) { if(n==null||isNaN(n)) return '$0.00'; return '$'+Number(n).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2}); },
        getCategoryColor(cat) {
            const c = { 'Helados':'background:#fef3c7;color:#92400e;border:1px solid #f59e0b;', 'Bebidas':'background:#dbeafe;color:#1e40af;border:1px solid #3b82f6;', 'Toppings':'background:#fce7f3;color:#9d174d;border:1px solid #ec4899;', 'Combos':'background:#d1fae5;color:#065f46;border:1px solid #10b981;', 'Snacks':'background:#ffedd5;color:#9a3412;border:1px solid #f97316;' };
            return c[cat]||'background:#f3f4f6;color:#4b5563;border:1px solid #d1d5db;';
        },
        getCategoryStyle(cat) {
            const c = { 'Principal':'background:#dbeafe;color:#1e40af;border:1px solid #3b82f6;', 'Secundaria':'background:#d1fae5;color:#065f46;border:1px solid #10b981;', 'Express':'background:#fef3c7;color:#92400e;border:1px solid #f59e0b;', 'Drive Thru':'background:#fce7f3;color:#9d174d;border:1px solid #ec4899;', 'Delivery':'background:#e0e7ff;color:#3730a3;border:1px solid #6366f1;' };
            return c[cat]||'background:#f3f4f6;color:#4b5563;border:1px solid #d1d5db;';
        },
        getBarType(pct) { if(pct>=20) return 'high'; if(pct>=10) return 'med'; if(pct>=5) return 'low'; return 'min'; }
    }
};