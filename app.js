const { createApp } = Vue;

createApp({
    components: {
        'sidebar': Sidebar,
        'dashboard-grid': DashboardGrid
    },
    data() {
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        // Fecha inicio del año para el filtro de tabla
        const startOfYear = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
        
        return {
            currentDashboard: 'daily',
            sidebarOpen: true,
            loading: false,
            
            // Datos Dashboard Principal
            kpis: [],
            secondaryMetrics: [],
            charts: [],
            
            // Filtros Dashboard Principal
            selectedDate: todayStr,
            datePreset: 'today',
            restaurants: [],
            selectedRestaurant: 'all',
            
            // Filtros para Tabla de Restaurantes (independientes)
            tableStartDate: startOfYear,
            tableEndDate: todayStr,
            tableRestaurants: ['all'],
            
            // Configuración Tabla
            tableData: [],
            tableColumns: [
                { key: 'restaurant', label: 'Restaurante' },
                { key: 'gmv', label: 'GMV' },
                { key: 'trx', label: 'Transacciones' },
                { key: 'aov', label: 'AOV' },
                { key: 'barquilla', label: 'Barquilla %' },
                { key: 'queso', label: 'Queso %' },
                { key: 'agrandado', label: 'Agrandado %' },
                { key: 'cambio', label: 'Cambio Pz %' }
            ],
            
            currentDate: today.toLocaleDateString('es-ES', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            })
        };
    },
    computed: {
        dashboardTitle() {
            const titles = {
                'daily': 'Daily Sales',
                'restaurants': 'Detalle de Restaurantes',
                'inventario': 'Inventario',
                'finanzas': 'Finanzas'
            };
            return titles[this.currentDashboard] || 'Dashboard';
        },
        
        maxDate() {
            return new Date().toISOString().split('T')[0];
        },
        
        displayDate() {
            if (this.datePreset === 'today') return 'Hoy';
            if (this.datePreset === 'yesterday') return 'Ayer';
            return this.formatDisplayDate(this.selectedDate);
        },
        
        // Para mostrar el período en la tabla
        tablePeriodLabel() {
            return `${this.formatDisplayDate(this.tableStartDate)} - ${this.formatDisplayDate(this.tableEndDate)}`;
        }
    },
    mounted() {
        this.loadRestaurants();
        this.loadDashboardData();
        if (window.innerWidth <= 768) {
            this.sidebarOpen = false;
        }
    },
    methods: {
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        
        async changeDashboard(dashboardId) {
            this.currentDashboard = dashboardId;
            await this.loadDashboardData();
        },
        
        formatDisplayDate(dateString) {
            if (!dateString) return '';
            const [year, month, day] = dateString.split('-');
            return `${day}/${month}/${year}`;
        },
        
        // Cargar lista de restaurantes para selectores
        async loadRestaurants() {
            try {
                const response = await apiService.getRestaurants();
                if (response.success) {
                    this.restaurants = response.data || [];
                }
            } catch (error) {
                console.error('Error cargando restaurantes:', error);
            }
        },
        
        // Cambiar restaurante en dashboard principal
        async changeRestaurant() {
            await this.loadDashboardData();
        },
        
        // Filtros de fecha dashboard principal
        async setDatePreset(preset) {
            this.datePreset = preset;
            const today = new Date();
            
            if (preset === 'today') {
                this.selectedDate = today.toISOString().split('T')[0];
            } else if (preset === 'yesterday') {
                const yesterday = new Date(today);
                yesterday.setDate(yesterday.getDate() - 1);
                this.selectedDate = yesterday.toISOString().split('T')[0];
            }
            
            await this.loadDashboardData();
        },
        
        async onDateInputChange(event) {
            const newDate = event.target.value;
            if (newDate) {
                this.selectedDate = newDate;
                this.datePreset = 'custom';
                await this.loadDashboardData();
            }
        },
        
        // Aplicar filtro de tabla ( Dashboard restaurants )
        async applyTableFilter() {
            if (this.currentDashboard === 'restaurants') {
                await this.loadDashboardData();
            }
        },
        
        // Cargar datos según el dashboard activo
        async loadDashboardData() {
            this.loading = true;
            try {
                if (this.currentDashboard === 'restaurants') {
                    // Endpoint especial para tabla de restaurantes
                    const params = {
                        start_date: this.tableStartDate,
                        end_date: this.tableEndDate,
                        restaurants: this.tableRestaurants
                    };
                    
                    const response = await apiService.getDashboardData('restaurants', params);
                    const data = response.data || response;
                    this.tableData = data.table || [];
                    
                } else {
                    // Dashboard normal (daily, etc.)
                    const params = {
                        date: this.selectedDate,
                        preset: this.datePreset,
                        restaurant: this.selectedRestaurant
                    };
                    
                    const response = await apiService.getDashboardData(this.currentDashboard, params);
                    const data = response.data || response;
                    this.kpis = data.kpis || [];
                    this.secondaryMetrics = data.secondary_metrics || [];
                    this.charts = data.charts || [];
                }
            } catch (error) {
                console.error('Error cargando datos:', error);
                // Resetear datos según el modo
                if (this.currentDashboard === 'restaurants') {
                    this.tableData = [];
                } else {
                    this.kpis = [];
                    this.secondaryMetrics = [];
                    this.charts = [];
                }
            } finally {
                this.loading = false;
            }
        }
    }
}).mount('#app');