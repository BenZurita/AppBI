const DashboardGrid = {
    components: {
        'kpi-card': KPICard
    },
    props: ['kpis', 'secondaryMetrics', 'charts', 'loading', 'tableData', 'tableColumns', 'isTableMode'],
    data() {
        return {
            sortKey: '',
            sortOrder: 'asc',
            chartInstances: {}
        }
    },
    template: `
        <div>
            <div v-if="loading" class="loading-overlay">
                <i class="fas fa-spinner fa-spin"></i> Cargando datos...
            </div>
            
            <!-- MODO TABLA (Detalles por restaurante) -->
            <div v-if="isTableMode" class="table-dashboard-container">
                <div class="table-header">
                    <h3>Detalle por Restaurante</h3>
                    <span class="period-badge" v-if="tableData && tableData.length > 0">
                        <i class="fas fa-calendar-alt"></i>
                        Período: {{ tablePeriod }}
                    </span>
                </div>
                
                <div class="table-responsive">
                    <table class="data-table compact-table" v-if="sortedTableData && sortedTableData.length > 0">
                        <thead>
                            <tr>
                                <th v-for="col in tableColumns" :key="col.key" 
                                    :class="{ 'text-right': col.key !== 'restaurant', 'sortable': true, 'sorted': sortKey === col.key }"
                                    @click="sortBy(col.key)">
                                    {{ col.label }}
                                    <i class="fas sort-icon" :class="getSortIcon(col.key)"></i>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(row, index) in sortedTableData" :key="index" :class="{ 'total-row': row.isTotal }">
                                <td v-for="col in tableColumns" :key="col.key" 
                                    :class="{ 'text-right': col.key !== 'restaurant', 'restaurant-name': col.key === 'restaurant', 'total-cell': row.isTotal }">
                                    {{ row[col.key] }}
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

            <!-- MODO NORMAL (Dashboard con KPIs) -->
            <template v-else>
                <!-- KPIs Principales (GMV, TRX, AOV) -->
                <div class="dashboard-grid">
                    <kpi-card 
                        v-for="(kpi, index) in kpis" 
                        :key="index"
                        :kpi="kpi">
                    </kpi-card>
                </div>

                <!-- Métricas Secundarias -->
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

                <!-- Charts Section CON WRAPPER ROBUSTO -->
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
        tablePeriod() {
            if (this.tableData && this.tableData.length > 0 && this.tableData[0].period) {
                const p = this.tableData[0].period;
                return `${p.start} al ${p.end}`;
            }
            return '';
        },
        sortedTableData() {
            if (!this.tableData) return [];
            
            const normalData = this.tableData.filter(row => !row.isTotal);
            const totalRow = this.tableData.find(row => row.isTotal);
            
            if (!this.sortKey) {
                return totalRow ? [...normalData, totalRow] : normalData;
            }
            
            const sorted = [...normalData].sort((a, b) => {
                let valA = a[this.sortKey];
                let valB = b[this.sortKey];
                
                if (typeof valA === 'string') {
                    const cleanA = valA.replace(/[$,%]/g, '').replace(/,/g, '');
                    const cleanB = valB.replace(/[$,%]/g, '').replace(/,/g, '');
                    const numA = parseFloat(cleanA);
                    const numB = parseFloat(cleanB);
                    
                    if (!isNaN(numA) && !isNaN(numB)) {
                        valA = numA;
                        valB = numB;
                    }
                }
                
                if (valA < valB) return this.sortOrder === 'asc' ? -1 : 1;
                if (valA > valB) return this.sortOrder === 'asc' ? 1 : -1;
                return 0;
            });
            
            if (totalRow) {
                sorted.push(totalRow);
            }
            
            return sorted;
        }
    },
    mounted() {
        // Renderizar charts si existen al montar
        if (!this.isTableMode && this.charts && this.charts.length > 0) {
            this.$nextTick(() => {
                setTimeout(() => this.renderCharts(), 100);
            });
        }
    },
    updated() {
        // Renderizar charts cuando se actualicen los datos
        if (!this.isTableMode && this.charts && this.charts.length > 0) {
            this.$nextTick(() => {
                this.renderCharts();
            });
        }
    },
    beforeUnmount() {
        Object.values(this.chartInstances).forEach(chart => {
            if (chart) chart.destroy();
        });
    },
    methods: {
        sortBy(key) {
            if (this.sortKey === key) {
                this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortKey = key;
                this.sortOrder = 'desc';
            }
        },
        getSortIcon(key) {
            if (this.sortKey !== key) return 'fa-sort';
            return this.sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down';
        },
        renderCharts() {
            if (!this.charts || this.isTableMode) return;
            
            this.charts.forEach((chartData, index) => {
                const canvasId = 'chart-' + index;
                const canvas = document.getElementById(canvasId);
                
                if (!canvas) {
                    console.warn('Canvas no encontrado:', canvasId);
                    return;
                }
                
                // Destruir instancia anterior si existe
                if (this.chartInstances[canvasId]) {
                    this.chartInstances[canvasId].destroy();
                    this.chartInstances[canvasId] = null;
                }
                
                // Verificar que el canvas tenga dimensiones
                if (canvas.width === 0 || canvas.height === 0) {
                    canvas.width = 800;
                    canvas.height = 300;
                }
                
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    console.error('No se pudo obtener contexto 2D');
                    return;
                }
                
                try {
                    // Configuración robusta de datos
                    const config = {
                        type: chartData.type || 'line',
                        data: chartData.data,
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            layout: {
                                padding: 10
                            },
                            plugins: {
                                legend: {
                                    display: true,
                                    position: 'top',
                                    labels: {
                                        usePointStyle: true,
                                        padding: 15,
                                        font: {
                                            size: 12,
                                            family: 'Inter, sans-serif'
                                        }
                                    }
                                },
                                tooltip: {
                                    enabled: true,
                                    backgroundColor: 'rgba(30, 41, 59, 0.95)',
                                    padding: 12,
                                    titleFont: { size: 13 },
                                    bodyFont: { size: 13 },
                                    cornerRadius: 8,
                                    callbacks: {
                                        label: function(context) {
                                            let label = context.dataset.label || '';
                                            if (label) label += ': ';
                                            if (context.parsed.y !== null && context.parsed.y !== undefined) {
                                                label += '$' + context.parsed.y.toLocaleString();
                                            }
                                            return label;
                                        }
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    display: true,
                                    grid: {
                                        color: 'rgba(0, 0, 0, 0.05)',
                                        drawBorder: false
                                    },
                                    ticks: {
                                        callback: function(value) {
                                            return '$' + value.toLocaleString();
                                        },
                                        font: { size: 11 },
                                        maxTicksLimit: 6
                                    }
                                },
                                x: {
                                    display: true,
                                    grid: {
                                        display: false
                                    },
                                    ticks: {
                                        font: { size: 11 },
                                        maxRotation: 45
                                    }
                                }
                            },
                            elements: {
                                line: {
                                    borderWidth: 3,
                                    tension: 0.4,
                                    fill: false
                                },
                                point: {
                                    radius: 5,
                                    hoverRadius: 7,
                                    backgroundColor: '#fff',
                                    borderWidth: 2
                                }
                            },
                            interaction: {
                                mode: 'index',
                                intersect: false
                            }
                        }
                    };
                    
                    this.chartInstances[canvasId] = new Chart(ctx, config);
                    console.log('Chart creado exitosamente:', canvasId);
                    
                } catch (error) {
                    console.error('Error al crear chart:', error);
                }
            });
        }
    }
};