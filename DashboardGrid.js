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
            
            <!-- MODO TABLA (Product Mix) -->
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
            
            if (!this.sortKey) {
                return totalRow ? [...normalData, totalRow] : normalData;
            }
            
            const sorted = [...normalData].sort((a, b) => {
                let valA = parseFloat(a[this.sortKey]) || 0;
                let valB = parseFloat(b[this.sortKey]) || 0;
                
                if (this.sortKey === 'product_name' || this.sortKey === 'category_name') {
                    valA = a[this.sortKey] || '';
                    valB = b[this.sortKey] || '';
                    return this.sortOrder === 'asc' 
                        ? valA.localeCompare(valB) 
                        : valB.localeCompare(valA);
                }
                
                return this.sortOrder === 'asc' ? valA - valB : valB - valA;
            });
            
            if (totalRow) sorted.push(totalRow);
            return sorted;
        },
        totalProducts() {
            return this.tableData ? this.tableData.filter(r => !r.isTotal).length : 0;
        },
        totalSales() {
            const totalRow = this.tableData.find(r => r.isTotal);
            return totalRow ? totalRow.total_usd : 0;
        }
    },
    mounted() {
        if (!this.isTableMode && this.charts && this.charts.length > 0) {
            this.$nextTick(() => setTimeout(() => this.renderCharts(), 100));
        }
    },
    updated() {
        if (!this.isTableMode && this.charts && this.charts.length > 0) {
            this.$nextTick(() => this.renderCharts());
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
        formatNumber(num) {
            if (num === undefined || num === null) return '0';
            return num.toLocaleString('es-ES');
        },
        formatCurrency(num) {
            if (num === undefined || num === null) return '$0.00';
            return '$' + num.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        },
        getCategoryColor(category) {
            const colors = {
                'Helados': 'background: #fef3c7; color: #92400e; border: 1px solid #f59e0b;',
                'Bebidas': 'background: #dbeafe; color: #1e40af; border: 1px solid #3b82f6;',
                'Toppings': 'background: #fce7f3; color: #9d174d; border: 1px solid #ec4899;',
                'Combos': 'background: #d1fae5; color: #065f46; border: 1px solid #10b981;',
                'Snacks': 'background: #ffedd5; color: #9a3412; border: 1px solid #f97316;'
            };
            return colors[category] || 'background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db;';
        },
        getBarType(pct) {
            if (pct >= 20) return 'high';
            if (pct >= 10) return 'med';
            if (pct >= 5) return 'low';
            return 'min';
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
                
                if (this.chartInstances[canvasId]) {
                    this.chartInstances[canvasId].destroy();
                    this.chartInstances[canvasId] = null;
                }
                
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