const { createApp } = Vue;

createApp({
    components: {
        'sidebar': Sidebar,
        'dashboard-grid': DashboardGrid
    },
    data() {
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        const startOfYear = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
        
        if (!apiService.isAuthenticated()) {
            window.location.href = '/login.html';
            return {};
        }
        
        return {
            currentDashboard: 'daily',
            sidebarOpen: true,
            loading: false,
            
            userRole: apiService.getRole(),
            userRestaurantCode: apiService.getRestaurantCode(),
            username: apiService.getUsername(),
            userRestaurantName: '',
            
            kpis: [],
            secondaryMetrics: [],
            charts: [],
            
            selectedDate: todayStr,
            datePreset: 'today',
            restaurants: [],
            selectedRestaurant: apiService.isAdmin() ? 'all' : apiService.getRestaurantCode(),
            
            tableStartDate: startOfYear,
            tableEndDate: todayStr,
            tableRestaurants: apiService.isAdmin() ? ['all'] : [apiService.getRestaurantCode()],
            showRestaurantDropdown: false,
            
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
                'salesbyregister': 'Venta por Caja',
                'productmix': 'Product Mix',
                'hours': 'Ventas por Hora'
            };
            return titles[this.currentDashboard] || 'Dashboard';
        },
        
        isAdmin() {
            return apiService.isAdmin();
        },
        
        maxDate() {
            return new Date().toISOString().split('T')[0];
        },
        
        displayDate() {
            if (this.datePreset === 'today') return 'Hoy';
            if (this.datePreset === 'yesterday') return 'Ayer';
            return this.formatDisplayDate(this.selectedDate);
        },
        
        tablePeriodLabel() {
            return `${this.formatDisplayDate(this.tableStartDate)} - ${this.formatDisplayDate(this.tableEndDate)}`;
        },
        
        isAllSelected() {
            return this.tableRestaurants.includes('all') || this.tableRestaurants.length === this.restaurants.length;
        },
        
        selectedRestaurantsText() {
            if (this.tableRestaurants.includes('all') || this.tableRestaurants.length === 0) {
                return 'Todos los restaurantes';
            }
            if (this.tableRestaurants.length === 1) {
                const rest = this.restaurants.find(r => r.id === this.tableRestaurants[0]);
                return rest ? rest.name : '1 seleccionado';
            }
            return `${this.tableRestaurants.length} restaurantes seleccionados`;
        }
    },
    mounted() {
        if (!apiService.isAuthenticated()) {
            window.location.href = '/login.html';
            return;
        }
        
        if (!apiService.isAdmin()) {
            this.selectedRestaurant = apiService.getRestaurantCode();
            this.tableRestaurants = [apiService.getRestaurantCode()];
        }
        
        this.loadRestaurants();
        this.loadDashboardData();
        
        if (window.innerWidth <= 768) {
            this.sidebarOpen = false;
        }
        
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.custom-dropdown')) {
                this.showRestaurantDropdown = false;
            }
        });
    },
    methods: {
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        
        logout() {
            apiService.logout();
        },
        
        async changeDashboard(dashboardId) {
            if (!this.isAdmin && dashboardId === 'restaurants') {
                alert('Solo los administradores pueden ver el detalle de todos los restaurantes.');
                return;
            }
            this.currentDashboard = dashboardId;
            await this.loadDashboardData();
        },
        
        formatDisplayDate(dateString) {
            if (!dateString) return '';
            const [year, month, day] = dateString.split('-');
            return `${day}/${month}/${year}`;
        },
        
        async loadRestaurants() {
            try {
                const response = await apiService.getRestaurants();
                if (response.success) {
                    this.restaurants = response.data || [];
                    
                    if (!this.isAdmin && this.userRestaurantCode) {
                        const userRest = this.restaurants.find(r => 
                            String(r.id) === String(this.userRestaurantCode)
                        );
                        if (userRest) {
                            this.userRestaurantName = userRest.name;
                        }
                    }
                }
            } catch (error) {
                console.error('Error cargando restaurantes:', error);
            }
        },
        
        async changeRestaurant() {
            if (!this.isAdmin && this.selectedRestaurant !== this.userRestaurantCode) {
                this.selectedRestaurant = this.userRestaurantCode;
                alert('Solo puedes ver tu restaurante asignado');
                return;
            }
            await this.loadDashboardData();
        },
        
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
        
        async applyTableFilter() {
            if (!this.isAdmin) {
                this.tableRestaurants = [this.userRestaurantCode];
            }
            if (this.currentDashboard === 'restaurants') {
                await this.loadDashboardData();
            }
        },
        
        toggleRestaurant(restId) {
            if (this.tableRestaurants.includes('all')) {
                this.tableRestaurants = [restId];
            } else {
                const index = this.tableRestaurants.indexOf(restId);
                if (index > -1) {
                    this.tableRestaurants.splice(index, 1);
                    if (this.tableRestaurants.length === 0) {
                        this.tableRestaurants = ['all'];
                    }
                } else {
                    this.tableRestaurants.push(restId);
                }
            }
        },
        
        toggleAllRestaurants() {
            if (this.isAllSelected) {
                this.tableRestaurants = [];
            } else {
                this.tableRestaurants = ['all'];
            }
        },
        
        prepareSalesByRegisterData(chartMain) {
            if (!chartMain || !chartMain.labels) return { labels: [], datasets: [] };
            
            const periodLabels = { hoy: 'Hoy', ayer: 'Ayer', semana: 'Esta Semana', mes: 'Este Mes' };
            const periodColors = {
                hoy: '#10b981',
                ayer: '#6b7280',
                semana: '#3b82f6',
                mes: '#f59e0b'
            };
            
            const datasets = [];
            
            ['gmv', 'trx', 'aov'].forEach(metric => {
                Object.keys(chartMain.datasets[metric]).forEach(period => {
                    datasets.push({
                        label: `${metric.toUpperCase()} ${periodLabels[period]}`,
                        data: chartMain.datasets[metric][period],
                        backgroundColor: periodColors[period],
                        borderColor: periodColors[period],
                        borderWidth: 1,
                        borderRadius: 4,
                        hidden: metric !== 'gmv' || period !== 'hoy',
                        metric: metric,
                        period: period
                    });
                });
            });
            
            return {
                labels: chartMain.labels,
                datasets: datasets
            };
        },
        
        async loadDashboardData() {
            this.loading = true;
            try {
                if (this.currentDashboard === 'salesbyregister') {
                    const params = {
                        date: this.selectedDate,
                        preset: this.datePreset,
                        restaurant: this.isAdmin ? this.selectedRestaurant : apiService.getUnifiedTeamSk()
                    };
                    
                    console.log('[DEBUG] Loading SalesByRegister with params:', params);
                    const response = await apiService.getDashboardData('salesbyregister', params);
                    const data = response.data || response;
                    
                    const chartData = this.prepareSalesByRegisterData(data.chart_main);
                    
                    this.charts = [{
                        type: 'bar',
                        title: 'Métricas por Caja',
                        data: chartData,
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            interaction: {
                                mode: 'index',
                                intersect: false
                            },
                            plugins: {
                                legend: {
                                    position: 'top',
                                    labels: {
                                        usePointStyle: true,
                                        padding: 15
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    grid: { display: false }
                                },
                                y: {
                                    beginAtZero: true,
                                    grid: { color: 'rgba(0, 0, 0, 0.05)' }
                                }
                            }
                        }
                    }];
                    
                    this.secondaryMetrics = data.category_donuts || [];
                    this.tableData = data.table || [];
                    
                } else if (this.currentDashboard === 'productmix') {
                    const params = {
                        start_date: this.tableStartDate,
                        end_date: this.tableEndDate,
                        restaurant: this.isAdmin ? this.selectedRestaurant : apiService.getUnifiedTeamSk()
                    };
                    
                    const response = await apiService.getDashboardData('productmix', params);
                    const data = response.data || response;
                    this.tableData = data.table || [];
                    
                } else if (this.currentDashboard === 'hours') {
                    const params = {
                        start_date: this.tableStartDate,
                        end_date: this.tableEndDate,
                        restaurant: this.isAdmin ? this.selectedRestaurant : apiService.getUnifiedTeamSk()
                    };
                    
                    const response = await apiService.getDashboardData('hours', params);
                    const data = response.data || response;
                    
                    this.hoursData = {
                        chart: data.chart || null,
                        periods: data.periods_table || []
                    };
                    
                } else {
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
                if (this.currentDashboard === 'salesbyregister') {
                    this.charts = [];
                    this.secondaryMetrics = [];
                    this.tableData = [];
                } else if (this.currentDashboard === 'productmix') {
                    this.tableData = [];
                } else if (this.currentDashboard === 'hours') {
                    this.hoursData = { chart: null, periods: [] };
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